"""Provider interface plus the shared logic for LLM-backed providers.

Subclasses only implement ``_complete(system, user) -> str``. Everything else
(batching, JSON parsing, retries, validation and hallucination guards) lives
here so every model is held to the same standard.
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from .. import prompts
from ..schemas import Answer, Citation, Clause, ClauseLabel, ContractSummary, Finding, RiskLevel
from ..taxonomy import BY_KEY, describe_for_prompt, keyword_scores

log = logging.getLogger(__name__)

# Clause types worth sending to the LLM for a deeper risk read
REVIEWABLE = {
    "limitation_of_liability", "uncapped_liability", "indemnification", "ip_ownership", "license_grant",
    "termination_for_convenience", "termination_for_cause", "renewal", "term", "payment", "price_restrictions",
    "confidentiality", "non_compete", "non_solicit", "exclusivity", "assignment", "warranty",
    "data_protection", "dispute_resolution", "insurance", "audit_rights",
}


class Provider(ABC):
    name: str = "base"

    @abstractmethod
    def classify(self, clauses: list[Clause]) -> list[ClauseLabel]: ...

    @abstractmethod
    def review(self, clauses: list[Clause], labels: list[ClauseLabel], playbook: Any,
               existing: list[Finding], contract_type: str) -> list[Finding]: ...

    @abstractmethod
    def summarize(self, text: str) -> ContractSummary: ...

    @abstractmethod
    def answer(self, question: str, context: list[Clause]) -> Answer: ...


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def extract_json(raw: str) -> dict[str, Any]:
    """Parse a JSON object from a model reply, tolerating code fences and chatter."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(raw[start:end + 1])


class LLMProvider(Provider):
    """Base class for real model providers (Claude, OpenAI, Ollama)."""

    batch_size = 10
    max_clause_chars = 1800

    def __init__(self, model: str, max_retries: int = 2):
        self.model = model
        self.max_retries = max_retries
        self.calls = 0

    # -------------------------------------------------------------- transport
    @abstractmethod
    def _complete(self, system: str, user: str) -> str: ...

    def _json(self, user: str) -> dict[str, Any]:
        last_err: Optional[Exception] = None
        prompt = user
        for _ in range(self.max_retries + 1):
            self.calls += 1
            raw = self._complete(prompts.SYSTEM, prompt)
            try:
                return extract_json(raw)
            except (json.JSONDecodeError, ValueError) as e:
                last_err = e
                prompt = user + f"\n\nYour previous reply was not valid JSON ({e}). Reply with JSON only."
        raise RuntimeError(f"{self.name}: model did not return valid JSON: {last_err}")

    def _fmt_clauses(self, clauses: list[Clause], hints: bool = False) -> str:
        parts = []
        for c in clauses:
            body = c.text if len(c.text) <= self.max_clause_chars else c.text[: self.max_clause_chars] + " …[truncated]"
            line = f"[{c.id}] {c.heading or ''}\n{body}"
            if hints:
                sc = keyword_scores(c.text, c.heading)
                if sc:
                    line += f"\n(hint: {max(sc, key=sc.get)})"
            parts.append(line)
        return "\n\n---\n\n".join(parts)

    # ----------------------------------------------------------------- tasks
    def classify(self, clauses: list[Clause]) -> list[ClauseLabel]:
        ids = {c.id for c in clauses}
        labels: list[ClauseLabel] = []
        for i in range(0, len(clauses), self.batch_size):
            batch = clauses[i:i + self.batch_size]
            data = self._json(prompts.CLASSIFY.format(taxonomy=describe_for_prompt(),
                                                      clauses=self._fmt_clauses(batch, hints=True)))
            got = set()
            for item in data.get("labels", []):
                cid, ctype = item.get("clause_id"), item.get("clause_type")
                if cid not in ids:
                    continue
                if ctype not in BY_KEY:
                    ctype = "other"
                conf = float(item.get("confidence", 0.5))
                labels.append(ClauseLabel(clause_id=cid, clause_type=ctype, confidence=max(0.0, min(1.0, conf)),
                                          rationale=item.get("rationale")))
                got.add(cid)
            for c in batch:  # never leave a clause unlabeled
                if c.id not in got:
                    labels.append(ClauseLabel(clause_id=c.id, clause_type="other", confidence=0.2,
                                              rationale="not labeled by model"))
        return labels

    def review(self, clauses, labels, playbook, existing, contract_type):
        types_of: dict[str, set[str]] = {}
        for lab in labels:
            types_of.setdefault(lab.clause_id, set()).add(lab.clause_type)
        targets = [c for c in clauses if types_of.get(c.id, set()) & REVIEWABLE]
        if not targets:
            return []

        positions = "\n".join(f"- {r.title}: {r.redline or r.explanation}" for r in playbook.rules)
        by_id = {c.id: c for c in clauses}
        out: list[Finding] = []
        for i in range(0, len(targets), self.batch_size):
            batch = targets[i:i + self.batch_size]
            batch_ids = {c.id for c in batch}
            already = "\n".join(f"- [{f.clause_id}] {f.title}" for f in existing if f.clause_id in batch_ids) or "- none"
            data = self._json(prompts.REVIEW.format(
                contract_type=contract_type, playbook_name=playbook.name, positions=positions,
                already=already, clauses=self._fmt_clauses(batch)))
            for k, item in enumerate(data.get("findings", [])):
                cid = item.get("clause_id")
                if cid not in batch_ids:
                    continue
                evidence = (item.get("evidence") or "").strip().strip('"')
                # Hallucination guard: the quote must really be in the clause
                if not evidence or _norm(evidence) not in _norm(by_id[cid].text):
                    log.info("Dropping ungrounded LLM finding on %s: %r", cid, evidence[:80])
                    continue
                try:
                    risk = RiskLevel(str(item.get("risk", "medium")).lower())
                except ValueError:
                    risk = RiskLevel.MEDIUM
                ctype = next(iter(sorted(types_of.get(cid, {"other"}) & REVIEWABLE)), None)
                out.append(Finding(
                    rule_id=f"LLM-{cid}-{k + 1}", title=str(item.get("title", "Issue"))[:80], risk=risk,
                    clause_id=cid, clause_type=ctype, evidence=evidence, explanation=item.get("explanation", ""),
                    suggested_redline=item.get("suggested_redline"), source="llm"))
        return out

    def summarize(self, text: str) -> ContractSummary:
        data = self._json(prompts.SUMMARY.format(text=text[:8000]))
        allowed = ContractSummary.model_fields.keys()
        return ContractSummary(**{k: v for k, v in data.items() if k in allowed and v is not None})

    def answer(self, question: str, context: list[Clause]) -> Answer:
        ctx = "\n\n".join(f"[{c.id}] {c.heading or ''}\n{c.text[:2500]}" for c in context)
        data = self._json(prompts.ANSWER.format(context=ctx, question=question))
        by_id = {c.id: c for c in context}
        cites = [Citation(clause_id=cid, heading=by_id[cid].heading, excerpt=by_id[cid].text[:300])
                 for cid in data.get("citations", []) if cid in by_id]
        grounded = bool(data.get("grounded", bool(cites))) and bool(cites)
        return Answer(question=question, answer=data.get("answer", ""), citations=cites, grounded=grounded)

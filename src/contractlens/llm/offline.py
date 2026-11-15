"""Offline provider: keyword classifier + regex extraction + extractive Q&A.

Runs with no API key and no network. Used for the demo, for CI, and as the
baseline the LLM providers are measured against in ``eval/``.
"""
from __future__ import annotations

import re
from typing import Any

from ..retrieval import expand_query
from ..schemas import Answer, Citation, Clause, ClauseLabel, ContractSummary, Finding
from ..taxonomy import keyword_scores
from .base import Provider

_HEADING_PREFIX = re.compile(r"^\s*(?:(?:section|article)\s+)?[\dIVX]{1,4}\.?\s+[A-Z][^.\n]{0,70}\.\s+", re.I)

_CONTRACT_TYPES = [
    (r"mutual non-?disclosure|mutual confidentiality", "Mutual NDA"),
    (r"non-?disclosure|confidentiality agreement", "NDA"),
    (r"master services? agreement", "Master Services Agreement"),
    (r"software as a service|saas|subscription agreement", "SaaS Subscription Agreement"),
    (r"software licen[cs]e", "Software License Agreement"),
    (r"employment agreement|offer of employment", "Employment Agreement"),
    (r"consult(ing|ancy) agreement|independent contractor", "Consulting Agreement"),
    (r"distribution agreement|distributor", "Distribution Agreement"),
    (r"lease agreement|tenancy", "Lease"),
    (r"services? agreement", "Services Agreement"),
]
_STOP = set("the a an of to and or in on for is are be by with what which who when how does do this that it any shall".split())


def _stem(w: str) -> str:
    for suf in ("ations", "ation", "ing", "ies", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _tokens(s: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP and len(w) > 2}


class OfflineProvider(Provider):
    name = "offline"

    def classify(self, clauses: list[Clause]) -> list[ClauseLabel]:
        labels = []
        for c in clauses:
            scores = keyword_scores(c.text, c.heading)
            if not scores or max(scores.values()) < 2.5:
                labels.append(ClauseLabel(clause_id=c.id, clause_type="other", confidence=0.3, rationale="no strong keywords"))
                continue
            top = max(scores.values())
            for key, s in sorted(scores.items(), key=lambda kv: -kv[1])[:3]:
                if s == top or (s >= 0.4 * top and s >= 3):
                    labels.append(ClauseLabel(clause_id=c.id, clause_type=key, confidence=round(min(0.95, 0.35 + s / 12), 2),
                                              rationale="keyword match"))
        return labels

    def review(self, clauses: list[Clause], labels: list[ClauseLabel], playbook: Any,
               existing: list[Finding], contract_type: str) -> list[Finding]:
        return []  # the rule engine already covers offline review

    def summarize(self, text: str) -> ContractSummary:
        head = text[:6000]
        ctype = next((name for pat, name in _CONTRACT_TYPES if re.search(pat, head[:1500], re.I)), "Agreement")

        parties: list[str] = []
        m = re.search(r"between\s+(.+?)\s*(?:\(|,).*?\band\s+(.+?)\s*(?:\(|,)", head, re.I | re.S)
        if m:
            parties = [" ".join(p.split()).strip(" ,") for p in m.groups()]

        eff = re.search(r"(?:effective|dated|made|entered into)(?: as of| on)?\s+([A-Z][a-z]+ \d{1,2}, \d{4}|\d{1,2} [A-Z][a-z]+ \d{4}|\d{4}-\d{2}-\d{2})", head)
        law = re.search(r"governed by (?:and construed in accordance with )?the laws? of (?:the )?([A-Z][\w .'-]{2,50}?)(?:[,.;]|\s+without)", text)
        period = r"((?:[a-z]+(?:-[a-z]+)?\s*)?\(?\d{1,3}\)?\s*(?:days?|months?|years?))"
        term = (re.search(r"(?:initial term|term of this agreement)[^.]{0,60}?" + period, text, re.I)
                or re.search(r"this agreement[^.]{0,80}?continues? for\s+" + period, text, re.I))

        return ContractSummary(
            contract_type=ctype, parties=parties[:4],
            effective_date=eff.group(1) if eff else None,
            term=" ".join(term.group(1).split()) if term else None,
            governing_law=law.group(1).strip() if law else None,
        )

    def answer(self, question: str, context: list[Clause]) -> Answer:
        """Extractive answer: the best-matching sentence(s) from the retrieved clauses."""
        q_raw = _tokens(question)
        q = _tokens(expand_query(question))
        best: tuple[float, Clause | None, list[str]] = (0.0, None, [])
        for rank, c in enumerate(context):
            body = _HEADING_PREFIX.sub("", c.text, count=1)
            sents = [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(\"])", body) if len(s.split()) > 3]
            for i, sent in enumerate(sents):
                t = _tokens(sent)
                # original words count double; expanded synonyms count once
                score = (2 * len(q_raw & t) + len((q - q_raw) & t)) / (2 * (len(q_raw) or 1)) - 0.05 * rank
                if score > best[0]:
                    best = (score, c, sents[i:i + 2] if len(sent) < 120 and i + 1 < len(sents) else [sent])
        score, clause, picked = best
        if clause is None or score < 0.2:
            return Answer(question=question, answer="I could not find this in the contract.", citations=[], grounded=False)
        quote = " ".join(" ".join(picked).split())
        return Answer(
            question=question,
            answer=f'Clause "{clause.heading}" says: "{quote}"',
            citations=[Citation(clause_id=clause.id, heading=clause.heading, excerpt=clause.text[:300])],
            grounded=True,
        )

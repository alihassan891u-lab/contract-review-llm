"""Deterministic playbook engine.

Rules are data (YAML), not code, so a lawyer can change positions without
touching Python. The engine is used on its own in offline mode and as a
guard-rail alongside the LLM: rule hits are never dropped because a model
disagreed, which keeps the review auditable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from .schemas import Clause, ClauseLabel, Finding, RiskLevel
from .taxonomy import BY_KEY

_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "eighteen": 18, "twenty": 20,
    "twenty-four": 24, "thirty": 30, "thirty-six": 36, "forty-five": 45, "sixty": 60, "ninety": 90,
}
_UNIT = r"\s*(?:calendar\s+|business\s+|working\s+)?(day|month|year)s?\b"
# "thirty (30) days" -> trust the digits in brackets
_DUR_PAREN = re.compile(r"\(\s*(\d{1,4})\s*\)" + _UNIT, re.I)
# "30 days" (but not the "(30) days" already handled above)
_DUR_DIGIT = re.compile(r"(?<![\(\d])\b(\d{1,4})" + _UNIT, re.I)
# "thirty days" with no digits
_DUR_WORD = re.compile(r"\b(" + "|".join(sorted(_NUM_WORDS, key=len, reverse=True)) + r")" + _UNIT, re.I)
_NET = re.compile(r"\bnet\s?(\d{1,3})\b", re.I)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", re.I)
_UNIT_DAYS = {"day": 1, "month": 30, "year": 365}


def durations_in_days(text: str) -> list[int]:
    """Every time period mentioned in the text, converted to days."""
    out = [int(m.group(1)) * _UNIT_DAYS[m.group(2).lower()] for m in _DUR_PAREN.finditer(text)]
    out += [int(m.group(1)) * _UNIT_DAYS[m.group(2).lower()] for m in _DUR_DIGIT.finditer(text)]
    out += [_NUM_WORDS[m.group(1).lower()] * _UNIT_DAYS[m.group(2).lower()] for m in _DUR_WORD.finditer(text)]
    out += [int(m.group(1)) for m in _NET.finditer(text)]
    return out


def percents_in(text: str) -> list[float]:
    return [float(m.group(1)) for m in _PERCENT.finditer(text)]


def _cmp(value: float, cond: dict[str, float]) -> bool:
    if "gt" in cond and not value > cond["gt"]:
        return False
    if "lt" in cond and not value < cond["lt"]:
        return False
    return True


@dataclass
class Rule:
    id: str
    title: str
    applies_to: list[str]
    risk: RiskLevel
    explanation: str
    redline: Optional[str] = None
    when: dict[str, Any] = field(default_factory=dict)

    def matches(self, text: str) -> bool:
        w = self.when
        if "any_regex" in w and not any(re.search(p, text, re.I | re.S) for p in w["any_regex"]):
            return False
        if "all_regex" in w and not all(re.search(p, text, re.I | re.S) for p in w["all_regex"]):
            return False
        if "none_regex" in w and any(re.search(p, text, re.I | re.S) for p in w["none_regex"]):
            return False
        for key, extract in (("duration", durations_in_days), ("percent", percents_in)):
            if key in w:
                vals = extract(text)
                pick = min if w[key].get("pick") == "min" else max
                if not vals or not _cmp(pick(vals), w[key]):
                    return False
        return True


@dataclass
class RequiredClause:
    type: str
    risk: RiskLevel
    why: str
    skip_for: list[str] = field(default_factory=list)

    def applies(self, contract_type: str) -> bool:
        ct = contract_type.lower()
        return not any(s.lower() in ct for s in self.skip_for)


@dataclass
class Playbook:
    name: str
    rules: list[Rule]
    required: list[RequiredClause]
    preferred: dict[str, list[str]]

    # ------------------------------------------------------------------ loading
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Playbook":
        rules = [
            Rule(
                id=r["id"], title=r["title"], applies_to=list(r["applies_to"]), risk=RiskLevel(r["risk"]),
                explanation=r["explanation"], redline=r.get("redline"), when=r.get("when", {}),
            )
            for r in data.get("rules", [])
        ]
        for r in rules:
            unknown = [t for t in r.applies_to if t not in BY_KEY]
            if unknown:
                raise ValueError(f"Rule {r.id} references unknown clause types: {unknown}")
        required = [RequiredClause(c["type"], RiskLevel(c["risk"]), c["why"], list(c.get("skip_for", [])))
                    for c in data.get("required_clauses", [])]
        for req in required:
            if req.type not in BY_KEY:
                raise ValueError(f"Required clause references unknown clause type: {req.type}")
        return cls(name=data.get("name", "custom"), rules=rules, required=required, preferred=data.get("preferred", {}))

    @classmethod
    def load(cls, path: Union[str, Path, None] = None) -> "Playbook":
        if path is None:
            text = resources.files("contractlens.playbooks").joinpath("default.yaml").read_text(encoding="utf-8")
        else:
            text = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(yaml.safe_load(text))

    # --------------------------------------------------------------- evaluation
    def evaluate(self, clauses: list[Clause], labels: list[ClauseLabel],
                 contract_type: str = "") -> tuple[list[Finding], list[str]]:
        by_id = {c.id: c for c in clauses}
        types_of: dict[str, set[str]] = {}
        for lab in labels:
            types_of.setdefault(lab.clause_id, set()).add(lab.clause_type)

        findings: list[Finding] = []
        seen: set[tuple[str, str]] = set()
        for cid, types in types_of.items():
            clause = by_id[cid]
            for rule in self.rules:
                hit_type = next((t for t in rule.applies_to if t in types), None)
                if not hit_type or (rule.id, cid) in seen:
                    continue
                if rule.matches(clause.text):
                    seen.add((rule.id, cid))
                    findings.append(
                        Finding(
                            rule_id=rule.id, title=rule.title, risk=rule.risk, clause_id=cid, clause_type=hit_type,
                            evidence=_evidence(clause.text, rule), explanation=rule.explanation,
                            suggested_redline=rule.redline, source="rules",
                        )
                    )

        findings += self._governing_law_check(clauses, types_of)

        present = {t for ts in types_of.values() for t in ts}
        missing: list[str] = []
        for req in self.required:
            if req.applies(contract_type) and req.type not in present:
                missing.append(req.type)
                findings.append(
                    Finding(
                        rule_id=f"MISSING-{req.type}", title=f"Missing clause: {BY_KEY[req.type].label}",
                        risk=req.risk, clause_id=None, clause_type=req.type, explanation=req.why, source="rules",
                    )
                )
        return findings, missing

    def _governing_law_check(self, clauses: list[Clause], types_of: dict[str, set[str]]) -> list[Finding]:
        preferred = self.preferred.get("governing_law") or []
        if not preferred:
            return []
        out = []
        for c in clauses:
            if "governing_law" not in types_of.get(c.id, set()):
                continue
            m = re.search(r"laws? of (?:the )?([A-Z][\w .,'-]{2,60}?)(?:[,.;]|\s+(?:without|and|excluding))", c.text)
            if m and not any(p.lower() in c.text.lower() for p in preferred):
                out.append(
                    Finding(
                        rule_id="GL-001", title="Governing law not on preferred list", risk=RiskLevel.LOW,
                        clause_id=c.id, clause_type="governing_law", evidence=m.group(0).strip(" ,.;"),
                        explanation=f"Governed by the laws of {m.group(1).strip()}; preferred: {', '.join(preferred)}.",
                        suggested_redline=f"Propose the laws of {preferred[0]}.", source="rules",
                    )
                )
        return out


def _evidence(text: str, rule: Rule, width: int = 220) -> str:
    """Return the sentence-sized excerpt around the first regex hit."""
    for p in rule.when.get("any_regex", []) + rule.when.get("all_regex", []):
        m = re.search(p, text, re.I | re.S)
        if m and p != ".":
            # start at the sentence containing the hit (or a word boundary if the sentence is long)
            sent_start = max(text.rfind(". ", 0, m.start()), text.rfind("\n", 0, m.start()))
            s = sent_start + 2 if sent_start != -1 and m.start() - sent_start <= width else max(0, m.start() - width // 2)
            if s and not text[s - 1].isspace():
                nxt = text.find(" ", s)
                s = nxt + 1 if 0 <= nxt < m.start() else s
            e = min(len(text), m.end() + width // 2)
            while e < len(text) and not text[e - 1].isspace() and e - m.end() < width:
                e += 1
            return ("…" if s else "") + " ".join(text[s:e].split()) + ("…" if e < len(text) else "")
    return " ".join(text[:width].split()) + ("…" if len(text) > width else "")

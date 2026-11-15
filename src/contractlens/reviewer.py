"""End-to-end review pipeline.

    document -> clauses -> labels -> rule findings + LLM findings -> report

The rule engine always runs. LLM findings are added on top and must quote the
contract verbatim to survive (see ``LLMProvider.review``).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from .ingest import Document, load_bytes, load_file
from .llm import Provider, get_provider
from .playbook import Playbook
from .retrieval import ClauseIndex
from .schemas import Answer, Finding, ReviewReport, RiskLevel
from .segment import segment

log = logging.getLogger(__name__)

_RISK_WEIGHT = {RiskLevel.LOW: 3, RiskLevel.MEDIUM: 8, RiskLevel.HIGH: 15, RiskLevel.CRITICAL: 30}


def score_findings(findings: list[Finding]) -> tuple[int, RiskLevel]:
    """0-100 risk score with diminishing returns, plus an overall level."""
    raw = sum(_RISK_WEIGHT[f.risk] for f in findings)
    score = round(100 * (1 - 0.985 ** raw))
    worst = max((f.risk for f in findings), key=lambda r: r.score, default=RiskLevel.LOW)
    if worst == RiskLevel.CRITICAL or score >= 75:
        level = RiskLevel.CRITICAL if worst == RiskLevel.CRITICAL else RiskLevel.HIGH
    elif worst == RiskLevel.HIGH or score >= 45:
        level = RiskLevel.HIGH
    elif score >= 20:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW
    return score, level


class ContractReviewer:
    def __init__(self, provider: Union[Provider, str, None] = None, playbook: Union[Playbook, str, Path, None] = None,
                 max_clause_chars: int = 2500):
        self.provider = provider if isinstance(provider, Provider) else get_provider(provider)
        self.playbook = playbook if isinstance(playbook, Playbook) else Playbook.load(playbook)
        self.max_clause_chars = max_clause_chars

    # ------------------------------------------------------------------ review
    def review_document(self, doc: Document) -> ReviewReport:
        clauses = segment(doc, max_chars=self.max_clause_chars)
        log.info("%s: %d clauses", doc.name, len(clauses))

        summary = self.provider.summarize(doc.text)
        labels = self.provider.classify(clauses)

        rule_findings, missing = self.playbook.evaluate(clauses, labels, summary.contract_type)
        llm_findings = self.provider.review(clauses, labels, self.playbook, rule_findings, summary.contract_type)
        findings = _dedupe(rule_findings + llm_findings)
        findings.sort(key=lambda f: (-f.risk.score, f.clause_id or "zzz"))

        score, level = score_findings(findings)
        return ReviewReport(
            document_name=doc.name, provider=self.provider.name, playbook=self.playbook.name, summary=summary,
            clauses=clauses, labels=labels, findings=findings, missing_clauses=missing,
            overall_risk=level, risk_score=score,
        )

    def review_file(self, path: Union[str, Path]) -> ReviewReport:
        return self.review_document(load_file(path))

    def review_bytes(self, data: bytes, filename: str) -> ReviewReport:
        return self.review_document(load_bytes(data, filename))

    def review_text(self, text: str, name: str = "contract.txt") -> ReviewReport:
        return self.review_document(load_bytes(text.encode(), name))

    # --------------------------------------------------------------------- Q&A
    def ask(self, report: ReviewReport, question: str, k: int = 4, index: Optional[ClauseIndex] = None) -> Answer:
        index = index or ClauseIndex(report.clauses)
        hits = [c for c, _ in index.search(question, k=k)]
        if not hits:
            return Answer(question=question, answer="I could not find this in the contract.", citations=[], grounded=False)
        return self.provider.answer(question, hits)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """Drop LLM findings that restate a rule finding on the same clause."""
    out: list[Finding] = []
    rule_titles = {(f.clause_id, f.title.lower()) for f in findings if f.source == "rules"}
    for f in findings:
        if f.source == "llm" and (f.clause_id, f.title.lower()) in rule_titles:
            continue
        out.append(f)
    return out

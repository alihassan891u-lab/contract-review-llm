"""Typed data models shared by every stage of the pipeline.

Every LLM response is parsed into these models, so a malformed answer fails
loudly instead of leaking bad data into the report.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def score(self) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


class Clause(BaseModel):
    """A contiguous chunk of the contract, usually one numbered section."""

    id: str = Field(..., description="Stable id, e.g. 'c007'")
    heading: Optional[str] = None
    text: str
    start_char: int
    end_char: int
    page: Optional[int] = None


class ClauseLabel(BaseModel):
    clause_id: str
    clause_type: str = Field(..., description="Taxonomy key, e.g. 'limitation_of_liability'")
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: Optional[str] = None


class Finding(BaseModel):
    """A risk or issue raised against a clause (or against the whole contract)."""

    rule_id: str
    title: str
    risk: RiskLevel
    clause_id: Optional[str] = Field(None, description="None for contract-level findings such as a missing clause")
    clause_type: Optional[str] = None
    evidence: Optional[str] = Field(None, description="Short excerpt from the contract supporting the finding")
    explanation: str
    suggested_redline: Optional[str] = None
    source: str = Field("rules", description="'rules' or 'llm'")


class ContractSummary(BaseModel):
    contract_type: str = "unknown"
    parties: list[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    term: Optional[str] = None
    governing_law: Optional[str] = None
    key_obligations: list[str] = Field(default_factory=list)


class ReviewReport(BaseModel):
    document_name: str
    provider: str
    playbook: str
    summary: ContractSummary
    clauses: list[Clause]
    labels: list[ClauseLabel]
    findings: list[Finding]
    missing_clauses: list[str]
    overall_risk: RiskLevel
    risk_score: int = Field(..., ge=0, le=100)

    def findings_by_risk(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {lvl.value: [] for lvl in RiskLevel}
        for f in self.findings:
            out[f.risk.value].append(f)
        return out


class Citation(BaseModel):
    clause_id: str
    heading: Optional[str] = None
    excerpt: str


class Answer(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    grounded: bool = Field(..., description="False when the contract does not contain the answer")

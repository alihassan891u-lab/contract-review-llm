import io

import pytest

from contractlens.ingest import load_bytes
from contractlens.playbook import Playbook, durations_in_days, percents_in
from contractlens.reviewer import score_findings
from contractlens.schemas import Finding, RiskLevel
from contractlens.segment import segment


# ---------------------------------------------------------------- parsing
@pytest.mark.parametrize("text,expected", [
    ("for twenty-four (24) months", [720]),
    ("one hundred twenty (120) days", [120]),
    ("net 45", [45]),
    ("within 2 years", [730]),
    ("thirty days", [30]),
    ("ten (10) business days", [10]),
])
def test_durations(text, expected):
    assert durations_in_days(text) == expected


def test_percents():
    assert percents_in("interest at 2.5% per month or 18 percent a year") == [2.5, 18.0]


def test_segment_numbered_sections(risky_path):
    doc = load_bytes(risky_path.read_bytes(), risky_path.name)
    clauses = segment(doc)
    heads = [c.heading for c in clauses]
    assert "Limitation of Liability" in heads and "Governing Law and Disputes" in heads
    assert len(clauses) == 16
    for c in clauses:  # offsets point back into the source text
        assert doc.text[c.start_char:c.end_char] == c.text


def test_segment_splits_long_clauses():
    body = "\n\n".join(f"7.{i} Sub-clause number {i}. " + "The party shall do things. " * 30 for i in range(1, 6))
    doc = load_bytes(f"7. Obligations\n{body}".encode(), "x.txt")
    clauses = segment(doc, max_chars=1200)
    assert len(clauses) > 1
    assert all(c.heading.startswith("Obligations") for c in clauses)


def test_docx_and_pdf_ingest(risky_path):
    docx = pytest.importorskip("docx")
    text = risky_path.read_text()
    d = docx.Document()
    for para in text.split("\n"):
        d.add_paragraph(para)
    buf = io.BytesIO()
    d.save(buf)
    assert "Limitation of Liability" in load_bytes(buf.getvalue(), "c.docx").text

    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for page in range(2):
        c.drawString(72, 720, f"{page + 1}. Section {page + 1}. Payment is due within thirty (30) days.")
        c.showPage()
    c.save()
    doc = load_bytes(buf.getvalue(), "c.pdf")
    assert doc.page_for(len(doc.text) - 1) == 2


def test_unsupported_type():
    with pytest.raises(ValueError):
        load_bytes(b"x", "contract.xls")


# ----------------------------------------------------------------- review
EXPECTED_RISKY = {
    "LOL-001", "LOL-002", "LOL-003", "IND-001", "IP-001", "NC-001", "REN-001", "REN-002", "PAY-001",
    "PAY-002", "PRC-001", "CONF-001", "WAR-001", "TFC-001", "DP-001", "ASG-001", "GL-001",
}


def test_risky_contract_catches_planted_issues(risky_report):
    got = {f.rule_id for f in risky_report.findings}
    missing = EXPECTED_RISKY - got
    assert not missing, f"missed: {missing}"
    assert risky_report.overall_risk == RiskLevel.CRITICAL
    assert risky_report.risk_score >= 80
    assert risky_report.findings[0].risk == RiskLevel.CRITICAL  # sorted worst first


def test_balanced_nda_is_clean(nda_report):
    assert nda_report.summary.contract_type == "Mutual NDA"
    assert nda_report.findings == []
    assert nda_report.overall_risk == RiskLevel.LOW


def test_summary_extraction(risky_report):
    s = risky_report.summary
    assert s.parties == ["Northwind Cloud Systems Ltd.", "Brightline Retail Inc."]
    assert s.effective_date == "March 1, 2026"
    assert s.governing_law == "Province of Ontario"
    assert "36" in (s.term or "")


def test_evidence_is_verbatim(risky_report):
    by_id = {c.id: c for c in risky_report.clauses}
    for f in risky_report.findings:
        if f.clause_id and f.evidence:
            snippet = f.evidence.strip("…")[:60]
            assert " ".join(snippet.split()) in " ".join(by_id[f.clause_id].text.split())


def test_custom_playbook_validation():
    with pytest.raises(ValueError):
        Playbook.from_dict({"rules": [{"id": "X", "title": "t", "applies_to": ["not_a_type"], "risk": "low",
                                       "explanation": "e"}]})


def test_score_monotonic():
    f = lambda r: Finding(rule_id="x", title="t", risk=r, explanation="e")  # noqa: E731
    assert score_findings([]) == (0, RiskLevel.LOW)
    s1, _ = score_findings([f(RiskLevel.MEDIUM)])
    s2, _ = score_findings([f(RiskLevel.MEDIUM)] * 3)
    assert s2 > s1
    assert score_findings([f(RiskLevel.CRITICAL)])[1] == RiskLevel.CRITICAL


# -------------------------------------------------------------------- Q&A
@pytest.mark.parametrize("question,clause_heading,needle", [
    ("Can they raise prices?", "Fees and Payment", "increase the fees"),
    ("How long does the confidentiality obligation last?", "Confidentiality", "one (1) year"),
    ("Where do we sue?", "Governing Law and Disputes", "Toronto"),
])
def test_ask_grounded(reviewer, risky_report, question, clause_heading, needle):
    ans = reviewer.ask(risky_report, question)
    assert ans.grounded
    assert ans.citations[0].heading == clause_heading
    assert needle in ans.answer


def test_ask_not_in_contract(reviewer, risky_report):
    ans = reviewer.ask(risky_report, "What is the capital of France?")
    assert not ans.grounded and ans.citations == []

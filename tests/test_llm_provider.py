"""Exercise the LLM code path with a scripted fake model (no network, no key)."""
import json

from contractlens import ContractReviewer
from contractlens.llm.base import LLMProvider, extract_json


class FakeLLM(LLMProvider):
    name = "fake"

    def __init__(self, script):
        super().__init__(model="fake-1", max_retries=1)
        self.script = script
        self.prompts = []

    def _complete(self, system, user):
        self.prompts.append(user)
        for key, reply in self.script:
            if key in user:
                return reply() if callable(reply) else reply
        return "{}"


def _classify_reply(user):
    import re

    ids = re.findall(r"^\[(c\d{3})\] (.*)$", user, re.M)
    labels = []
    for cid, head in ids:
        h = head.lower()
        t = ("limitation_of_liability" if "liability" in h else "payment" if "fee" in h else
             "confidentiality" if "confidential" in h else "governing_law" if "law" in h else
             "termination_for_cause" if "terminat" in h else "other")
        labels.append({"clause_id": cid, "clause_type": t, "confidence": 0.9})
    labels.append({"clause_id": "c999", "clause_type": "payment", "confidence": 1})  # unknown id: must be ignored
    return json.dumps({"labels": labels})


def test_extract_json_tolerates_fences_and_chatter():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": [1, 2]} hope that helps') == {"a": [1, 2]}


def test_llm_pipeline_with_guards(risky_path):
    holder = {}

    def classify():
        return _classify_reply(holder["fake"].prompts[-1])

    review_reply = json.dumps({"findings": [
        {"clause_id": "c008", "title": "Data loss excluded", "risk": "high",
         "evidence": "INCLUDING LOSS OF DATA", "explanation": "Provider is not liable for losing your data.",
         "suggested_redline": "Carve data loss out of the exclusion."},
        {"clause_id": "c008", "title": "Invented issue", "risk": "critical",
         "evidence": "Provider shall pay Customer one million dollars", "explanation": "hallucinated"},
    ]})
    fake = FakeLLM([
        ("Classify each contract clause", classify),
        ("Find additional material risks", review_reply),
        ("extract key facts", '{"contract_type": "SaaS Agreement", "parties": ["Northwind", "Brightline"], "governing_law": "Ontario"}'),
        ("Answer the question", '{"answer": "Up to 3 months of fees.", "citations": ["c008", "c999"], "grounded": true}'),
    ])
    holder["fake"] = fake

    rv = ContractReviewer(provider=fake)
    report = rv.review_file(risky_path)

    titles = {f.title for f in report.findings if f.source == "llm"}
    assert "Data loss excluded" in titles          # grounded quote kept
    assert "Invented issue" not in titles          # hallucinated quote dropped
    assert any(f.rule_id == "LOL-001" for f in report.findings)  # rules still run alongside the LLM
    assert report.summary.contract_type == "SaaS Agreement"
    assert {lab.clause_id for lab in report.labels} == {c.id for c in report.clauses}  # every clause labeled

    ans = rv.ask(report, "What is the liability cap?")
    assert ans.grounded and [c.clause_id for c in ans.citations] == ["c008"]  # unknown citation dropped


def test_llm_retries_on_bad_json(risky_path):
    replies = iter(["not json at all", '{"contract_type": "MSA"}'])
    fake = FakeLLM([("extract key facts", lambda: next(replies))])
    assert fake.summarize("text").contract_type == "MSA"
    assert fake.calls == 2

"""Run the CUAD evaluator on a tiny CUAD-format fixture built from a sample contract."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_eval():
    spec = importlib.util.spec_from_file_location("run_cuad_eval", ROOT / "eval" / "run_cuad_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cuad_eval_on_fixture(tmp_path, risky_path):
    text = risky_path.read_text()
    answers = {
        "Governing Law": "This Agreement shall be governed by the laws of the Province of Ontario",
        "Cap On Liability": "IN NO EVENT SHALL PROVIDER'S AGGREGATE LIABILITY",
        "Non-Compete": "shall not, directly or indirectly, engage any business that competes",
        "Audit Rights": None,  # not in the contract
    }
    qas = []
    for cat, ans in answers.items():
        qas.append({"id": f"SAMPLE__{cat}", "question": cat, "is_impossible": ans is None,
                    "answers": [] if ans is None else [{"text": ans, "answer_start": text.index(ans)}]})
    fixture = {"data": [{"title": "SAMPLE", "paragraphs": [{"context": text, "qas": qas}]}]}
    path = tmp_path / "cuad.json"
    path.write_text(json.dumps(fixture))

    ev = _load_eval()
    res = ev.evaluate(path, "offline")
    assert res["contracts"] == 1
    for k in ("governing_law", "limitation_of_liability", "non_compete"):
        assert res["per_category"][k]["clause"]["tp"] == 1, k
    assert res["per_category"]["audit_rights"]["contract"]["fp"] == 0
    assert "Clause-level micro F1" in ev.to_markdown(res)

"""Evaluate clause classification against CUAD (Contract Understanding Atticus Dataset).

CUAD: 510 real commercial contracts, 13k+ expert annotations across 41 clause
categories (Hendrycks et al., 2021, CC BY 4.0).

Get the data (SQuAD-format JSON):
    https://zenodo.org/records/4595826  ->  CUAD_v1.json
    or Hugging Face dataset "theatticusproject/cuad-qa"

Run:
    python eval/run_cuad_eval.py --cuad data/CUAD_v1.json --provider offline
    python eval/run_cuad_eval.py --cuad data/CUAD_v1.json --provider claude --limit 25

Metric: a (contract, clause, category) triple is a true positive when our
clause carries the category label AND overlaps a CUAD answer span. We report
micro and per-category precision / recall / F1, plus contract-level detection
("does this contract contain a Governing Law clause?").
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from contractlens.ingest import Document  # noqa: E402
from contractlens.llm import get_provider  # noqa: E402
from contractlens.segment import segment  # noqa: E402
from contractlens.taxonomy import TAXONOMY  # noqa: E402

CUAD_TO_KEY = {t.cuad_name: t.key for t in TAXONOMY if t.cuad_name}
CUAD_TO_KEY["No-Solicit Of Customers"] = "non_solicit"


def load_cuad(path: Path, limit: int | None):
    data = json.loads(path.read_text(encoding="utf-8"))["data"]
    for item in data[:limit]:
        para = item["paragraphs"][0]
        spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for qa in para["qas"]:
            cat = qa["id"].split("__")[-1]
            key = CUAD_TO_KEY.get(cat)
            if not key:
                continue
            for a in qa["answers"]:
                spans[key].append((a["answer_start"], a["answer_start"] + len(a["text"])))
        yield item["title"], para["context"], dict(spans)


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def evaluate(cuad_path: Path, provider_name: str, limit: int | None = None) -> dict:
    provider = get_provider(provider_name)
    keys = sorted(set(CUAD_TO_KEY.values()))
    clause_counts = {k: [0, 0, 0] for k in keys}  # tp, fp, fn
    doc_counts = {k: [0, 0, 0] for k in keys}
    n_docs, t0 = 0, time.time()

    for title, text, gold in load_cuad(cuad_path, limit):
        n_docs += 1
        # Segment the raw CUAD text; no normalisation so offsets line up with the gold spans
        clauses = segment(Document(name=title, text=text))
        labels = provider.classify(clauses)
        pred: dict[str, set[str]] = defaultdict(set)
        for lab in labels:
            pred[lab.clause_type].add(lab.clause_id)

        for k in keys:
            gold_ids = {c.id for c in clauses for (s, e) in gold.get(k, []) if c.start_char < e and s < c.end_char}
            p = pred.get(k, set())
            clause_counts[k][0] += len(p & gold_ids)
            clause_counts[k][1] += len(p - gold_ids)
            clause_counts[k][2] += len(gold_ids - p)
            has_gold, has_pred = bool(gold.get(k)), bool(p)
            doc_counts[k][0] += has_gold and has_pred
            doc_counts[k][1] += has_pred and not has_gold
            doc_counts[k][2] += has_gold and not has_pred
        print(f"\r{n_docs} contracts", end="", file=sys.stderr)
    print(file=sys.stderr)

    micro = [sum(v[i] for v in clause_counts.values()) for i in range(3)]
    micro_doc = [sum(v[i] for v in doc_counts.values()) for i in range(3)]
    return {
        "provider": provider_name, "contracts": n_docs, "seconds": round(time.time() - t0, 1),
        "clause_level_micro": prf(*micro), "contract_level_micro": prf(*micro_doc),
        "per_category": {k: {"clause": prf(*clause_counts[k]), "contract": prf(*doc_counts[k])} for k in keys},
    }


def to_markdown(res: dict) -> str:
    rows = ["| Category | Clause P | Clause R | Clause F1 | Contract F1 |", "|---|---:|---:|---:|---:|"]
    for k, v in sorted(res["per_category"].items(), key=lambda kv: -kv[1]["clause"]["f1"]):
        c, d = v["clause"], v["contract"]
        rows.append(f"| {k} | {c['precision']:.2f} | {c['recall']:.2f} | {c['f1']:.2f} | {d['f1']:.2f} |")
    m, md = res["clause_level_micro"], res["contract_level_micro"]
    head = (f"**Provider:** {res['provider']} · **Contracts:** {res['contracts']} · "
            f"**Clause-level micro F1:** {m['f1']:.3f} (P {m['precision']:.3f} / R {m['recall']:.3f}) · "
            f"**Contract-level micro F1:** {md['f1']:.3f}\n\n")
    return head + "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuad", type=Path, required=True, help="path to CUAD_v1.json")
    ap.add_argument("--provider", default="offline")
    ap.add_argument("--limit", type=int, default=None, help="only the first N contracts (keeps API costs down)")
    ap.add_argument("--out", type=Path, default=Path("eval/results"))
    a = ap.parse_args()

    res = evaluate(a.cuad, a.provider, a.limit)
    a.out.mkdir(parents=True, exist_ok=True)
    stem = f"cuad_{a.provider}_{res['contracts']}"
    (a.out / f"{stem}.json").write_text(json.dumps(res, indent=2))
    (a.out / f"{stem}.md").write_text(to_markdown(res))
    print(to_markdown(res))


if __name__ == "__main__":
    main()

"""Command-line interface.

    contractlens review samples/saas_msa_risky.txt --format html -o report.html
    contractlens ask samples/saas_msa_risky.txt "Can the provider raise prices?"
    contractlens review contract.pdf --provider claude --playbook my_playbook.yaml
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .llm import PROVIDERS
from .report import to_html, to_markdown
from .reviewer import ContractReviewer

_ICON = {"critical": "■", "high": "▲", "medium": "●", "low": "·"}


def _console(report) -> str:
    out = [f"{report.document_name}: {report.overall_risk.value.upper()} risk ({report.risk_score}/100), "
           f"{len(report.findings)} findings  [{report.summary.contract_type}]"]
    for f in report.findings:
        where = f.clause_id or "contract"
        out.append(f"  {_ICON[f.risk.value]} {f.risk.value:<8} {where:<8} {f.title}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="contractlens", description="LLM-assisted contract review")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("file", type=Path, help="PDF, DOCX or TXT contract")
    common.add_argument("--provider", choices=PROVIDERS, default=None, help="default: $CONTRACTLENS_PROVIDER or offline")
    common.add_argument("--model", default=None, help="override the provider's default model")
    common.add_argument("--playbook", type=Path, default=None, help="YAML playbook (default: built-in)")

    rv = sub.add_parser("review", parents=[common], help="review a contract")
    rv.add_argument("--format", choices=["console", "json", "markdown", "html"], default="console")
    rv.add_argument("-o", "--output", type=Path, default=None)
    rv.add_argument("--fail-on", choices=["low", "medium", "high", "critical"], default=None,
                    help="exit 2 if any finding is at or above this risk (useful in CI / batch jobs)")

    ak = sub.add_parser("ask", parents=[common], help="ask a question about a contract")
    ak.add_argument("question")

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    kw = {"model": a.model} if a.model else {}
    from .llm import get_provider

    reviewer = ContractReviewer(provider=get_provider(a.provider, **kw), playbook=a.playbook)
    report = reviewer.review_file(a.file)

    if a.cmd == "ask":
        ans = reviewer.ask(report, a.question)
        print(ans.answer)
        for c in ans.citations:
            print(f"  [{c.clause_id}] {c.heading}")
        return 0 if ans.grounded else 1

    rendered = {
        "console": lambda: _console(report),
        "json": lambda: report.model_dump_json(indent=2),
        "markdown": lambda: to_markdown(report),
        "html": lambda: to_html(report),
    }[a.format]()
    if a.output:
        a.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {a.output}  ({report.overall_risk.value} risk, {len(report.findings)} findings)")
    else:
        print(rendered)

    if a.fail_on:
        from .schemas import RiskLevel

        threshold = RiskLevel(a.fail_on).score
        if any(f.risk.score >= threshold for f in report.findings):
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

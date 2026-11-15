"""Render a ReviewReport as Markdown or a self-contained HTML page."""
from __future__ import annotations

from collections import Counter
from html import escape

from .schemas import ReviewReport, RiskLevel
from .taxonomy import BY_KEY

_COLORS = {"critical": "#b42318", "high": "#d9480f", "medium": "#b08800", "low": "#3b7d3b"}
_DISCLAIMER = ("Automated first-pass review. Not legal advice: have a qualified lawyer confirm "
               "every finding before relying on it.")


def _label(key: str | None) -> str:
    return BY_KEY[key].label if key in BY_KEY else (key or "Contract-level")


def to_markdown(r: ReviewReport) -> str:
    s = r.summary
    lines = [
        f"# Contract review: {r.document_name}",
        "",
        f"**Overall risk:** {r.overall_risk.value.upper()} ({r.risk_score}/100) · "
        f"**Findings:** {len(r.findings)} · **Provider:** {r.provider} · **Playbook:** {r.playbook}",
        "",
        "## Summary",
        f"- **Type:** {s.contract_type}",
        f"- **Parties:** {', '.join(s.parties) or 'not detected'}",
        f"- **Effective date:** {s.effective_date or 'not detected'}",
        f"- **Term:** {s.term or 'not detected'}",
        f"- **Governing law:** {s.governing_law or 'not detected'}",
    ]
    if s.key_obligations:
        lines += ["- **Key obligations:**", *[f"  - {o}" for o in s.key_obligations]]
    clause_by_id = {c.id: c for c in r.clauses}
    for level in (RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW):
        group = [f for f in r.findings if f.risk == level]
        if not group:
            continue
        lines += ["", f"## {level.value.capitalize()} risk ({len(group)})"]
        for f in group:
            where = clause_by_id[f.clause_id].heading if f.clause_id in clause_by_id else "Whole contract"
            lines += ["", f"### {f.title}", f"*{where} · {_label(f.clause_type)} · `{f.rule_id}` · {f.source}*", "",
                      f.explanation]
            if f.evidence:
                lines += ["", f"> {f.evidence}"]
            if f.suggested_redline:
                lines += ["", f"**Suggested redline:** {f.suggested_redline}"]
    lines += ["", "---", f"_{_DISCLAIMER}_", ""]
    return "\n".join(lines)


def to_html(r: ReviewReport) -> str:
    s = r.summary
    e = escape
    counts = Counter(f.risk.value for f in r.findings)
    clause_by_id = {c.id: c for c in r.clauses}
    types_of: dict[str, list[str]] = {}
    for lab in r.labels:
        types_of.setdefault(lab.clause_id, []).append(_label(lab.clause_type))
    flagged = Counter(f.clause_id for f in r.findings if f.clause_id)

    chips = "".join(
        f'<span class="chip" style="--c:{_COLORS[k]}">{counts.get(k, 0)} {k}</span>'
        for k in ("critical", "high", "medium", "low")
    )
    cards = []
    for f in r.findings:
        where = clause_by_id[f.clause_id].heading if f.clause_id in clause_by_id else "Whole contract"
        cards.append(f"""
<article class="finding" style="--c:{_COLORS[f.risk.value]}">
  <header><span class="badge">{e(f.risk.value)}</span><h3>{e(f.title)}</h3></header>
  <p class="meta">{e(where or '')} · {e(_label(f.clause_type))} · <code>{e(f.rule_id)}</code> · {e(f.source)}</p>
  <p>{e(f.explanation)}</p>
  {f'<blockquote>{e(f.evidence)}</blockquote>' if f.evidence else ''}
  {f'<p class="redline"><strong>Suggested redline:</strong> {e(f.suggested_redline)}</p>' if f.suggested_redline else ''}
</article>""")
    rows = "".join(
        f"<tr><td><code>{c.id}</code></td><td>{e(c.heading or '')}</td><td>{e(', '.join(types_of.get(c.id, [])))}</td>"
        f"<td>{'⚑ ' + str(flagged[c.id]) if flagged[c.id] else ''}</td></tr>"
        for c in r.clauses
    )
    gauge_color = _COLORS[r.overall_risk.value]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contract review · {e(r.document_name)}</title>
<style>
:root{{--ink:#1d2433;--muted:#5c667a;--line:#e3e6ec;--bg:#f7f8fa}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}}
main{{max-width:980px;margin:0 auto;padding:32px 20px 60px}}
h1{{font-size:26px;margin:0 0 4px}}h2{{font-size:18px;margin:32px 0 12px}}h3{{font-size:16px;margin:0}}
.top{{display:grid;grid-template-columns:1fr 180px;gap:20px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px}}
.gauge{{text-align:center}}.gauge b{{display:block;font-size:44px;color:{gauge_color};line-height:1}}
.gauge span{{text-transform:uppercase;letter-spacing:.08em;font-size:12px;color:{gauge_color};font-weight:700}}
dl{{display:grid;grid-template-columns:140px 1fr;gap:4px 12px;margin:12px 0 0}}dt{{color:var(--muted)}}dd{{margin:0}}
.chip{{display:inline-block;margin:10px 6px 0 0;padding:2px 10px;border-radius:99px;border:1px solid var(--c);color:var(--c);font-size:13px;font-weight:600}}
.finding{{background:#fff;border:1px solid var(--line);border-left:4px solid var(--c);border-radius:10px;padding:14px 18px;margin:0 0 12px}}
.finding header{{display:flex;gap:10px;align-items:center}}
.badge{{background:var(--c);color:#fff;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:2px 8px;border-radius:6px;font-weight:700}}
.meta{{color:var(--muted);font-size:13px;margin:4px 0 8px}}
blockquote{{margin:8px 0;padding:8px 12px;background:var(--bg);border-left:3px solid var(--line);font-family:ui-serif,Georgia,serif;color:#333}}
.redline{{background:#eef6ee;border-radius:8px;padding:8px 12px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}}
td{{padding:7px 10px;border-top:1px solid var(--line);font-size:14px}}code{{font-size:12px;color:var(--muted)}}
footer{{margin-top:36px;color:var(--muted);font-size:13px}}
@media(max-width:640px){{.top{{grid-template-columns:1fr}}dl{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section class="top">
  <div>
    <h1>{e(r.document_name)}</h1>
    <div class="meta">Provider: {e(r.provider)} · Playbook: {e(r.playbook)} · {len(r.clauses)} clauses</div>
    <dl>
      <dt>Type</dt><dd>{e(s.contract_type)}</dd>
      <dt>Parties</dt><dd>{e(', '.join(s.parties) or 'not detected')}</dd>
      <dt>Effective date</dt><dd>{e(s.effective_date or 'not detected')}</dd>
      <dt>Term</dt><dd>{e(s.term or 'not detected')}</dd>
      <dt>Governing law</dt><dd>{e(s.governing_law or 'not detected')}</dd>
    </dl>
    {chips}
  </div>
  <div class="gauge"><b>{r.risk_score}</b><span>{e(r.overall_risk.value)} risk</span></div>
</section>
<h2>Findings ({len(r.findings)})</h2>
{''.join(cards) or '<p>No issues found against this playbook.</p>'}
<h2>Clause map</h2>
<table>{rows}</table>
<footer>{e(_DISCLAIMER)} Generated by ContractLens.</footer>
</main></body></html>"""

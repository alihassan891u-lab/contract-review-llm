"""Streamlit demo UI.

    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from contractlens import ContractReviewer
from contractlens.llm import PROVIDERS, get_provider
from contractlens.report import to_html, to_markdown
from contractlens.retrieval import ClauseIndex
from contractlens.taxonomy import BY_KEY

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
COLORS = {"critical": "#b42318", "high": "#d9480f", "medium": "#b08800", "low": "#3b7d3b"}

st.set_page_config(page_title="ContractLens · AI Contract Review", page_icon="⚖️", layout="wide")


@st.cache_resource
def reviewer_for(provider: str, model: str | None) -> ContractReviewer:
    kw = {"model": model} if model else {}
    return ContractReviewer(provider=get_provider(provider, **kw))


with st.sidebar:
    st.title("⚖️ ContractLens")
    st.caption("Clause-level risk review with suggested redlines, plus Q&A with citations.")
    default = os.getenv("CONTRACTLENS_PROVIDER", "offline")
    provider = st.selectbox("Model provider", PROVIDERS, index=PROVIDERS.index(default) if default in PROVIDERS else 0)
    model = st.text_input("Model (optional)", placeholder="provider default")
    if provider == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = st.text_input("Anthropic API key", type="password")
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.text_input("OpenAI API key", type="password")
    st.divider()
    sample = st.selectbox("…or try a sample", ["—"] + sorted(p.name for p in SAMPLES.glob("*.txt")))
    st.caption("Not legal advice. Confirm findings with a qualified lawyer.")

upload = st.file_uploader("Upload a contract (PDF, DOCX, TXT)", type=["pdf", "docx", "txt", "md"])

source = None
if upload is not None:
    source = (upload.getvalue(), upload.name)
elif sample != "—":
    source = ((SAMPLES / sample).read_bytes(), sample)

if source is None:
    st.info("Upload a contract or pick a sample from the sidebar to start.")
    st.stop()

key = (source[1], len(source[0]), provider, model)
if st.session_state.get("key") != key:
    with st.spinner("Reviewing contract…"):
        try:
            rv = reviewer_for(provider, model or None)
            report = rv.review_bytes(*source)
        except Exception as e:  # show the error in the UI instead of a stack trace
            st.error(f"Review failed: {e}")
            st.stop()
    st.session_state.update(key=key, report=report, index=ClauseIndex(report.clauses), chat=[])

report = st.session_state["report"]
rv = reviewer_for(provider, model or None)
s = report.summary

c1, c2, c3, c4 = st.columns(4)
c1.metric("Risk score", f"{report.risk_score}/100", report.overall_risk.value.upper(), delta_color="off")
c2.metric("Findings", len(report.findings))
c3.metric("Clauses", len(report.clauses))
c4.metric("Missing clauses", len(report.missing_clauses))

st.markdown(f"**{s.contract_type}** · {' ↔ '.join(s.parties) or 'parties not detected'} · "
            f"effective {s.effective_date or '—'} · term {s.term or '—'} · law: {s.governing_law or '—'}")

tab_f, tab_q, tab_c, tab_x = st.tabs(["Findings", "Ask the contract", "Clauses", "Export"])

with tab_f:
    levels = st.multiselect("Show risk levels", list(COLORS), default=list(COLORS))
    clause_by_id = {c.id: c for c in report.clauses}
    for f in report.findings:
        if f.risk.value not in levels:
            continue
        where = clause_by_id[f.clause_id].heading if f.clause_id in clause_by_id else "Whole contract"
        with st.container(border=True):
            st.markdown(f"<span style='background:{COLORS[f.risk.value]};color:#fff;padding:2px 8px;border-radius:6px;"
                        f"font-size:12px;font-weight:700'>{f.risk.value.upper()}</span> &nbsp; **{f.title}**",
                        unsafe_allow_html=True)
            st.caption(f"{where} · {BY_KEY.get(f.clause_type).label if f.clause_type in BY_KEY else '—'} · {f.rule_id} · {f.source}")
            st.write(f.explanation)
            if f.evidence:
                st.markdown(f"> {f.evidence}")
            if f.suggested_redline:
                st.success(f"**Suggested redline:** {f.suggested_redline}")

with tab_q:
    for role, msg in st.session_state["chat"]:
        st.chat_message(role).markdown(msg)
    q = st.chat_input("e.g. Can the provider raise prices? How long does confidentiality last?")
    if q:
        st.chat_message("user").markdown(q)
        ans = rv.ask(report, q, index=st.session_state["index"])
        cites = "\n".join(f"- `{c.clause_id}` {c.heading}" for c in ans.citations)
        msg = ans.answer + (f"\n\n**Sources**\n{cites}" if cites else "")
        st.chat_message("assistant").markdown(msg)
        st.session_state["chat"] += [("user", q), ("assistant", msg)]

with tab_c:
    types_of: dict[str, list[str]] = {}
    for lab in report.labels:
        types_of.setdefault(lab.clause_id, []).append(f"{BY_KEY[lab.clause_type].label} ({lab.confidence:.0%})")
    for c in report.clauses:
        with st.expander(f"{c.id} · {c.heading} — {', '.join(types_of.get(c.id, []))}"):
            st.text(c.text)

with tab_x:
    stem = Path(report.document_name).stem
    st.download_button("Download HTML report", to_html(report), f"{stem}_review.html", "text/html")
    st.download_button("Download Markdown", to_markdown(report), f"{stem}_review.md", "text/markdown")
    st.download_button("Download JSON", report.model_dump_json(indent=2), f"{stem}_review.json", "application/json")

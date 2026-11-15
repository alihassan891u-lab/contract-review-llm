"""Split contract text into clauses.

Strategy:
1. Split on top-level headings ("5. Limitation of Liability", "ARTICLE IV",
   "Section 12", short ALL-CAPS lines).
2. Any clause longer than ``max_chars`` is split again on sub-section numbers
   ("5.2") and then on blank lines, keeping the parent heading so each chunk
   still carries context for the LLM and for retrieval.
"""
from __future__ import annotations

import re
from typing import Optional

from .ingest import Document
from .schemas import Clause

_TOP_NUMBERED = re.compile(r"^\s*(\d{1,2})\.?\s+(?=[A-Z])")
_SECTION_WORD = re.compile(r"^\s*(?:section|article|clause)\s+([\dIVXLC]+)\b[\.:]?\s*", re.I)
_ALL_CAPS = re.compile(r"^\s*[A-Z][A-Z0-9 \-&,'/()]{3,70}\s*$")
_SUB_NUMBERED = re.compile(r"^\s*\d{1,2}\.\d{1,2}(?:\.\d{1,2})?\.?\s+")


def _heading_from_line(line: str) -> str:
    line = line.strip()
    m = _SECTION_WORD.match(line) or _TOP_NUMBERED.match(line)
    rest = line[m.end():] if m else line
    # "Limitation of Liability. In no event ..." -> "Limitation of Liability"
    head = re.split(r"(?<=[a-z\)])[\.:]\s", rest, maxsplit=1)[0]
    head = head.rstrip(".:").strip()
    if len(head) > 80:
        head = " ".join(head.split()[:8]) + "…"
    return head or line[:60]


def _is_heading(line: str) -> bool:
    if not line.strip():
        return False
    if _SECTION_WORD.match(line) or _TOP_NUMBERED.match(line):
        return True
    return bool(_ALL_CAPS.match(line)) and len(line.split()) <= 10


def _line_spans(text: str) -> list[tuple[int, int, str]]:
    spans, pos = [], 0
    for line in text.split("\n"):
        spans.append((pos, pos + len(line), line))
        pos += len(line) + 1
    return spans


def _split_long(text: str, start: int, max_chars: int) -> list[tuple[int, int]]:
    """Return (start, end) offsets of sub-chunks for an oversized clause."""
    spans = _line_spans(text)
    cut_points = [s for s, _, line in spans if _SUB_NUMBERED.match(line)]
    if len(cut_points) < 2:
        cut_points = [s for i, (s, _, line) in enumerate(spans) if i > 0 and not spans[i - 1][2].strip() and line.strip()]
    cut_points = sorted({0, *cut_points})

    chunks: list[tuple[int, int]] = []
    cur_start = 0
    for cp in cut_points[1:] + [len(text)]:
        if cp - cur_start >= max_chars or cp == len(text):
            chunks.append((cur_start, cp))
            cur_start = cp
    # Merge a tiny tail into its predecessor
    if len(chunks) > 1 and chunks[-1][1] - chunks[-1][0] < 200:
        prev = chunks.pop(-2)
        last = chunks.pop()
        chunks.append((prev[0], last[1]))
    return [(start + a, start + b) for a, b in chunks if text[a:b].strip()]


def segment(doc: Document, max_chars: int = 2500) -> list[Clause]:
    text = doc.text
    spans = _line_spans(text)

    boundaries: list[tuple[int, Optional[str]]] = []
    for s, _, line in spans:
        if _is_heading(line):
            boundaries.append((s, _heading_from_line(line)))

    if not boundaries or boundaries[0][0] > 0:
        boundaries.insert(0, (0, "Preamble"))

    raw: list[tuple[int, int, Optional[str]]] = []
    for i, (s, head) in enumerate(boundaries):
        e = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        # Stand-alone ALL-CAPS title lines with no body get folded into the next clause
        body = text[s:e].strip()
        if not body:
            continue
        raw.append((s, e, head))

    # Fold heading-only fragments (e.g. a title line) forward
    merged: list[tuple[int, int, Optional[str]]] = []
    carry: Optional[tuple[int, Optional[str]]] = None
    for s, e, head in raw:
        if carry is not None:
            s, head = carry[0], (carry[1] if head in (None, "Preamble") else head)
            carry = None
        if len(text[s:e].strip()) < 40 and "\n" not in text[s:e].strip():
            carry = (s, head)
            continue
        merged.append((s, e, head))
    if carry is not None:
        if merged:
            s0, _, h0 = merged.pop()
            merged.append((s0, len(text), h0))
        else:
            merged.append((carry[0], len(text), carry[1]))

    clauses: list[Clause] = []
    for s, e, head in merged:
        pieces = [(s, e)] if e - s <= max_chars else _split_long(text[s:e], s, max_chars)
        for j, (ps, pe) in enumerate(pieces):
            chunk = text[ps:pe].strip()
            if not chunk:
                continue
            lead = len(text[ps:pe]) - len(text[ps:pe].lstrip())
            h = head if len(pieces) == 1 else f"{head} (part {j + 1})"
            clauses.append(
                Clause(
                    id=f"c{len(clauses):03d}",
                    heading=h,
                    text=chunk,
                    start_char=ps + lead,
                    end_char=ps + lead + len(chunk),
                    page=doc.page_for(ps + lead),
                )
            )
    return clauses

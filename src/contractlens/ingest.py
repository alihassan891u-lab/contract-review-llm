"""Load contracts from PDF, DOCX or plain text into a single normalised string.

Page boundaries are kept as character offsets so every clause and citation can
point back to the page it came from.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


@dataclass
class Document:
    name: str
    text: str
    page_starts: list[int] = field(default_factory=lambda: [0])

    def page_for(self, char_offset: int) -> Optional[int]:
        """1-based page number containing ``char_offset``."""
        if len(self.page_starts) <= 1:
            return None
        page = 1
        for i, start in enumerate(self.page_starts):
            if char_offset >= start:
                page = i + 1
            else:
                break
        return page


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    # Re-join words hyphenated across PDF line breaks: "termi-\nnation" -> "termination"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _from_pdf(data: bytes) -> list[str]:
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [(p.extract_text() or "") for p in pdf.pages]
    except ImportError:  # pragma: no cover - fallback path
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return [(p.extract_text() or "") for p in reader.pages]


def _from_docx(data: bytes) -> str:
    import docx

    d = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in d.paragraphs)


def load_bytes(data: bytes, filename: str) -> Document:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported file type '{suffix}'. Use one of: {sorted(SUPPORTED)}")

    if suffix == ".pdf":
        pages = [_normalise(p) for p in _from_pdf(data)]
        starts, chunks, pos = [], [], 0
        for p in pages:
            starts.append(pos)
            chunks.append(p)
            pos += len(p) + 2  # account for the "\n\n" joiner
        text = "\n\n".join(chunks)
        if not text.strip():
            raise ValueError("No extractable text found. The PDF may be scanned; run OCR first.")
        return Document(name=filename, text=text, page_starts=starts)

    if suffix == ".docx":
        return Document(name=filename, text=_normalise(_from_docx(data)))

    return Document(name=filename, text=_normalise(data.decode("utf-8", errors="replace")))


def load_file(path: Union[str, Path]) -> Document:
    path = Path(path)
    return load_bytes(path.read_bytes(), path.name)

"""REST API.

    uvicorn contractlens.api:app --reload
    open http://localhost:8000/docs
"""
from __future__ import annotations

import os
import uuid
from collections import OrderedDict
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import __version__
from .llm import PROVIDERS, get_provider
from .report import to_html, to_markdown
from .retrieval import ClauseIndex
from .reviewer import ContractReviewer
from .schemas import Answer, ReviewReport

MAX_BYTES = int(os.getenv("CONTRACTLENS_MAX_MB", "10")) * 1024 * 1024
CACHE_SIZE = int(os.getenv("CONTRACTLENS_CACHE", "50"))

app = FastAPI(
    title="ContractLens API",
    version=__version__,
    description="Upload a contract, get clause-level risk findings with suggested redlines, then ask questions with citations.",
)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])

_reviewers: dict[str, ContractReviewer] = {}
_store: "OrderedDict[str, tuple[ReviewReport, ClauseIndex, str]]" = OrderedDict()


def _reviewer(provider: Optional[str]) -> ContractReviewer:
    key = (provider or os.getenv("CONTRACTLENS_PROVIDER") or "offline").lower()
    if key not in PROVIDERS:
        raise HTTPException(400, f"provider must be one of {PROVIDERS}")
    if key not in _reviewers:
        try:
            _reviewers[key] = ContractReviewer(provider=get_provider(key), playbook=os.getenv("CONTRACTLENS_PLAYBOOK"))
        except RuntimeError as e:
            raise HTTPException(400, str(e)) from e
    return _reviewers[key]


def _save(report: ReviewReport, provider_key: str) -> str:
    rid = uuid.uuid4().hex[:12]
    _store[rid] = (report, ClauseIndex(report.clauses), provider_key)
    while len(_store) > CACHE_SIZE:
        _store.popitem(last=False)
    return rid


def _get(rid: str):
    if rid not in _store:
        raise HTTPException(404, "Unknown or expired review id")
    return _store[rid]


class ReviewResponse(BaseModel):
    review_id: str
    report: ReviewReport


class TextIn(BaseModel):
    text: str = Field(..., min_length=50)
    name: str = "pasted_contract.txt"
    provider: Optional[str] = None


class Question(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    k: int = Field(4, ge=1, le=10)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "providers": list(PROVIDERS)}


@app.post("/review", response_model=ReviewResponse)
async def review_upload(file: UploadFile = File(...), provider: Optional[str] = Form(None)):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"File larger than {MAX_BYTES // (1024 * 1024)} MB")
    rv = _reviewer(provider)
    try:
        report = rv.review_bytes(data, file.filename or "upload.txt")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return ReviewResponse(review_id=_save(report, rv.provider.name), report=report)


@app.post("/review/text", response_model=ReviewResponse)
def review_text(body: TextIn):
    rv = _reviewer(body.provider)
    report = rv.review_text(body.text, body.name)
    return ReviewResponse(review_id=_save(report, rv.provider.name), report=report)


@app.post("/reviews/{rid}/ask", response_model=Answer)
def ask(rid: str, q: Question):
    report, index, provider_key = _get(rid)
    return _reviewer(provider_key).ask(report, q.question, k=q.k, index=index)


@app.get("/reviews/{rid}", response_model=ReviewReport)
def get_review(rid: str):
    return _get(rid)[0]


@app.get("/reviews/{rid}/report.html", response_class=HTMLResponse)
def report_html(rid: str):
    return to_html(_get(rid)[0])


@app.get("/reviews/{rid}/report.md", response_class=PlainTextResponse)
def report_md(rid: str):
    return to_markdown(_get(rid)[0])

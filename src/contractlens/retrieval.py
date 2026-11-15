"""Clause retrieval for contract Q&A (the "R" in RAG).

Default: TF-IDF over clause text + heading (fast, no downloads, good on legal
vocabulary). If ``sentence-transformers`` is installed and
CONTRACTLENS_EMBEDDINGS=1, dense scores are blended in (hybrid search).
"""
from __future__ import annotations

import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .schemas import Clause

# Plain-English -> contract vocabulary. Users ask "can they raise prices?";
# contracts say "may increase the fees".
SYNONYMS = {
    "price": "fees fee pricing rates", "prices": "fees fee pricing rates", "raise": "increase adjust",
    "cost": "fees", "pay": "payment invoice fees", "paid": "payment invoice",
    "cap": "exceed aggregate liability limit", "limit": "exceed aggregate liability",
    "last": "survive period term years", "long": "period term years months survive",
    "end": "terminate termination expire", "cancel": "terminate termination non-renewal",
    "quit": "terminate termination", "renew": "renewal automatically", "owns": "title interest assigns ownership",
    "own": "title interest assigns ownership", "ip": "intellectual property", "sue": "jurisdiction courts dispute arbitration",
    "court": "jurisdiction dispute", "law": "governed laws", "secret": "confidential confidentiality",
    "privacy": "personal data protection security", "breach": "material breach security incident",
    "compete": "non-compete competes", "hire": "solicit hire personnel", "transfer": "assign assignment",
    "refund": "refund pro-rata prepaid", "warranty": "warrants warranties as is", "notice": "notice written",
    "early": "terminate convenience", "they": "provider", "we": "customer",
}


def expand_query(query: str) -> str:
    words = query.lower().split()
    extra = [SYNONYMS[w.strip("?.,!")] for w in words if w.strip("?.,!") in SYNONYMS]
    return " ".join([query, *extra])


class ClauseIndex:
    def __init__(self, clauses: list[Clause], dense_weight: float = 0.5):
        if not clauses:
            raise ValueError("Cannot index an empty contract")
        self.clauses = clauses
        docs = [f"{c.heading or ''} {c.heading or ''} {c.text}" for c in clauses]  # heading counted twice
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english", min_df=1)
        self.matrix = self.vec.fit_transform(docs)
        self.dense_weight = dense_weight
        self._encoder = None
        self._dense = None
        if os.getenv("CONTRACTLENS_EMBEDDINGS") == "1":
            try:
                from sentence_transformers import SentenceTransformer

                self._encoder = SentenceTransformer(os.getenv("CONTRACTLENS_EMBED_MODEL", "BAAI/bge-small-en-v1.5"))
                self._dense = self._encoder.encode(docs, normalize_embeddings=True)
            except ImportError:  # pragma: no cover
                self._encoder = None

    def search(self, query: str, k: int = 4) -> list[tuple[Clause, float]]:
        sparse = (self.matrix @ self.vec.transform([expand_query(query)]).T).toarray().ravel()
        scores = sparse
        if self._encoder is not None:
            q = self._encoder.encode([query], normalize_embeddings=True)[0]
            dense = self._dense @ q
            scores = (1 - self.dense_weight) * sparse + self.dense_weight * dense
        order = np.argsort(-scores)[:k]
        return [(self.clauses[i], float(scores[i])) for i in order if scores[i] > 0]

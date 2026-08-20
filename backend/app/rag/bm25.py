"""自实现 BM25 检索（无第三方依赖）。

基于经典 BM25 算法：
  score(D,Q) = Σ IDF(qi) * (f(qi,D) * (k1+1)) / (f(qi,D) + k1 * (1 - b + b * |D|/avgdl))
"""
from __future__ import annotations

import math
import re
from collections import Counter

from app.rag.vectorstore import RetrievedChunk


def _tokenize(text: str) -> list[str]:
    """轻量分词：按非字母数字切分，小写化。"""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Index:
    """BM25 倒排索引。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._docs: list[str] = []
        self._doc_ids: list[str] = []
        self._doc_metadata: list[dict] = []
        self._doc_tokens: list[Counter] = []
        self._avgdl = 0.0
        self._idf: dict[str, float] = {}

    def index(self, docs: list[dict]) -> None:
        """docs: [{id, text, metadata}]"""
        self._docs = []
        self._doc_ids = []
        self._doc_metadata = []
        self._doc_tokens = []
        for d in docs:
            self._docs.append(d["text"])
            self._doc_ids.append(d["id"])
            self._doc_metadata.append(d.get("metadata", {}))
            self._doc_tokens.append(Counter(_tokenize(d["text"])))
        total_len = sum(sum(t.values()) for t in self._doc_tokens) or 1
        n_docs = len(self._doc_tokens) or 1
        self._avgdl = total_len / n_docs
        self._compute_idf()

    def _compute_idf(self) -> None:
        n = len(self._doc_tokens)
        df: Counter = Counter()
        for tokens in self._doc_tokens:
            df.update(tokens.keys())
        self._idf = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        q_tokens = _tokenize(query)
        if not q_tokens or not self._doc_tokens:
            return []
        scores: list[tuple[int, float]] = []
        for idx, tokens in enumerate(self._doc_tokens):
            score = 0.0
            doc_len = sum(tokens.values())
            for term in q_tokens:
                tf = tokens.get(term, 0)
                if tf == 0:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = tf + self._k1 * (1 - self._b + self._b * doc_len / self._avgdl)
                score += idf * (tf * (self._k1 + 1)) / denom
            scores.append((idx, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [
            RetrievedChunk(
                id=self._doc_ids[idx],
                text=self._docs[idx],
                score=score,
                metadata=self._doc_metadata[idx],
            )
            for idx, score in scores[:top_k]
        ]

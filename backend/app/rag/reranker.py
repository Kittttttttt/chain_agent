"""Reranker：对混合检索结果重排。

默认使用「查询-文档」向量相似度 + 召回排名特征进行轻量重排；
在配置了 LLM 时可接入 LLM 打分器（RankLLM），进一步提高相关性判断质量。
"""
from __future__ import annotations

from typing import Any, Callable

from app.rag.vectorstore import RetrievedChunk

# 类型：给一段文本打分（query, candidate）→ score(0-1)
Scorer = Callable[[str, str], float]


class EmbeddingReranker:
    """基于 embedding 相似度的重排器。"""

    def __init__(
        self,
        embed_fn: Callable[[list[str]], list[list[float]]],
        dense_weight: float = 0.5,
        rrf_weight: float = 0.5,
    ) -> None:
        self._embed_fn = embed_fn
        self._dense_weight = dense_weight
        self._rrf_weight = rrf_weight

    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int = 3) -> list[RetrievedChunk]:
        if not candidates:
            return []
        q_vec = self._embed_fn([query])[0]
        q_norm = _l2(q_vec)
        for chunk in candidates:
            c_vec = self._embed_fn([chunk.text])[0]
            sim = _cosine_sim(q_vec, q_norm, c_vec)
            rrf_score = chunk.score  # RRF 融合后的分数
            chunk.score = self._dense_weight * sim + self._rrf_weight * min(rrf_score, 1.0)
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:top_k]


class LLMReranker:
    """基于 LLM 的相关性打分重排器（可选）。"""

    def __init__(self, llm: Any, prompt_template: str | None = None) -> None:
        self._llm = llm
        self._template = prompt_template or (
            "你是检索重排器。判断以下内容与问题是否相关，只输出 0-1 之间的数字：\n"
            "问题: {query}\n内容: {candidate}\n相关性分数(0-1):"
        )

    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int = 3) -> list[RetrievedChunk]:
        for chunk in candidates:
            prompt = self._template.format(query=query, candidate=chunk.text[:2000])
            try:
                resp = self._llm.invoke(prompt)
                chunk.score = float(_extract_number(str(resp.content)))
            except Exception:  # noqa: BLE001 - LLM 打分失败不阻塞流程
                chunk.score = 0.5
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:top_k]


def _l2(v: list[float]) -> float:
    return sum(x * x for x in v) ** 0.5


def _cosine_sim(v1: list[float], n1: float, v2: list[float]) -> float:
    n2 = _l2(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    return sum(a * b for a, b in zip(v1, v2)) / (n1 * n2)


def _extract_number(text: str) -> float:
    import re

    m = re.search(r"0?\.\d+|1(\.0+)?|[01]", text)
    if not m:
        return 0.5
    return min(1.0, max(0.0, float(m.group())))

"""Hybrid Retrieval：向量召回与 BM25 结果融合。

使用 RRF（Reciprocal Rank Fusion）融合两个检索通道的排序结果：
  score(d) = Σ 1 / (k + rank(d))
"""
from __future__ import annotations

from app.rag.vectorstore import RetrievedChunk


def rrf_fusion(
    dense_results: list[RetrievedChunk],
    bm25_results: list[RetrievedChunk],
    k: int = 60,
) -> list[RetrievedChunk]:
    """将两路检索结果按 RRF 融合。"""
    fused: dict[str, dict] = {}
    for results in (dense_results, bm25_results):
        for rank, chunk in enumerate(results):
            entry = fused.setdefault(
                chunk.id,
                {
                    "chunk": chunk,
                    "rrf": 0.0,
                    "dense_rank": None,
                    "bm25_rank": None,
                },
            )
            entry["rrf"] += 1.0 / (k + rank + 1)
            if results is dense_results:
                entry["dense_rank"] = rank
            else:
                entry["bm25_rank"] = rank

    ordered = sorted(fused.values(), key=lambda e: e["rrf"], reverse=True)
    results: list[RetrievedChunk] = []
    for entry in ordered:
        chunk = entry["chunk"]
        chunk.score = entry["rrf"]
        chunk.metadata["dense_rank"] = entry["dense_rank"]
        chunk.metadata["bm25_rank"] = entry["bm25_rank"]
        results.append(chunk)
    return results

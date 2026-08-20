"""评测指标实现。

- Retrieval: Recall@K, MRR
- Agent: Task Completion, Tool Success Rate, Iteration Count
- Answer: Faithfulness(关键词覆盖), Citation Coverage
"""
from __future__ import annotations

import re
from typing import Any


def recall_at_k(relevant_ids: list[str], retrieved_ids: list[str], k: int | None = None) -> float:
    """Recall@K：K 个检索结果中命中的相关项比例。"""
    k = k or len(retrieved_ids)
    if not relevant_ids:
        return 0.0
    hit = sum(1 for rid in retrieved_ids[:k] if rid in relevant_ids)
    return hit / len(relevant_ids)


def mrr(relevant_ids: list[str], retrieved_ids: list[str]) -> float:
    """MRR：首个相关结果的倒数排名。"""
    for rank, rid in enumerate(retrieved_ids, 1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def keyword_coverage(text: str, keywords: list[str]) -> float:
    """关键词覆盖率（用于粗略衡量回答忠实度）。"""
    if not keywords:
        return 1.0
    lowered = text.lower()
    hit = sum(1 for kw in keywords if kw.lower() in lowered)
    return hit / len(keywords)


def tool_success_rate(tool_calls: list[dict[str, Any]]) -> float:
    if not tool_calls:
        return 1.0
    ok = sum(1 for tc in tool_calls if tc.get("success"))
    return ok / len(tool_calls)


def citation_coverage(report: str, citations: list[Any]) -> float:
    """报告中实际使用的引用占全部引用/来源的比例。"""
    if not citations:
        return 0.0
    refs = set(re.findall(r"\[来源(\d+)\]", report))
    return min(1.0, len(refs) / len(citations))


def aggregation_table(rows: list[dict[str, Any]]) -> str:
    """将指标行渲染为 Markdown 表格。"""
    if not rows:
        return "_无数据_"
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)

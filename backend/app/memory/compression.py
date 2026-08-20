"""Context Compression：避免 Context 无限增长。

策略：
- 滚动窗口：只保留最近 N 条消息
- 摘要压缩：较旧的 tool 结果 / 文档摘要为一行
- Token 预算裁剪：超过上限时丢弃最不相关的观察
"""
from __future__ import annotations

from typing import Any


class ContextCompressor:
    """上下文压缩器。"""

    def __init__(self, max_tokens: int = 8000, keep_recent: int = 8) -> None:
        self._max_tokens = max_tokens
        self._keep_recent = keep_recent

    def compress_notes(self, notes: list[str], max_items: int = 10) -> list[str]:
        """保留最近 max_items 条，其余合并为摘要。"""
        if len(notes) <= max_items:
            return notes
        recent = notes[-max_items:]
        old = notes[:-max_items]
        summary = "【历史摘要】" + "；".join(n[:80] for n in old[-5:])
        return [summary] + recent

    def compress_evidence(self, evidence: list[Any], max_items: int = 15) -> list[Any]:
        """仅保留高置信度证据，控制进入上下文的证据数量。"""
        sorted_ev = sorted(evidence, key=lambda e: getattr(e, "confidence", 0), reverse=True)
        return sorted_ev[:max_items]

    def truncate_text(self, text: str, limit: int = 3000) -> str:
        return text[:limit] if len(text) > limit else text

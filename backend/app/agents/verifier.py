"""Citation Verifier：对最终报告中的引用进行校验。

原则：禁止编造来源。
- 报告中的引用必须能映射到实际检索到的 Source
- 无法映射 / 无法验证的声明标记为 `unverified`
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.models import Citation, Evidence, Source
from app.observability import traceable


class CitationVerifier:
    """引用校验器。"""

    @traceable(name="citation_verifier.verify")
    def verify(self, report: str, evidence: list[Evidence]) -> list[Citation]:
        """从报告中提取 [来源N] 标记并映射到证据来源。"""
        citations: list[Citation] = []
        # 收集报告中出现的引用编号
        refs = sorted({int(m) for m in re.findall(r"\[来源(\d+)\]", report)})
        evidence_by_index = {i + 1: e for i, e in enumerate(evidence)}

        for ref in refs:
            ev = evidence_by_index.get(ref)
            if ev is None:
                citations.append(
                    Citation(
                        claim=f"[来源{ref}]",
                        source=Source(url="", title="未知来源"),
                        status="unverified",
                        confidence=0.0,
                        reason="报告引用了未检索到的来源编号",
                    )
                )
                continue
            citations.append(
                Citation(
                    claim=ev.claim,
                    source=ev.source,
                    status="verified" if ev.source.url else "unverified",
                    confidence=ev.confidence,
                    reason="对应到已检索证据",
                )
            )
        logger.info("引用校验完成: {} 条 (verified={})", len(citations), sum(1 for c in citations if c.status == "verified"))
        return citations

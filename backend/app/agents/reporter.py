"""Report Writer Agent：汇总证据生成结构化研究报告。"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.agents.llm import get_llm
from app.models import Evidence
from app.observability import traceable

_REPORTER_PROMPT = """你是一名深度研究分析师。请基于以下证据，撰写一份结构化的深度研究报告。

研究问题：{question}

可用的证据（带来源）：
{evidence}

要求：
1. 报告采用 Markdown，包含：摘要、正文（分小节）、关键结论。
2. 每个关键结论后标注来源编号，格式：[来源N]。
3. 只使用提供的证据，不得编造任何事实或来源。
4. 若证据不足，明确标注「证据不足，无法确认」。
5. 输出完整报告正文（Markdown）。"""


class ReportWriterAgent:
    """报告生成器。"""

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm or get_llm()

    @traceable(name="report_writer.write")
    def write(self, question: str, evidence: list[Evidence]) -> str:
        if not evidence:
            return (
                f"# {question}\n\n"
                "**证据不足，无法生成可靠报告。** 本次研究未能收集到足够可靠的证据。"
            )
        evidence_text = "\n\n".join(
            f"[{i + 1}] {e.claim}\n    - 来源: {e.source.title} ({e.source.url})\n"
            f"    - 置信度: {e.confidence:.2f}"
            for i, e in enumerate(evidence)
        )
        prompt = _REPORTER_PROMPT.format(
            question=question,
            evidence=evidence_text[:12000],
        )
        try:
            resp = self._llm.invoke(prompt)
            report = str(resp.content).strip()
        except Exception as exc:  # noqa: BLE001
            logger.error("报告生成失败({}), 使用模板回退", exc)
            report = self._fallback(question, evidence)
        return report

    @staticmethod
    def _fallback(question: str, evidence: list[Evidence]) -> str:
        """无 LLM 时的模板回退（保证演示可运行）。"""
        lines = [f"# {question}", "", "## 摘要", ""]
        for i, e in enumerate(evidence, 1):
            lines.append(f"- 发现{i}: {e.claim}（来源: {e.source.title}, {e.source.url}）")
        lines += ["", "## 结论", "", "以上结论均基于检索到的证据，详见引用来源。"]
        return "\n".join(lines)

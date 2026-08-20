"""Planner Agent：将用户研究问题拆解为结构化研究计划。

由 LLM 真正参与任务拆解（Agent First），输出 JSON 结构化计划。
"""
from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from app.agents.llm import get_llm
from app.models import ResearchPlan, Subtask
from app.observability import traceable

_PLANNER_PROMPT = """你是一名资深研究规划师。请将用户的研究问题拆解为可执行的子任务，并生成研究计划。

要求：
1. 分析问题的范围、时效性、所需信息来源（web/arxiv/github/document）。
2. 拆解为 3~6 个子任务，每个子任务应相互独立、可并行执行。
3. 输出严格的 JSON，不要输出其他内容，格式如下：
{{
  "goal": "研究目标一句话概括",
  "subtasks": [
    {{
      "id": "task_1",
      "question": "子任务具体问题",
      "priority": "high|medium|low",
      "required_sources": ["web", "arxiv", "github"]
    }}
  ]
}}

用户问题：{question}"""


class PlannerAgent:
    """研究计划生成器。"""

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm or get_llm()

    @traceable(name="planner.plan")
    def plan(self, question: str) -> ResearchPlan:
        prompt = _PLANNER_PROMPT.format(question=question)
        try:
            resp = self._llm.invoke(prompt)
            content = str(resp.content)
            plan = self._parse(content)
        except Exception as exc:  # noqa: BLE001
            logger.error("Planner 解析失败({}), 使用兜底计划", exc)
            plan = ResearchPlan(
                goal=question,
                subtasks=[
                    Subtask(
                        id="task_1",
                        question=question,
                        priority="high",
                        required_sources=["web", "arxiv"],
                    )
                ],
            )
        logger.info("生成研究计划: goal={}, subtasks={}", plan.goal, len(plan.subtasks))
        return plan

    def _parse(self, content: str) -> ResearchPlan:
        """从 LLM 输出中提取 JSON（容忍 Markdown 代码块包裹）。"""
        json_str = re.sub(r"```(?:json)?", "", content).strip()
        data: dict[str, Any] = json.loads(json_str)
        subtasks = []
        for idx, item in enumerate(data.get("subtasks", [])):
            subtasks.append(
                Subtask(
                    id=item.get("id") or f"task_{idx + 1}",
                    question=item.get("question") or "",
                    priority=item.get("priority", "medium"),
                    required_sources=item.get("required_sources", ["web"]),
                )
            )
        if not subtasks:
            raise ValueError("计划中没有子任务")
        return ResearchPlan(goal=data.get("goal") or "", subtasks=subtasks)

"""Research Worker Agent：核心 Agent Loop。

真实 Tool Calling 实现：LLM 绑定工具 → 自主决策调用 → 执行工具 → 观察结果，
循环直到 LLM 判定不再需要工具或达到轮次上限。
"""
from __future__ import annotations

from typing import Any

from loguru import logger
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.llm import get_llm
from app.observability import traceable
from app.tools.registry import ToolRegistry

_WORKER_SYSTEM = """你是一名深度研究执行者，为研究问题收集可靠证据。

可用工具：
- search_web(query): 网页搜索，查找时效性信息
- search_arxiv(query): 学术论文检索
- search_github(query): 开源仓库检索
- read_webpage(url): 读取网页正文
- retrieve_documents(query): 在已收集文档中检索

规则：
1. 分析当前证据缺口后，自主决定调用哪个工具。
2. 一次可并行发起多个工具调用。
3. 观察工具结果，提取关键证据。
4. 当证据足以支撑回答时，输出最终研究结论，不要继续调用工具。
5. 禁止编造工具结果；工具失败时可换策略重试。"""


class ResearchWorkerAgent:
    """在单个节点内执行一轮「决策-调用-观察」循环。"""

    def __init__(self, registry: ToolRegistry, llm: Any = None) -> None:
        self._registry = registry
        self._llm = llm or get_llm()
        self._tools = registry.to_langchain_tools()
        self._tool_map = {t.name: t for t in registry.tools}
        self._bound_llm = self._llm.bind_tools(self._tools)

    @traceable(name="research_worker.run_once")
    def run_once(
        self,
        question: str,
        context: str,
        iteration: int,
        max_iterations: int,
    ) -> dict[str, Any]:
        """执行一轮 Agent Loop，返回结构化结果。

        返回:
            {
              "observations": [tool 观察文本],
              "evidence": [{"claim", "source_url", "title", "confidence"}],
              "notes": str,
              "tool_calls": [{"tool", "input", "output", "latency", "success"}],
            }
        """
        messages = [
            SystemMessage(content=_WORKER_SYSTEM),
            HumanMessage(
                content=(
                    f"研究问题：{question}\n"
                    f"当前已有上下文（第 {iteration}/{max_iterations} 轮）：\n{context[:3000]}\n"
                    "请决定本轮动作。"
                )
            ),
        ]

        observations: list[str] = []
        evidence: list[dict[str, Any]] = []
        tool_calls_log: list[dict[str, Any]] = []
        notes = ""
        max_tool_rounds = 4  # 单节点内最大工具调用轮数，防止失控

        for _ in range(max_tool_rounds):
            resp = self._bound_llm.invoke(messages)
            messages.append(resp)

            if not getattr(resp, "tool_calls", None):
                # LLM 判定不再需要工具 → 本轮结束
                notes = str(resp.content)
                break

            # OpenAI 协议要求：每个 tool_call 必须用带 tool_call_id 的 ToolMessage 回填
            tool_messages: list[Any] = []
            for tc in resp.tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id", "")
                tool = self._tool_map.get(tool_name)
                if tool is None:
                    observation = f"[tool:{tool_name}] 不存在，已跳过"
                    tool_messages.append(
                        ToolMessage(content=observation, tool_call_id=tool_call_id, name=tool_name)
                    )
                    continue
                result = tool.invoke(**tool_args)
                tool_calls_log.append(
                    {
                        "tool": tool_name,
                        "input": tool_args,
                        "output": result.data if result.success else result.error,
                        "latency_ms": result.latency_ms,
                        "success": result.success,
                    }
                )
                observation = result.to_observation()
                observations.append(observation)
                tool_messages.append(
                    ToolMessage(content=observation, tool_call_id=tool_call_id, name=tool_name)
                )
                # 简单证据抽取：网页/检索返回的直接文本作为候选证据
                data = result.data
                if isinstance(data, dict) and "results" in data:
                    data = data["results"]  # retrieve_documents 等返回 {results, detail}
                if result.success and isinstance(data, list):
                    for item in data[:3]:
                        if isinstance(item, dict) and item.get("url"):
                            evidence.append(
                                {
                                    "claim": (item.get("snippet") or item.get("title") or "")[:300],
                                    "source_url": item.get("url", ""),
                                    "title": item.get("title", ""),
                                    "confidence": 0.6,
                                }
                            )
            # 将 ToolMessage 结果回填给模型（必须，否则违反 OpenAI 协议）
            messages.extend(tool_messages)

        return {
            "observations": observations,
            "evidence": evidence,
            "notes": notes,
            "tool_calls": tool_calls_log,
        }

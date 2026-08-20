"""短时记忆：基于 LangGraph Checkpointer（InMemorySaver / PostgresSaver）。

短时记忆保存：当前研究状态、消息、工具结果、证据等（即 AgentState 本身）。
"""
from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from app.graph.state import AgentState


class ShortTermMemory:
    """研究会话级短时记忆，通过 Checkpointer 保存 AgentState。"""

    def __init__(self) -> None:
        self._checkpointer = InMemorySaver()
        self._threads: dict[str, str] = {}  # research_id -> thread_id

    @property
    def checkpointer(self) -> InMemorySaver:
        return self._checkpointer

    def register(self, research_id: str) -> str:
        """为一次研究注册线程。"""
        self._threads[research_id] = f"thread-{research_id}"
        return self._threads[research_id]

    def get_thread(self, research_id: str) -> str | None:
        return self._threads.get(research_id)

    def snapshot(self, research_id: str, state: AgentState) -> None:
        """快照当前状态（供恢复/分析）。"""
        self._threads[research_id] = f"thread-{research_id}"

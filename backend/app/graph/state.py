"""LangGraph Agent State 定义。"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.models import Citation, Evidence, ResearchPlan, Source, Subtask


class TokenUsage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class AgentState(TypedDict, total=True):
    # ---- 输入 ----
    research_question: str
    depth: str
    max_iterations: int

    # ---- 计划 ----
    research_plan: ResearchPlan
    current_task_id: str | None

    # ---- 执行过程 ----
    messages: Annotated[list[BaseMessage], add_messages]
    search_queries: Annotated[list[str], operator.add]
    documents: Annotated[list[dict[str, Any]], operator.add]
    tool_calls: Annotated[list[dict[str, Any]], operator.add]
    research_notes: Annotated[list[str], operator.add]
    observations_pool: Annotated[list[str], operator.add]
    # 执行事件流（供 SSE / 前端 Trace 面板消费，含耗时/状态/错误）
    events: Annotated[list[dict[str, Any]], operator.add]

    # ---- 证据 / 声明 / 引用 ----
    evidence: Annotated[list[Evidence], operator.add]
    claims: Annotated[list[str], operator.add]
    citations: Annotated[list[Citation], operator.add]
    verification_results: Annotated[list[dict[str, Any]], operator.add]

    # ---- 循环控制 ----
    iteration_count: int
    sufficiency_threshold: float
    sufficiency_score: float
    sufficient: bool
    worker_status: str  # running / done / failed

    # ---- 输出 ----
    final_report: str

    # ---- 度量 ----
    token_usage: TokenUsage
    execution_metadata: dict[str, Any]  # latency / cost / per-node metrics


def initial_state(question: str, depth: str = "standard", max_iterations: int = 8) -> AgentState:
    """构造初始 Agent State。"""
    return {
        "research_question": question,
        "depth": depth,
        "max_iterations": max_iterations,
        "research_plan": ResearchPlan(goal="", subtasks=[]),
        "current_task_id": None,
        "messages": [],
        "search_queries": [],
        "documents": [],
        "tool_calls": [],
        "research_notes": [],
        "observations_pool": [],
        "events": [],
        "evidence": [],
        "claims": [],
        "citations": [],
        "verification_results": [],
        "iteration_count": 0,
        "sufficiency_threshold": 0.6,
        "sufficiency_score": 0.0,
        "sufficient": False,
        "worker_status": "running",
        "final_report": "",
        "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "execution_metadata": {},
    }

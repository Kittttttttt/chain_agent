"""LangGraph 工作流：构建 DeepResearch Agent 的 StateGraph。

节点：research_intake → planner → research_worker → evidence_extraction
      → evidence_evaluation → sufficiency_check
        ├─ insufficient → research_worker（循环）
        └─ sufficient  → report_writer → citation_verification → evaluator → END
"""
from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from loguru import logger

from app.agents.evaluator import evidence_score, is_sufficient
from app.agents.llm import get_llm
from app.agents.planner import PlannerAgent
from app.agents.reporter import ReportWriterAgent
from app.agents.verifier import CitationVerifier
from app.agents.worker import ResearchWorkerAgent
from app.graph.state import AgentState
from app.models import Evidence, Source, Subtask
from app.tools.registry import ToolRegistry, get_default_registry

# 运行时组件容器（可替换为依赖注入）
_RUNTIME: dict[str, Any] = {}

# 事件实时转发回调（由 build_graph 绑定，service 侧写入会话供 SSE 消费）
_CALLBACK: Callable[[dict], None] | None = None

# 工具名 → Agent 执行阶段（供前端 Trace 面板分组展示）
_TOOL_PHASE: dict[str, str] = {
    "search_web": "web_search",
    "search_arxiv": "arxiv_search",
    "search_github": "github_search",
    "read_webpage": "read_source",
    "retrieve_documents": "rag_retrieval",
}


def _get_tool_registry() -> ToolRegistry:
    if "tool_registry" not in _RUNTIME:
        _RUNTIME["tool_registry"] = get_default_registry()
    return _RUNTIME["tool_registry"]


# ---------------------------------------------------------------------------
# 事件发射基础设施
# ---------------------------------------------------------------------------


def _emit(state: AgentState, event: dict[str, Any]) -> None:
    """向 state.events 追加事件，并实时转发给外部回调（供 SSE）。"""
    event["ts"] = time.time()
    state.setdefault("events", []).append(event)
    if _CALLBACK is not None:
        _CALLBACK(event)


def _node(name: str) -> Callable:
    """装饰器：包装图节点，广播 node_start / node_end（含耗时），仅返回本节点新增事件。"""

    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(state: AgentState) -> dict[str, Any]:
            # 复制 events 列表：避免节点内 append 修改共享引用，导致 operator.add 归约重复
            base = list(state.get("events") or [])
            state["events"] = base
            start_idx = len(base)
            _emit(state, {"type": "node_start", "node": name})
            t0 = time.time()
            out = fn(state) or {}
            latency_ms = int(round((time.time() - t0) * 1000))
            _emit(state, {"type": "node_end", "node": name, "latency_ms": latency_ms, "status": "done"})
            out["events"] = state["events"][start_idx:]
            return out

        return wrapper

    return deco


# ---------------------------------------------------------------------------
# 节点实现
# ---------------------------------------------------------------------------


def research_intake(state: AgentState) -> dict[str, Any]:
    """初始化：记录开始时间与深度配置。"""
    state["execution_metadata"]["started_at"] = time.time()
    state["execution_metadata"]["node_timings"] = {}
    logger.info("研究启动: {}", state["research_question"][:80])
    return {"execution_metadata": state["execution_metadata"]}


def planner_node(state: AgentState) -> dict[str, Any]:
    """Planner：拆解研究任务。"""
    t0 = time.time()
    planner = PlannerAgent()
    plan = planner.plan(state["research_question"])
    state["research_plan"] = plan
    state["execution_metadata"]["node_timings"]["planner"] = round(time.time() - t0, 3)
    _emit(state, {"type": "planner_plan", "plan": plan.model_dump()})
    return {
        "research_plan": plan,
        "execution_metadata": state["execution_metadata"],
    }


def _current_task(state: AgentState) -> Subtask:
    """取当前（或第一个 pending）子任务。"""
    plan = state["research_plan"]
    for st in plan.subtasks:
        if st.status == "pending":
            return st
    return plan.subtasks[0] if plan.subtasks else Subtask(id="task_1", question=state["research_question"])


def research_worker(state: AgentState) -> dict[str, Any]:
    """Research Worker：Agent Loop（决策→调用→观察）。

    注意：tool_calls / research_notes / observations_pool / evidence 均为
    operator.add 归约字段，本节点只返回「本轮新增」的部分，避免重复累加。
    """
    t0 = time.time()
    task = _current_task(state)
    worker = ResearchWorkerAgent(registry=_get_tool_registry())
    iteration = state.get("iteration_count", 0) + 1
    max_iter = state.get("max_iterations", 8)

    context = "\n".join(state.get("observations_pool", [])[-10:]) or state["research_question"]

    result = worker.run_once(
        question=task.question,
        context=context,
        iteration=iteration,
        max_iterations=max_iter,
    )

    new_tool_calls = result["tool_calls"]
    new_note = result["notes"] or f"Task {task.id}: 完成一轮研究（{len(new_tool_calls)} 次工具调用）"
    new_observations = result["observations"]

    # 广播每次工具调用事件（含阶段映射 / 耗时 / 错误 / RAG 检索明细）
    for call in new_tool_calls:
        tool_name = call.get("tool", "")
        phase = _TOOL_PHASE.get(tool_name, "tool_call")
        event: dict[str, Any] = {
            "type": "tool_call",
            "tool": tool_name,
            "phase": phase,
            "input": call.get("input"),
            "success": call.get("success", False),
            "latency_ms": call.get("latency_ms"),
        }
        output = call.get("output")
        if isinstance(output, dict) and "detail" in output and phase == "rag_retrieval":
            # RAG 检索明细（Dense / BM25 / Hybrid / Rerank）
            detail = output["detail"]
            event["output_summary"] = f"top-{len(detail.get('reranked', []))} 片段"
            _emit(state, event)
            _emit(
                state,
                {
                    "type": "rag_retrieval",
                    "query": detail.get("query", ""),
                    "dense": detail.get("dense", []),
                    "bm25": detail.get("bm25", []),
                    "hybrid": detail.get("hybrid", []),
                    "reranked": detail.get("reranked", []),
                },
            )
        else:
            summary = output if isinstance(output, str) else (len(output) if output else 0)
            event["output_summary"] = f"{summary} 条结果" if isinstance(summary, int) else str(summary)[:200]
            if not event["success"]:
                event["error"] = str(output)
            _emit(state, event)

    # 新增证据（去重：按 source_url）
    existing_urls = {e.source.url for e in state.get("evidence", [])}
    new_evidence: list[Evidence] = []
    for ev in result["evidence"]:
        url = ev.get("source_url", "")
        if url and url not in existing_urls:
            new_evidence.append(
                Evidence(
                    claim=ev["claim"],
                    source=Source(
                        url=url,
                        title=ev.get("title", ""),
                        source_type="web",
                        snippet=ev["claim"],
                    ),
                    relevance=0.8,
                    confidence=float(ev.get("confidence", 0.6)),
                )
            )
            existing_urls.add(url)

    state["iteration_count"] = iteration
    timings = state.get("execution_metadata", {}).get("node_timings", {})
    timings["worker"] = round(time.time() - t0, 3)
    metadata = dict(state.get("execution_metadata", {}))
    metadata["node_timings"] = timings

    return {
        "tool_calls": new_tool_calls,
        "research_notes": [new_note],
        "evidence": new_evidence,
        "iteration_count": iteration,
        "observations_pool": new_observations,
        "execution_metadata": metadata,
    }


def evidence_extraction(state: AgentState) -> dict[str, Any]:
    """从观察中提取证据（与 worker 已合并）。

    证据字段为 operator.add 归约，此处不返回值，排序在 evidence_evaluation 内完成。
    """
    return {}


def evidence_evaluation(state: AgentState) -> dict[str, Any]:
    """评估证据质量与充分性。"""
    evidence = sorted(state.get("evidence", []), key=lambda e: e.confidence, reverse=True)
    score = evidence_score(evidence)
    state["sufficiency_score"] = score
    state["execution_metadata"]["sufficiency_score"] = score
    _emit(
        state,
        {
            "type": "evidence_evaluated",
            "sufficiency_score": score,
            "evidence_count": len(evidence),
            "threshold": state.get("sufficiency_threshold", 0.6),
        },
    )
    logger.info("证据评估: score={} evidence={}", score, len(evidence))
    return {
        "sufficiency_score": score,
        "execution_metadata": state["execution_metadata"],
    }


def sufficiency_check(state: AgentState) -> str:
    """Sufficiency Check：判断继续研究还是进入报告阶段。"""
    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 8)
    sufficient, score = is_sufficient(
        evidence=state.get("evidence", []),
        threshold=state.get("sufficiency_threshold", 0.6),
        min_evidence=3,
        iteration=iteration,
        max_iterations=max_iter,
    )
    logger.info(
        "Sufficiency: {} (score={}, iteration={}/{})",
        "sufficient" if sufficient else "continue",
        score,
        iteration,
        max_iter,
    )
    if sufficient:
        return "report"
    return "continue"


def report_writer(state: AgentState) -> dict[str, Any]:
    """Report Writer：基于证据生成结构化报告。"""
    t0 = time.time()
    writer = ReportWriterAgent()
    report = writer.write(state["research_question"], state.get("evidence", []))
    state["final_report"] = report
    state["execution_metadata"]["node_timings"]["report_writer"] = round(time.time() - t0, 3)
    _emit(state, {"type": "report_generated", "length": len(report)})
    return {"final_report": report, "execution_metadata": state["execution_metadata"]}


def citation_verification(state: AgentState) -> dict[str, Any]:
    """Citation Verification：报告引用与来源映射校验。"""
    verifier = CitationVerifier()
    citations = verifier.verify(state.get("final_report", ""), state.get("evidence", []))
    state["citations"] = citations
    _emit(
        state,
        {
            "type": "citation_verified",
            "citations": [c.model_dump() for c in citations],
            "verified_count": sum(1 for c in citations if c.status == "verified"),
            "unverified_count": sum(1 for c in citations if c.status == "unverified"),
        },
    )
    return {"citations": citations}


def evaluator_node(state: AgentState) -> dict[str, Any]:
    """Evaluator：汇总执行指标（token / latency / cost）。"""
    metadata = state.get("execution_metadata", {})
    metadata["finished_at"] = time.time()
    if metadata.get("started_at"):
        metadata["total_latency_s"] = round(metadata["finished_at"] - metadata["started_at"], 3)
    metadata["tool_call_count"] = len(state.get("tool_calls", []))
    metadata["evidence_count"] = len(state.get("evidence", []))
    metadata["iteration_count"] = state.get("iteration_count", 0)
    _emit(state, {"type": "evaluator_done", "metrics": dict(metadata)})
    return {"execution_metadata": metadata}


# ---------------------------------------------------------------------------
# 图构建
# ---------------------------------------------------------------------------


def build_graph(event_callback: Callable[[dict], None] | None = None) -> Any:
    """构建并编译 LangGraph。

    event_callback: 可选实时事件回调（服务层传入后，事件同步写入会话供 SSE 消费）。
    """
    global _CALLBACK
    _CALLBACK = event_callback
    g = StateGraph(AgentState)
    g.add_node("research_intake", _node("research_intake")(research_intake))
    g.add_node("planner", _node("planner")(planner_node))
    g.add_node("research_worker", _node("research_worker")(research_worker))
    g.add_node("evidence_extraction", _node("evidence_extraction")(evidence_extraction))
    g.add_node("evidence_evaluation", _node("evidence_evaluation")(evidence_evaluation))
    g.add_node("report_writer", _node("report_writer")(report_writer))
    g.add_node("citation_verification", _node("citation_verification")(citation_verification))
    g.add_node("evaluator", _node("evaluator")(evaluator_node))

    g.add_edge(START, "research_intake")
    g.add_edge("research_intake", "planner")
    g.add_edge("planner", "research_worker")
    g.add_edge("research_worker", "evidence_extraction")
    g.add_edge("evidence_extraction", "evidence_evaluation")
    g.add_conditional_edges(
        "evidence_evaluation",
        sufficiency_check,
        {"continue": "research_worker", "report": "report_writer"},
    )
    g.add_edge("report_writer", "citation_verification")
    g.add_edge("citation_verification", "evaluator")
    g.add_edge("evaluator", END)

    return g.compile()


def run_research(question: str, depth: str = "standard", max_iterations: int = 8) -> dict[str, Any]:
    """便捷入口：执行一次完整研究。"""
    from app.config import get_settings
    from app.graph.state import initial_state
    from app.observability import setup_langsmith

    setup_langsmith(get_settings())  # 确保 LangSmith 环境变量已注入
    graph = build_graph()
    state = initial_state(question, depth=depth, max_iterations=max_iterations)
    final = graph.invoke(state)
    return final

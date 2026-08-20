"""研究编排服务：受理、执行、查询研究任务。"""
from __future__ import annotations

import contextvars
import json
import threading
import time
import uuid
from typing import Any, Callable

from loguru import logger

from app.agents.llm import get_llm
from app.config import get_settings
from app.graph.graph import build_graph
from app.graph.state import initial_state
from app.memory.long_term import build_long_term_memory
from app.memory.short_term import ShortTermMemory
from app.models import ResearchPlan, Source

# 当前线程正在执行的研究任务（graph 事件回调据此路由到对应会话）
_CURRENT_RID: contextvars.ContextVar[str | None] = contextvars.ContextVar("research_rid", default=None)


class ResearchService:
    """管理多次研究的生命周期（同步执行 + 异步回调）。"""

    def __init__(self) -> None:
        self._settings = get_settings()
        from app.observability import setup_langsmith

        setup_langsmith(self._settings)  # API 路径：启动时注入 LangSmith 环境变量
        self._graph = None
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._long_term = build_long_term_memory(
            backend=self._settings.memory_backend,
            database_url=self._settings.database_url,
            sqlite_path=self._settings.sqlite_path,
        )
        self._short_term = ShortTermMemory()

    def _ensure_graph(self):
        if self._graph is None:
            self._graph = build_graph(event_callback=self._emit_event)
        return self._graph

    def _emit_event(self, event: dict[str, Any]) -> None:
        """graph 实时事件 → 写入当前任务的会话（供 SSE 增量消费）。"""
        rid = _CURRENT_RID.get()
        if rid is None:
            return
        with self._lock:
            session = self._sessions.get(rid)
            if session is not None:
                session.setdefault("events", []).append(event)

    def create_session(self, question: str, depth: str = "standard", max_iterations: int | None = None) -> str:
        """创建研究会话，返回 research_id。"""
        research_id = uuid.uuid4().hex[:12]
        self._short_term.register(research_id)
        self._sessions[research_id] = {
            "research_id": research_id,
            "question": question,
            "depth": depth,
            "status": "queued",
            "created_at": time.time(),
            "report": "",
            "sources": [],
            "citations": [],
            "evidence": [],
            "metrics": {},
            "trace": [],
            "events": [],
            "error": None,
        }
        return research_id

    def run(self, research_id: str, max_iterations: int | None = None) -> dict[str, Any]:
        """同步执行研究并更新会话状态。"""
        _CURRENT_RID.set(research_id)  # graph 事件回调路由到本会话
        with self._lock:
            session = self._sessions.get(research_id)
            if session is None:
                raise KeyError(f"unknown research_id: {research_id}")
            session["status"] = "running"

        s = self._settings
        graph = self._ensure_graph()
        state = initial_state(
            session["question"],
            depth=session["depth"],
            max_iterations=max_iterations or s.max_iterations,
        )
        # 将阈值等配置注入 state（供 Sufficiency Check 使用）
        state["sufficiency_threshold"] = s.sufficiency_threshold

        try:
            final = graph.invoke(state, config={"recursion_limit": 100})
        except Exception as exc:  # noqa: BLE001
            logger.exception("研究执行失败: {}", research_id)
            session["status"] = "failed"
            session["error"] = str(exc)
            return session

        # 从证据中汇总去重后的来源
        sources: list[Source] = []
        seen_urls: set[str] = set()
        for ev in final.get("evidence", []):
            src = ev.source
            if src.url and src.url not in seen_urls:
                seen_urls.add(src.url)
                sources.append(src)

        with self._lock:
            session.update(
                {
                    "status": "completed",
                    "report": final.get("final_report", ""),
                    "sources": [s.model_dump() for s in sources],
                    "evidence": [e.model_dump() for e in final.get("evidence", [])],
                    "citations": [c.model_dump() for c in final.get("citations", [])],
                    "metrics": {
                        "sufficiency_score": final.get("sufficiency_score", 0.0),
                        "iteration_count": final.get("iteration_count", 0),
                        "evidence_count": len(final.get("evidence", [])),
                        "tool_call_count": len(final.get("tool_calls", [])),
                        "execution_metadata": final.get("execution_metadata", {}),
                        "token_usage": final.get("token_usage", {}),
                    },
                    "trace": self._build_trace(final),
                    # 图执行期间经回调实时写入，此处兜底补全（回调被禁用时）
                    "events": session.get("events") or final.get("events", []),
                }
            )
        # 写入长时记忆
        self._long_term.save_session(
            research_id,
            session["question"],
            final.get("final_report", "")[:500],
            {"user_key": "default", "depth": session["depth"]},
        )
        return session

    def run_async(self, research_id: str, max_iterations: int | None = None) -> None:
        """后台线程执行（供异步 API 使用）。"""
        threading.Thread(target=self.run, args=(research_id, max_iterations), daemon=True).start()

    def get(self, research_id: str) -> dict[str, Any]:
        return self._sessions.get(research_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """返回全部会话摘要（按创建时间倒序，供历史任务页）。"""
        with self._lock:
            sessions = sorted(
                self._sessions.values(),
                key=lambda s: s.get("created_at", 0),
                reverse=True,
            )
            return [
                {
                    "research_id": s["research_id"],
                    "question": s["question"],
                    "depth": s.get("depth", "standard"),
                    "status": s.get("status", "queued"),
                    "created_at": s.get("created_at", 0),
                    "sufficiency_score": s.get("metrics", {}).get("sufficiency_score"),
                    "evidence_count": s.get("metrics", {}).get("evidence_count"),
                    "tool_call_count": s.get("metrics", {}).get("tool_call_count"),
                }
                for s in sessions
            ]

    def _build_trace(self, final: dict[str, Any]) -> list[dict[str, Any]]:
        """构建可读的 Agent 执行轨迹。"""
        trace: list[dict[str, Any]] = [
            {"node": "planner", "plan": final.get("research_plan", ResearchPlan(goal="", subtasks=[])).model_dump()}
        ]
        for call in final.get("tool_calls", []):
            trace.append(
                {
                    "node": "research_worker",
                    "tool": call.get("tool"),
                    "input": call.get("input"),
                    "success": call.get("success"),
                    "latency_ms": call.get("latency_ms"),
                }
            )
        trace.append({"node": "evidence_evaluation", "sufficiency_score": final.get("sufficiency_score")})
        trace.append({"node": "report_writer", "status": "done"})
        return trace


_service: ResearchService | None = None


def get_research_service() -> ResearchService:
    global _service
    if _service is None:
        _service = ResearchService()
    return _service

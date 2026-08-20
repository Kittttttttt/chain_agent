"""FastAPI 路由：研究任务的受理、查询与健康检查。"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.models import HealthResponse, ResearchRequest, ResearchResponse, ResearchResult
from app.services import get_research_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    s = get_settings()
    return HealthResponse(
        status="ok",
        app=s.app_name,
        version=s.app_version,
        llm_provider=s.llm_provider,
        search_provider=s.search_provider,
        vector_backend=s.vector_backend,
        embedding_provider=s.embedding_provider,
    )


@router.post("/api/research", response_model=ResearchResponse, tags=["research"])
async def start_research(req: ResearchRequest) -> ResearchResponse:
    """受理研究任务（后台异步执行）。"""
    service = get_research_service()
    research_id = service.create_session(req.question, depth=req.depth, max_iterations=req.max_iterations)
    service.run_async(research_id, max_iterations=req.max_iterations)
    logger.info("受理研究任务: {} ({})", research_id, req.question[:60])
    return ResearchResponse(research_id=research_id, status="queued", message="研究任务已受理")


@router.post("/api/research/sync", response_model=ResearchResult, tags=["research"])
async def run_research_sync(req: ResearchRequest) -> ResearchResult:
    """同步执行研究（测试/演示用）。"""
    service = get_research_service()
    research_id = service.create_session(req.question, depth=req.depth, max_iterations=req.max_iterations)
    session = service.run(research_id, max_iterations=req.max_iterations)
    return _to_result(session)


@router.get("/api/research", tags=["research"])
async def list_research() -> dict[str, Any]:
    """历史研究任务列表（摘要）。"""
    sessions = get_research_service().list_sessions()
    return {"items": sessions, "total": len(sessions)}


@router.get("/api/research/{research_id}", response_model=ResearchResult, tags=["research"])
async def get_research(research_id: str) -> ResearchResult:
    session = get_research_service().get(research_id)
    if session is None:
        raise HTTPException(status_code=404, detail="research not found")
    return _to_result(session)


@router.get("/api/research/{research_id}/trace", tags=["research"])
async def get_trace(research_id: str) -> dict[str, Any]:
    session = get_research_service().get(research_id)
    if session is None:
        raise HTTPException(status_code=404, detail="research not found")
    return {"research_id": research_id, "trace": session.get("trace", [])}


@router.get("/api/research/{research_id}/sources", tags=["research"])
async def get_sources(research_id: str) -> dict[str, Any]:
    session = get_research_service().get(research_id)
    if session is None:
        raise HTTPException(status_code=404, detail="research not found")
    return {"research_id": research_id, "sources": session.get("sources", [])}


@router.get("/api/research/{research_id}/evaluation", tags=["research"])
async def get_evaluation(research_id: str) -> dict[str, Any]:
    session = get_research_service().get(research_id)
    if session is None:
        raise HTTPException(status_code=404, detail="research not found")
    return {"research_id": research_id, "metrics": session.get("metrics", {})}


@router.get("/api/research/{research_id}/stream", tags=["research"])
async def stream_research(research_id: str):
    """SSE 流式返回 Agent 实时执行事件（节点 / 工具调用 / RAG / 证据 / 报告）。"""

    async def event_gen():
        service = get_research_service()
        last_status = ""
        last_event_idx = 0
        for _ in range(720):  # 最多 720 次轮询（~6 分钟）
            session = service.get(research_id)
            if session is None:
                yield {"event": "error", "data": json.dumps({"detail": "not found"})}
                return

            # 增量推送 agent 事件（节点 / 工具 / RAG / 证据 / 报告）
            events = session.get("events", [])
            while last_event_idx < len(events):
                yield {"event": "agent", "data": json.dumps(events[last_event_idx])}
                last_event_idx += 1

            status = session["status"]
            if status != last_status:
                yield {
                    "event": "status",
                    "data": json.dumps(
                        {
                            "research_id": research_id,
                            "status": status,
                            "report": session.get("report", "") if status == "completed" else "",
                        }
                    ),
                }
                last_status = status

            if status in ("completed", "failed"):
                # 完成后推送一次完整结果（含 evidence/citations/metrics/events）
                yield {"event": "done", "data": json.dumps(_to_result(session).model_dump())}
                return

            import asyncio

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_gen())


def _to_result(session: dict[str, Any]) -> ResearchResult:
    return ResearchResult(
        research_id=session["research_id"],
        status=session.get("status", "running"),
        question=session["question"],
        report=session.get("report", ""),
        sources=session.get("sources", []),
        evidence=session.get("evidence", []),
        citations=session.get("citations", []),
        metrics=session.get("metrics", {}),
        trace=session.get("trace", []),
        events=session.get("events", []),
        error=session.get("error"),
    )

<<<<<<< HEAD
"""FastAPI 路由：研究任务的受理、查询、知识库管理与健康检查。"""
=======
"""FastAPI 路由：研究任务的受理、查询与健康检查。"""
>>>>>>> 5c75f1da527ef6958155c67f4b87d0c0297882d6
from __future__ import annotations

import json
from typing import Any

<<<<<<< HEAD
from fastapi import APIRouter, File, HTTPException, UploadFile
=======
from fastapi import APIRouter, HTTPException
>>>>>>> 5c75f1da527ef6958155c67f4b87d0c0297882d6
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
<<<<<<< HEAD
from app.models import (
    HealthResponse,
    KnowledgeDeleteResponse,
    KnowledgeDocument,
    KnowledgeIndexRequest,
    KnowledgeTestRequest,
    KnowledgeTestResponse,
    KnowledgeUploadResponse,
    ResearchRequest,
    ResearchResponse,
    ResearchResult,
)
from app.rag.docloader import is_supported_filename, load_file, load_text, load_url
=======
from app.models import HealthResponse, ResearchRequest, ResearchResponse, ResearchResult
>>>>>>> 5c75f1da527ef6958155c67f4b87d0c0297882d6
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
<<<<<<< HEAD


# ---------------------------------------------------------------------------
# 知识库（Document Ingestion）
# ---------------------------------------------------------------------------


def _get_pipeline():
    from app.rag.pipeline import get_rag_pipeline

    return get_rag_pipeline()


@router.post("/api/knowledge/upload", response_model=KnowledgeUploadResponse, tags=["knowledge"])
async def upload_knowledge(file: UploadFile = File(...)) -> KnowledgeUploadResponse:
    """上传文档（TXT / Markdown / PDF / HTML）→ 解析 → 切块 → Embedding → Qdrant + BM25。"""
    if not is_supported_filename(file.filename or ""):
        raise HTTPException(status_code=400, detail="不支持的文件类型，仅支持 txt / md / markdown / pdf / html")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        docs = load_file(file.filename or "upload.txt", content, source=file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = _get_pipeline().add_documents(docs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    logger.info("知识库上传: {} → {} chunks", file.filename, result["chunks"])
    return KnowledgeUploadResponse(
        document_id=result["document_id"],
        title=result["title"],
        file_type=str(docs[0].metadata.get("file_type", "txt")),
        chunks=int(result["chunks"]),
        message=result["message"],
    )


@router.post("/api/knowledge/index", response_model=KnowledgeUploadResponse, tags=["knowledge"])
async def index_knowledge(req: KnowledgeIndexRequest) -> KnowledgeUploadResponse:
    """从文本 / URL 入库（Loader → Cleaning → Chunking → Embedding → Qdrant + BM25）。"""
    if not req.text and not req.url:
        raise HTTPException(status_code=400, detail="text 与 url 至少提供一个")

    try:
        if req.url:
            docs = load_url(req.url)
            title = req.title or docs[0].metadata.get("title", "")
            file_type = "html"
        else:
            docs = load_text(
                req.text or "",
                source=req.source or "memory",
                title=req.title or "text",
                file_type=req.file_type,
            )
            title = req.title
            file_type = req.file_type
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = _get_pipeline().add_documents(docs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    logger.info("知识库索引: {} → {} chunks", req.url or req.source, result["chunks"])
    return KnowledgeUploadResponse(
        document_id=result["document_id"],
        title=title,
        file_type=file_type,
        chunks=int(result["chunks"]),
        message=result["message"],
    )


@router.get("/api/knowledge/documents", response_model=list[KnowledgeDocument], tags=["knowledge"])
async def list_knowledge() -> list[KnowledgeDocument]:
    """知识库文档列表（doc_id / 标题 / 类型 / 页数 / chunk 数）。"""
    return [KnowledgeDocument(**item) for item in _get_pipeline().list_documents()]


@router.delete("/api/knowledge/{document_id}", response_model=KnowledgeDeleteResponse, tags=["knowledge"])
async def delete_knowledge(document_id: str) -> KnowledgeDeleteResponse:
    """删除指定文档的全部 chunk（Qdrant + BM25 同步）。"""
    removed = _get_pipeline().delete_document(document_id)
    if removed == 0:
        raise HTTPException(status_code=404, detail=f"文档不存在或已删除: {document_id}")
    return KnowledgeDeleteResponse(
        document_id=document_id,
        deleted_chunks=removed,
        message=f"已删除 {removed} 个 chunk",
    )


@router.post("/api/knowledge/test", response_model=KnowledgeTestResponse, tags=["knowledge"])
async def test_knowledge(req: KnowledgeTestRequest) -> KnowledgeTestResponse:
    """知识库检索测试：Dense + BM25 → Hybrid → Rerank 各阶段明细。"""
    detail = _get_pipeline().retrieve_detailed(req.query, top_k=req.top_k)
    return KnowledgeTestResponse(
        query=detail["query"],
        dense=detail["dense"],
        bm25=detail["bm25"],
        hybrid=detail["hybrid"],
        reranked=detail["reranked"],
    )
=======
>>>>>>> 5c75f1da527ef6958155c67f4b87d0c0297882d6

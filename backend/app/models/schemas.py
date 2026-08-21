"""Pydantic 数据模型（Schema 层）。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 领域模型
# ---------------------------------------------------------------------------


class Source(BaseModel):
    """信息源（网页 / 论文 / 代码仓库）。"""

    url: str = Field(description="来源地址")
    title: str = Field(default="", description="标题")
    source_type: Literal["web", "arxiv", "github", "document"] = "web"
    published_at: str | None = None
    snippet: str = Field(default="", description="摘要片段")
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """证据：一个可被引用的信息片段。"""

    claim: str = Field(description="证据所支撑的陈述")
    source: Source
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    verified: bool = False
    verification_note: str = ""


class Citation(BaseModel):
    """引用：报告中的关键声明与其来源之间的映射。"""

    claim: str
    source: Source
    status: Literal["verified", "unverified"] = "unverified"
    confidence: float = 0.0
    reason: str = ""


class Subtask(BaseModel):
    """Planner 拆解出的子任务。"""

    id: str
    question: str
    priority: Literal["high", "medium", "low"] = "medium"
    required_sources: list[str] = Field(default_factory=lambda: ["web"])
    status: Literal["pending", "in_progress", "done", "failed"] = "pending"
    result_summary: str = ""


class ResearchPlan(BaseModel):
    """整体研究计划。"""

    goal: str
    subtasks: list[Subtask] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API 请求 / 响应
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    """发起一次研究。"""

    question: str = Field(min_length=1, max_length=2000)
    depth: Literal["quick", "standard", "deep"] = "standard"
    max_iterations: int | None = Field(default=None, ge=1, le=50)


class ResearchResponse(BaseModel):
    """研究任务的异步受理响应。"""

    research_id: str
    status: str
    message: str = ""


class ResearchResult(BaseModel):
    """一次研究的完整结果。"""

    research_id: str
    status: Literal["completed", "failed", "running"] = "completed"
    question: str
    report: str = ""
    sources: list[Source] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class HealthResponse(BaseModel):
    """健康检查。"""

    status: str
    app: str
    version: str
    llm_provider: str
    search_provider: str
    vector_backend: str
    embedding_provider: str


# ---------------------------------------------------------------------------
# 知识库（Document Ingestion）
# ---------------------------------------------------------------------------


class KnowledgeDocument(BaseModel):
    """知识库中文档摘要（按 doc_id 聚合）。"""

    document_id: str
    title: str = ""
    source: str = ""
    file_type: Literal["txt", "markdown", "pdf", "html"] = "txt"
    page_count: int = 0
    chunk_count: int = 0


class KnowledgeUploadResponse(BaseModel):
    """文件上传入库响应。"""

    document_id: str
    title: str
    file_type: str
    chunks: int
    message: str = ""


class KnowledgeIndexRequest(BaseModel):
    """从文本或 URL 入库。"""

    text: str | None = Field(default=None, description="纯文本/Markdown 内容（text 与 url 二选一）")
    url: str | None = Field(default=None, description="抓取的网页地址")
    source: str = Field(default="", description="来源标识（默认用 url 或自动生成）")
    title: str = Field(default="", description="标题（缺省从内容/文件名推导）")
    file_type: Literal["txt", "markdown", "html"] = "txt"


class KnowledgeTestRequest(BaseModel):
    """知识库检索测试。"""

    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeTestResponse(BaseModel):
    """检索测试结果（各阶段明细）。"""

    query: str
    dense: list[dict[str, Any]] = Field(default_factory=list)
    bm25: list[dict[str, Any]] = Field(default_factory=list)
    hybrid: list[dict[str, Any]] = Field(default_factory=list)
    reranked: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeDeleteResponse(BaseModel):
    """删除文档响应。"""

    document_id: str
    deleted_chunks: int
    message: str = ""

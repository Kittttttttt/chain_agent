"""集中式配置管理。

所有配置均来自环境变量 / `.env` 文件，通过 Pydantic Settings 加载，
禁止在业务代码中硬编码任何 API Key 或连接地址。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录 = backend/ 的上一级
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT.parent / ".env"

# 当以 `uvicorn app.main:app` 从 backend 目录启动时，.env 位于项目根；兼容两种场景
_ENV_CANDIDATES = [ENV_FILE, PROJECT_ROOT / ".env"]


class Settings(BaseSettings):
    """应用全局配置。"""

    model_config = SettingsConfigDict(
        env_file=[str(p) for p in _ENV_CANDIDATES if p.exists()],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 基础 ----------
    app_name: str = "DeepResearch Agent"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, description="调试模式")
    log_level: str = "INFO"

    # ---------- LLM 提供商 ----------
    # 默认使用 DeepSeek（.env 中已配置），其余提供商按需配置后切换
    llm_provider: Literal["deepseek", "openai", "anthropic", "qwen", "ollama", "mock"] = "deepseek"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    dashscope_api_key: str = ""          # 通义千问（Qwen）与 DashScope Embedding 共用
    qwen_model: str = "qwen-plus"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout: float = 120.0

    # ---------- 搜索 ----------
    # search_provider: duckduckgo(默认, 免key) / tavily
    search_provider: Literal["duckduckgo", "tavily"] = "duckduckgo"
    tavily_api_key: str = ""
    tavily_max_results: int = 5
    ddg_max_results: int = 5

    # ---------- RAG / 向量库 ----------
    # embedding_provider: dashscope(推荐外部API) / openai / ollama / mock(测试兜底)
    embedding_provider: Literal["dashscope", "openai", "ollama", "mock"] = "mock"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024
    embedding_batch_size: int = 16

    # Qdrant：URL 为空时使用本地模式(local path)，并自动回退到内存向量库
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_path: str = "data/qdrant"
    qdrant_collection: str = "research_documents"
    vector_backend: Literal["auto", "qdrant", "memory"] = "auto"

    # RAG 检索参数
    rag_top_k: int = 5
    rag_dense_weight: float = 0.5
    rag_bm25_weight: float = 0.5
    rag_rerank_top_k: int = 3
    chunk_size: int = 512
    chunk_overlap: int = 64

    # ---------- 记忆 / 存储 ----------
    # memory_backend: sqlite(默认, 开箱即用) / postgres
    memory_backend: Literal["sqlite", "postgres"] = "sqlite"
    database_url: str = ""  # 配置 PostgreSQL DSN 时自动切换，如 postgresql://user:pass@host:5432/db
    sqlite_path: str = "data/deepresearch.db"
    memory_top_k: int = 5
    context_max_tokens: int = 8000

    # ---------- Agent 运行参数 ----------
    max_iterations: int = 8
    agent_timeout_seconds: float = 600.0
    sufficiency_threshold: float = 0.6
    dedupe_queries: bool = True
    trace_enabled: bool = True  # LangSmith tracing 总开关

    # ---------- LangSmith 观测性 ----------
    # 字段名与 .env 中的 LANGSMITH_* 环境变量一一对应（pydantic-settings 自动读取）
    langsmith_tracing: bool = True   # 对应 LANGSMITH_TRACING
    langsmith_api_key: str = ""      # 对应 LANGSMITH_API_KEY
    langsmith_project: str = "deepresearch-agent"  # 对应 LANGSMITH_PROJECT

    # ---------- MCP ----------
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 9000

    # ---------- FastAPI ----------
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def is_tavily_configured(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def is_llm_configured(self) -> bool:
        if self.llm_provider == "mock":
            return True
        key_map = {
            "deepseek": self.deepseek_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "qwen": self.dashscope_api_key,
            "ollama": True,
        }
        return bool(key_map.get(self.llm_provider))


@lru_cache
def get_settings() -> Settings:
    """缓存单例配置。"""
    return Settings()

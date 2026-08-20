"""Research Tools：Web 搜索 / ArXiv / GitHub / 网页阅读 / 文档检索。

每个 Tool 均继承 `BaseResearchTool`，具备：
- Pydantic 输入 Schema 与校验
- 结构化输出（ToolResult）
- 异常处理 / 重试 / 超时
- Tool Call 记录（由调用方在 ToolResult 中消费）
"""
from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.tools.base import BaseResearchTool, ToolResult
from app.tools.web_search import SearchProvider, build_search_provider


# ---------------------------------------------------------------------------
# 1. Web Search
# ---------------------------------------------------------------------------


class SearchWebInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=5, ge=1, le=10)


class SearchWebTool(BaseResearchTool):
    name = "search_web"
    description = "在互联网上搜索最新信息。适合查找时效性强、开放领域的内容。"
    args_schema = SearchWebInput

    def __init__(
        self,
        provider: SearchProvider | None = None,
        max_results: int = 5,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds, max_retries=max_retries)
        self._provider = provider
        self._max_results = max_results

    def _execute(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        provider = self._provider
        if provider is None:
            from app.config import get_settings

            s = get_settings()
            provider = build_search_provider(
                s.search_provider, s.tavily_api_key, s.tavily_max_results
            )
        results = provider.search(query, max_results=max_results)
        return [r.to_dict() for r in results]


# ---------------------------------------------------------------------------
# 2. ArXiv
# ---------------------------------------------------------------------------


class SearchArxivInput(BaseModel):
    query: str = Field(description="ArXiv 论文检索关键词（标题或摘要）")
    max_results: int = Field(default=5, ge=1, le=20)


class SearchArxivTool(BaseResearchTool):
    name = "search_arxiv"
    description = "在 arXiv 学术论文库中检索论文，返回标题、作者、摘要与链接。适合科研类问题。"
    args_schema = SearchArxivInput

    def _execute(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        import xml.etree.ElementTree as ET

        import httpx

        # arXiv API：https://export.arxiv.org/api/query
        url = "https://export.arxiv.org/api/query"
        params = {"search_query": f"all:{query}", "start": 0, "max_results": max_results}
        resp = httpx.get(url, params=params, timeout=self.timeout_seconds)
        resp.raise_for_status()

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(resp.text)
        items: list[dict[str, Any]] = []
        for entry in root.findall("atom:entry", ns)[:max_results]:
            title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
            summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
            link_el = entry.find("atom:id", ns)
            items.append(
                {
                    "title": title,
                    "url": link_el.text if link_el is not None else "",
                    "snippet": summary[:500],
                    "published_at": entry.findtext("atom:published", "", ns),
                }
            )
        return items


# ---------------------------------------------------------------------------
# 3. GitHub
# ---------------------------------------------------------------------------


class SearchGithubInput(BaseModel):
    query: str = Field(description="GitHub 仓库检索关键词")
    max_results: int = Field(default=5, ge=1, le=20)


class SearchGithubTool(BaseResearchTool):
    name = "search_github"
    description = "在 GitHub 上检索相关开源仓库，返回仓库名、描述、Stars 与地址。适合工程/代码类问题。"
    args_schema = SearchGithubInput

    def _execute(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        import httpx

        url = "https://api.github.com/search/repositories"
        params = {"q": query, "per_page": max_results, "sort": "stars"}
        resp = httpx.get(url, params=params, timeout=self.timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        items: list[dict[str, Any]] = []
        for repo in data.get("items", [])[:max_results]:
            items.append(
                {
                    "title": repo.get("full_name", ""),
                    "url": repo.get("html_url", ""),
                    "snippet": repo.get("description") or "",
                    "metadata": {"stars": repo.get("stargazers_count")},
                }
            )
        return items


# ---------------------------------------------------------------------------
# 4. Web Reader
# ---------------------------------------------------------------------------


class ReadWebpageInput(BaseModel):
    url: str = Field(description="需要阅读的网页地址")


class ReadWebpageTool(BaseResearchTool):
    name = "read_webpage"
    description = "读取一个网页的正文内容（自动提取标题与主要文本，截断到合理长度）。"
    args_schema = ReadWebpageInput

    def _execute(self, url: str) -> dict[str, Any]:
        import re

        import httpx

        resp = httpx.get(url, timeout=self.timeout_seconds, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else url

        # 简单正文提取：去脚本/样式，压缩空白
        text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        max_chars = 8000
        truncated = len(text) > max_chars
        return {"title": title, "url": url, "content": text[:max_chars], "truncated": truncated}


# ---------------------------------------------------------------------------
# 5. RAG Retrieval
# ---------------------------------------------------------------------------


class RetrieveDocumentsInput(BaseModel):
    query: str = Field(description="检索问题或关键词")
    top_k: int = Field(default=5, ge=1, le=20)


class RetrieveDocumentsTool(BaseResearchTool):
    name = "retrieve_documents"
    description = "在已收集的文档语料库中进行混合检索（向量 + BM25 + Rerank），返回最相关的片段。"
    args_schema = RetrieveDocumentsInput

    def __init__(self, rag_pipeline: Any = None, top_k: int = 5, include_detail: bool = True) -> None:
        super().__init__()
        self._pipeline = rag_pipeline
        self._top_k = top_k
        self._include_detail = include_detail

    def _execute(self, query: str, top_k: int = 5) -> dict[str, Any]:
        if self._pipeline is None:
            from app.rag.pipeline import get_rag_pipeline

            self._pipeline = get_rag_pipeline()
        if self._include_detail:
            detail = self._pipeline.retrieve_detailed(query, top_k=top_k)
            return {"results": detail["reranked"], "detail": detail}
        results = self._pipeline.retrieve(query, top_k=top_k)
        return {"results": [r.to_dict() for r in results]}

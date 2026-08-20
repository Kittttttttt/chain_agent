"""Tool Registry：集中注册与管理所有 Research Tool。"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.tools.base import BaseResearchTool
from app.tools.research import (
    ReadWebpageTool,
    RetrieveDocumentsTool,
    SearchArxivTool,
    SearchGithubTool,
    SearchWebTool,
)
from app.tools.web_search import SearchProvider, build_search_provider


def build_default_tools(
    provider: SearchProvider | None = None,
    rag_pipeline: Any = None,
    search_provider_name: str = "duckduckgo",
    tavily_api_key: str = "",
    max_results: int = 5,
) -> list[BaseResearchTool]:
    """构建默认工具集。

    provider 传入时优先使用；否则按配置自动构建搜索 Provider（可插拔）。
    """
    if provider is None:
        provider = build_search_provider(search_provider_name, tavily_api_key, max_results)

    tools: list[BaseResearchTool] = [
        SearchWebTool(provider=provider, max_results=max_results),
        SearchArxivTool(),
        SearchGithubTool(),
        ReadWebpageTool(),
        RetrieveDocumentsTool(rag_pipeline=rag_pipeline),
    ]
    logger.debug("构建工具集: {}", [t.name for t in tools])
    return tools


class ToolRegistry:
    """按名称索引工具，供 Agent 决策后调度。"""

    def __init__(self, tools: list[BaseResearchTool]) -> None:
        self._tools: dict[str, BaseResearchTool] = {t.name: t for t in tools}

    def get(self, name: str) -> BaseResearchTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def to_langchain_tools(self) -> list[Any]:
        return [t.to_langchain_tool() for t in self._tools.values()]

    @property
    def tools(self) -> list[BaseResearchTool]:
        return list(self._tools.values())


_default_registry: ToolRegistry | None = None


def get_default_registry() -> ToolRegistry:
    """全局默认注册表（懒加载）。"""
    global _default_registry
    if _default_registry is None:
        from app.config import get_settings

        s = get_settings()
        _default_registry = ToolRegistry(
            build_default_tools(
                search_provider_name=s.search_provider,
                tavily_api_key=s.tavily_api_key,
                max_results=s.tavily_max_results,
            )
        )
    return _default_registry

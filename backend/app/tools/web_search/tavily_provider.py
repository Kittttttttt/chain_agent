"""Tavily 搜索 Provider（需要 TAVILY_API_KEY）。"""
from __future__ import annotations

from loguru import logger

from app.tools.web_search.base import SearchProvider, SearchResult
from app.tools.web_search.duckduckgo_provider import DuckDuckGoProvider


class TavilyProvider(SearchProvider):
    """基于 Tavily Search API 的实现。"""

    name = "tavily"
    _URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        import httpx

        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(self._URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
        results: list[SearchResult] = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                )
            )
        return results


def build_search_provider(
    provider: str, tavily_api_key: str = "", max_results: int = 5
) -> SearchProvider:
    """根据配置构建搜索 Provider（可插拔切换）。"""
    if provider == "tavily" and tavily_api_key:
        logger.info("使用 Tavily 搜索 Provider")
        return TavilyProvider(api_key=tavily_api_key)
    logger.info("使用 DuckDuckGo 搜索 Provider（免 Key）")
    return DuckDuckGoProvider()

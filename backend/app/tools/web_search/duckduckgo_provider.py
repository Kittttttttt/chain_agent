"""DuckDuckGo 搜索 Provider（自实现，免 API Key）。

通过 DuckDuckGo HTML 端点获取结果并使用正则解析，避免额外依赖。
注：该方式用于教学/演示；生产环境建议切换 Tavily。
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any

import httpx
from loguru import logger

from app.tools.web_search.base import SearchProvider, SearchResult


class DuckDuckGoProvider(SearchProvider):
    """基于 DuckDuckGo HTML 的轻量搜索实现。"""

    name = "duckduckgo"
    _SEARCH_URL = "https://html.duckduckgo.com/html/"
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        params = {"q": query, "kl": "us-en"}
        headers = {"User-Agent": self._UA}
        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            resp = client.get(self._SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
        return self._parse(resp.text, max_results=max_results)

    def _parse(self, html: str, max_results: int) -> list[SearchResult]:
        """解析 DuckDuckGo HTML 结果块（result__a 与 result__snippet）。"""
        results: list[SearchResult] = []
        # 每个结果块
        blocks = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
        snippets = re.findall(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
        for idx, (href, title_html) in enumerate(blocks[:max_results]):
            url = self._clean_url(href)
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            snippet = ""
            if idx < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[idx]).strip()
            if url:
                results.append(SearchResult(title=title, url=url, snippet=snippet))
        return results

    @staticmethod
    def _clean_url(raw: str) -> str:
        """DuckDuckGo 返回的是重定向链接，提取真实 URL。"""
        parsed = urllib.parse.urlparse(raw)
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query and query["uddg"]:
            return query["uddg"][0]
        return raw

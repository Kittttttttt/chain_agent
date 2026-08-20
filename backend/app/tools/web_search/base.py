"""SearchProvider 接口：解耦搜索逻辑与具体供应商。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SearchResult:
    """统一搜索结果结构。"""

    __slots__ = ("title", "url", "snippet")

    def __init__(self, title: str, url: str, snippet: str = "") -> None:
        self.title = title
        self.url = url
        self.snippet = snippet

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}

    def __repr__(self) -> str:
        return f"SearchResult(title={self.title!r}, url={self.url!r})"


class SearchProvider(ABC):
    """搜索引擎抽象。实现 duckduckgo / tavily / 自定义供应商。"""

    name: str = "base"

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """执行搜索，返回结构化结果。"""
        raise NotImplementedError

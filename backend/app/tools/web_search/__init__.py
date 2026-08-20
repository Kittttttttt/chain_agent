"""Web 搜索相关工具与 Provider。"""
from app.tools.web_search.base import SearchProvider, SearchResult
from app.tools.web_search.tavily_provider import build_search_provider

__all__ = ["SearchProvider", "SearchResult", "build_search_provider"]

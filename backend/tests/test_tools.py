"""Tool 层测试：Schema 校验、错误处理、结构化输出。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402
import pytest  # noqa: E402

from app.tools.base import ToolResult  # noqa: E402
from app.tools.research import SearchWebTool  # noqa: E402
from app.tools.web_search.base import SearchResult, SearchProvider  # noqa: E402


class FakeProvider(SearchProvider):
    name = "fake"

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return [SearchResult(title=f"r{i}", url=f"https://x.com/{i}", snippet="s") for i in range(max_results)]


def test_search_web_returns_structured_result():
    tool = SearchWebTool(provider=FakeProvider())
    result = tool.invoke(query="test", max_results=3)
    assert isinstance(result, ToolResult)
    assert result.success
    assert len(result.data) == 3
    assert result.data[0]["url"].startswith("https://")


def test_args_schema_validation():
    tool = SearchWebTool(provider=FakeProvider())
    with pytest.raises(ValidationError):
        tool.invoke(query="", max_results=100)


def test_tool_error_handling():
    class BoomProvider(SearchProvider):
        name = "boom"

        def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
            raise RuntimeError("boom")

    tool = SearchWebTool(provider=BoomProvider(), max_retries=1)
    result = tool.invoke(query="x")
    assert not result.success
    assert "boom" in (result.error or "")
    assert result.retries == 1

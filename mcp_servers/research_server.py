"""FastMCP 服务：将 Research Tools 以 MCP 协议暴露。

运行：python -m mcp_servers.research_server
或：  fastmcp run mcp_servers/research_server.py

Agent 可通过 langchain-mcp-adapters 的 load_mcp_tools 动态发现并调用这些工具，
从而体现 MCP 作为独立 Tool 接入机制（而非硬编码工具）的设计。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证 backend 可被 import
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastmcp import FastMCP  # noqa: E402
from loguru import logger  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.tools.web_search import build_search_provider  # noqa: E402

mcp = FastMCP("DeepResearch MCP Server")


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """在互联网上搜索信息，返回标题、链接与摘要。"""
    s = get_settings()
    provider = build_search_provider(s.search_provider, s.tavily_api_key, s.tavily_max_results)
    return [r.to_dict() for r in provider.search(query, max_results=max_results)]


@mcp.tool()
def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """检索 arXiv 学术论文。"""
    import xml.etree.ElementTree as ET

    import httpx

    resp = httpx.get(
        "https://export.arxiv.org/api/query",
        params={"search_query": f"all:{query}", "max_results": max_results},
        timeout=30,
    )
    resp.raise_for_status()
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    out = []
    for entry in root.findall("atom:entry", ns)[:max_results]:
        out.append(
            {
                "title": entry.findtext("atom:title", "", ns).strip(),
                "url": (entry.find("atom:id", ns).text if entry.find("atom:id", ns) is not None else ""),
                "snippet": entry.findtext("atom:summary", "", ns).strip()[:500],
            }
        )
    return out


@mcp.tool()
def search_github(query: str, max_results: int = 5) -> list[dict]:
    """检索 GitHub 开源仓库。"""
    import httpx

    resp = httpx.get(
        "https://api.github.com/search/repositories",
        params={"q": query, "per_page": max_results, "sort": "stars"},
        timeout=30,
    )
    resp.raise_for_status()
    return [
        {
            "title": r.get("full_name", ""),
            "url": r.get("html_url", ""),
            "snippet": r.get("description") or "",
        }
        for r in resp.json().get("items", [])[:max_results]
    ]


@mcp.tool()
def read_webpage(url: str) -> dict:
    """读取网页正文并提取标题。"""
    import re

    import httpx

    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "title": title.group(1).strip() if title else url,
        "url": url,
        "content": text[:8000],
    }


if __name__ == "__main__":
    s = get_settings()
    logger.info("启动 MCP Server: {}:{}", s.mcp_server_host, s.mcp_server_port)
    mcp.run(transport="sse", host=s.mcp_server_host, port=s.mcp_server_port)

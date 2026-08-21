"""统一 Document Loader：TXT / Markdown / PDF / HTML / URL → Document。

设计要点：
- 只依赖标准库 + pypdf（PDF 解析），不引入 LangChain / Unstructured
- 统一输出 Document(text, metadata)，metadata 含 source/title/file_type/page/url
- PDF 按页拆分为多个 Document，每页记录 page 序号，保证 Citation 可追溯原文
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from loguru import logger


@dataclass
class Document:
    """加载后的文档单元（PDF 一页一个 Document）。"""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        return str(self.metadata.get("doc_id", ""))


class _HtmlTextExtractor(HTMLParser):
    """轻量 HTML 正文提取器（标准库实现，去 script/style/标签，压缩空白）。"""

    _SKIP_TAGS = {"script", "style", "noscript", "template", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        import re

        raw = " ".join(self._parts)
        # 压缩多余空行：保留段落边界
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return raw.strip()


def _guess_file_type(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".md") or name.endswith(".markdown"):
        return "markdown"
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".html", ".htm")):
        return "html"
    return "txt"


def load_file(filename: str, content: bytes, *, source: str = "", doc_id: str = "") -> list[Document]:
    """按扩展名解析文件内容为 Document 列表。

    Args:
        filename: 文件名（决定解析方式）
        content: 文件字节内容
        source: 来源标识（如原始路径 / URL），缺省用 filename
        doc_id: 文档唯一 ID（缺省自动生成）

    Returns:
        list[Document]：TXT/MD/HTML 返回 1 个；PDF 每页 1 个

    Raises:
        ValueError: 未知格式或内容为空
    """
    file_type = _guess_file_type(filename)
    source = source or filename
    title = _title_from_filename(filename)

    if file_type == "txt":
        text = content.decode("utf-8", errors="replace")
        docs = [Document(text=text, metadata={"source": source, "title": title, "file_type": "txt", "page": None})]
    elif file_type == "markdown":
        text = content.decode("utf-8", errors="replace")
        docs = [Document(text=text, metadata={"source": source, "title": title, "file_type": "markdown", "page": None})]
    elif file_type == "html":
        html = content.decode("utf-8", errors="replace")
        docs = [_from_html(html, source=source, title=title)]
    elif file_type == "pdf":
        docs = _from_pdf(content, source=source, title=title)
    else:  # pragma: no cover - _guess_file_type 已收敛
        raise ValueError(f"不支持的文件类型: {file_type}")

    docs = [d for d in docs if d.text.strip()]
    if not docs:
        raise ValueError(f"文档内容为空或无法解析: {filename}")

    # 统一注入 doc_id（保证同一文档的所有 Document/chunk 可追溯）
    for d in docs:
        d.metadata["doc_id"] = doc_id or _stable_doc_id(d.metadata["source"], title)
    logger.info("加载文件 {}: {} 个 Document ({})", filename, len(docs), file_type)
    return docs


def load_text(text: str, *, source: str = "memory", title: str = "text", file_type: str = "txt", doc_id: str = "") -> list[Document]:
    """直接加载纯文本（供 API / 测试使用）。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("文本内容为空")
    return [
        Document(
            text=text,
            metadata={
                "source": source,
                "title": title,
                "file_type": file_type,
                "page": None,
                "doc_id": doc_id or _stable_doc_id(source, title),
            },
        )
    ]


def load_url(url: str, *, timeout: float = 20.0) -> list[Document]:
    """抓取 URL 并解析为 Document（轻量 HTML parser，无第三方依赖）。"""
    import httpx

    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    docs = [_from_html(html, source=url, title=url)]
    docs = [d for d in docs if d.text.strip()]
    if not docs:
        raise ValueError(f"URL 内容为空或无法解析: {url}")
    docs[0].metadata["doc_id"] = _stable_doc_id(url, docs[0].metadata.get("title", ""))
    return docs


# ---------------------------------------------------------------------------
# 内部实现
# ---------------------------------------------------------------------------


def _from_html(html: str, *, source: str, title: str) -> Document:
    import re

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    parsed_title = title_match.group(1).strip() if title_match else title
    extractor = _HtmlTextExtractor()
    try:
        extractor.feed(html)
    except Exception as exc:  # noqa: BLE001 - 容错：HTML 不规范时降级为正则清洗
        logger.warning("HTML 解析降级为正则清洗: {}", exc)
        import re as _re

        text = _re.sub(r"<[^>]+>", " ", html)
        text = _re.sub(r"\s+", " ", text).strip()
        extractor = _HtmlTextExtractor()
        extractor._parts = [text]  # noqa: SLF001
    return Document(text=extractor.text(), metadata={"source": source, "title": parsed_title, "file_type": "html", "page": None})


def _from_pdf(content: bytes, *, source: str, title: str) -> list[Document]:
    from pypdf import PdfReader

    reader = PdfReader(__import__("io").BytesIO(content))
    docs: list[Document] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = " ".join(text.split()).strip()
        docs.append(
            Document(
                text=text,
                metadata={"source": source, "title": title, "file_type": "pdf", "page": i + 1},
            )
        )
    return docs


def _stable_doc_id(source: str, title: str) -> str:
    """由 source+title 生成稳定的文档 ID（uuid5），避免重复上传产生重复文档。"""
    import hashlib
    import re

    raw = f"{source}|{title}".strip().lower()
    raw = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", raw).strip("-")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _title_from_filename(filename: str) -> str:
    from pathlib import Path

    return Path(filename).stem or "untitled"


def is_supported_filename(filename: str) -> bool:
    """文件扩展名是否受支持。"""
    return _guess_file_type(filename) in ("txt", "markdown", "pdf", "html")

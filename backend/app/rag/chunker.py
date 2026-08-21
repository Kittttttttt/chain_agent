"""文档切分：解析 → 清洗 → 标题/段落/句子/固定长度多级切块。

设计要点：
- `recursive_chunk_text`：兼容旧版递归切块（句子 → 词），供既有逻辑/测试使用
- `chunk_document`：文档级切块入口。按「标题 → 段落 → 句子 → 固定长度」逐级切分，
  优先保留语义完整边界；每个 chunk 携带 doc_id/source/title/file_type/page/chunk_id
  等溯源 metadata，保证后续 Citation 能追溯到原文。
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.rag.docloader import Document

# Markdown 标题行：# 一级标题、## 二级……
_TITLE_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")

# 空行分隔段落
_PARA_SPLIT_RE = re.compile(r"\n\s*\n+")


def parse_document(text: str) -> str:
    """基础清洗：去重空白、HTML 标签残留等。"""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def recursive_chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[str]:
    """按段落/句子/词三级递归切块，尽量保留语义完整性。"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks: list[str] = []
    # 1) 先按句子拆
    sentences = re.split(r"(?<=[。.!?；;])|\n", text)
    current = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) > chunk_size:
            # 超长句子再按词切
            for piece in _chunk_by_words(sent, chunk_size, chunk_overlap):
                chunks.append(piece)
            current = ""
            continue
        if len(current) + len(sent) + 1 > chunk_size:
            if current:
                chunks.append(current.strip())
            current = sent
        else:
            current = (current + " " + sent).strip()
    if current:
        chunks.append(current.strip())

    # 2) 加 overlap：将相邻 chunk 尾/首重叠拼接
    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = []
        for i, c in enumerate(chunks):
            if i == 0:
                overlapped.append(c)
            else:
                prev = chunks[i - 1]
                overlap_text = prev[-chunk_overlap:] if prev else ""
                overlapped.append((overlap_text + " " + c).strip())
        chunks = overlapped

    logger.debug("切分为 {} 个 chunk", len(chunks))
    return chunks


def chunk_document(
    doc: Document,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[dict[str, Any]]:
    """文档级多级切块：标题 → 段落 → 句子 → 固定长度。

    Returns:
        形如 [{"text": ..., "metadata": {...}}] 的 chunk 列表；
        metadata 必含 doc_id / source / title / file_type / page / chunk_id / chunk_index。
    """
    base = {
        "doc_id": doc.metadata.get("doc_id", ""),
        "source": doc.metadata.get("source", ""),
        "title": doc.metadata.get("title", ""),
        "file_type": doc.metadata.get("file_type", "txt"),
        "page": doc.metadata.get("page"),
        "url": doc.metadata.get("url", ""),
    }
    text = parse_document(doc.text)
    if not text:
        return []

    sections = _split_by_heading(text)

    chunks: list[dict[str, Any]] = []
    for section_text in sections:
        # 段落级：空行拆分；段落过大再走句子/词递归切块
        paragraphs = _split_paragraphs(section_text)
        current = ""
        for para in paragraphs:
            if not para:
                continue
            if len(para) > chunk_size:
                if current:
                    chunks.append(current)
                    current = ""
                for piece in recursive_chunk_text(para, chunk_size, chunk_overlap):
                    chunks.append(piece)
                continue
            if len(current) + len(para) + 1 > chunk_size:
                if current:
                    chunks.append(current)
                current = para
            else:
                current = (current + " " + para).strip()
        if current:
            chunks.append(current)

    # 去重 + 组装 metadata
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for i, text_chunk in enumerate(chunks):
        text_chunk = text_chunk.strip()
        if not text_chunk or text_chunk in seen:
            continue
        seen.add(text_chunk)
        page = base.get("page")
        page_tag = f"p{page}" if page else "p0"
        result.append(
            {
                "text": text_chunk,
                "metadata": {
                    **base,
                    "chunk_index": i,
                    "chunk_id": f"{base['doc_id']}-{page_tag}-c{i}",
                },
            }
        )
    logger.debug("文档 {} 切分为 {} 个 chunk", base.get("doc_id"), len(result))
    return result


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _split_by_heading(text: str) -> list[str]:
    """按 Markdown 标题切分：每个标题开启新 section，标题行保留在 section 开头。"""
    lines = text.split("\n")
    sections: list[str] = []
    current: list[str] = []
    for line in lines:
        if _TITLE_RE.match(line):
            if current and any(l.strip() for l in current):
                sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current and any(l.strip() for l in current):
        sections.append("\n".join(current).strip())
    # 无任何标题命中 → 整篇作为一个 section
    return sections or [text]


def _split_paragraphs(text: str) -> list[str]:
    """按空行拆段落（中英混合）。"""
    return [p.strip() for p in _PARA_SPLIT_RE.split(text)]


def _chunk_by_words(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    pieces: list[str] = []
    i = 0
    while i < len(words):
        piece = " ".join(words[i : i + chunk_size])
        pieces.append(piece)
        i += max(1, chunk_size - overlap)
    return pieces

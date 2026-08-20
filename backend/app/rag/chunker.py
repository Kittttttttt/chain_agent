"""文档切分：解析 → 清洗 → 语义/递归切块。"""
from __future__ import annotations

import re

from loguru import logger


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


def _chunk_by_words(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    pieces: list[str] = []
    i = 0
    while i < len(words):
        piece = " ".join(words[i : i + chunk_size])
        pieces.append(piece)
        i += max(1, chunk_size - overlap)
    return pieces

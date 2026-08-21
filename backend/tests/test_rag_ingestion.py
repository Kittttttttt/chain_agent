"""RAG Document Ingestion 最小单元测试。

覆盖：
- TXT / Markdown / PDF 的解析（loader）
- 三类文档的入库流程（Loader → Cleaning → Chunking → Embedding → VectorStore + BM25）
- chunk 溯源 metadata（doc_id / source / page / chunk_id）
- 按 doc_id 删除文档
- 检索可追溯（document_id / chunk_id）

使用内存向量库 + MockEmbedding，不依赖 Qdrant / 外部 API，保证测试快速稳定。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.rag.chunker import chunk_document  # noqa: E402
from app.rag.docloader import Document, load_file, load_text  # noqa: E402
from app.rag.embedding import MockEmbeddingProvider  # noqa: E402
from app.rag.pipeline import RAGPipeline  # noqa: E402
from app.rag.vectorstore import MemoryVectorStore  # noqa: E402


@pytest.fixture()
def pipeline() -> RAGPipeline:
    """内存向量库 + Mock 嵌入的隔离 pipeline。"""
    return RAGPipeline(
        embedding=MockEmbeddingProvider(dimension=256),
        vector_store=MemoryVectorStore(dimension=256),
        chunk_size=64,  # 小 chunk_size 便于触发切块
        chunk_overlap=8,
        top_k=5,
        rerank_top_k=3,
    )


TXT_TEXT = (
    "Retrieval Augmented Generation is a technique that combines retrieval with "
    "generation. It fetches relevant documents from a knowledge base before answering. "
    "This improves answer accuracy and reduces hallucination."
)


def test_txt_parse_and_index(pipeline: RAGPipeline) -> None:
    """TXT：解析 → 入库 → 可检索。"""
    docs = load_text(TXT_TEXT, source="test.txt", title="TXT Test", doc_id="txt-doc-1")
    assert len(docs) == 1
    assert docs[0].metadata["file_type"] == "txt"

    result = pipeline.add_documents(docs)
    assert result["document_id"] == "txt-doc-1"
    assert result["chunks"] >= 1

    hits = pipeline.retrieve("retrieval augmented generation", top_k=5)
    assert hits, "入库后应能检索到内容"
    assert hits[0].metadata.get("doc_id") == "txt-doc-1"


MARKDOWN_TEXT = (
    "# RAG 混合检索\n\n"
    "混合检索结合稠密向量检索与 BM25 稀疏检索。\n\n"
    "## Dense Retrieval\n\n"
    "稠密检索使用向量相似度匹配语义相关内容。\n\n"
    "## BM25\n\n"
    "BM25 是基于词频的经典稀疏检索算法。\n"
)


def test_markdown_parse_and_chunk_by_heading(pipeline: RAGPipeline) -> None:
    """Markdown：按标题切块（标题 → 段落），chunk 保留溯源 metadata。"""
    docs = load_file("guide.md", MARKDOWN_TEXT.encode("utf-8"), source="guide.md", doc_id="md-doc-1")
    assert len(docs) == 1
    assert docs[0].metadata["file_type"] == "markdown"

    chunks = chunk_document(docs[0], chunk_size=64, chunk_overlap=8)
    assert len(chunks) >= 2, "按标题应切出多个 chunk"
    for chunk in chunks:
        meta = chunk["metadata"]
        assert meta["doc_id"] == "md-doc-1"
        assert meta["source"] == "guide.md"
        assert meta["chunk_id"].startswith("md-doc-1-")
        assert "chunk_index" in meta

    result = pipeline.add_documents(docs)
    assert result["chunks"] == len(chunks)

    hits = pipeline.retrieve("BM25 稀疏检索算法", top_k=5)
    assert hits
    top1_meta = hits[0].metadata
    assert top1_meta.get("doc_id") == "md-doc-1"
    assert "BM25" in hits[0].text or "BM25" in " ".join(h.text for h in hits[:2])


def _make_pdf_bytes() -> bytes:
    """构建一个 2 页、含真实文本的合法 PDF（手工生成 xref，仅依赖 pypdf 读取）。"""
    page1 = b"BT /F1 12 Tf 72 720 Td (Hello RAG Page One) Tj ET"
    page2 = b"BT /F1 12 Tf 72 720 Td (Hello Rerank Page Two) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 7 0 R >> >> >>",
        b"<< /Length " + str(len(page1)).encode() + b" >>\nstream\n" + page1 + b"\nendstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>",
        b"<< /Length " + str(len(page2)).encode() + b" >>\nstream\n" + page2 + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return out


def test_pdf_parse_page_metadata(pipeline: RAGPipeline) -> None:
    """PDF：pypdf 解析，每页一个 Document 且 page 正确。"""
    pypdf = pytest.importorskip("pypdf")
    content = _make_pdf_bytes()
    docs = load_file("paper.pdf", content, source="paper.pdf", doc_id="pdf-doc-1")
    assert docs, "应解析出至少一页"
    assert all(d.metadata["file_type"] == "pdf" for d in docs)
    assert all(isinstance(d.metadata["page"], int) for d in docs)
    assert [d.metadata["page"] for d in docs] == list(range(1, len(docs) + 1))


def test_pdf_ingestion(pipeline: RAGPipeline) -> None:
    """PDF：入库后可检索，Evidence 可追溯 document_id + chunk_id + page。"""
    pytest.importorskip("pypdf")
    content = _make_pdf_bytes()
    docs = load_file("paper.pdf", content, source="paper.pdf", doc_id="pdf-doc-1")
    result = pipeline.add_documents(docs)
    assert result["chunks"] >= 1

    hits = pipeline.retrieve("RAG", top_k=5)
    assert hits
    top1_meta = hits[0].metadata
    assert top1_meta.get("doc_id") == "pdf-doc-1"
    assert top1_meta.get("chunk_id", "").startswith("pdf-doc-1-")
    assert top1_meta.get("page") is not None


def test_delete_document(pipeline: RAGPipeline) -> None:
    """删除文档：向量库与检索结果同步移除。"""
    pipeline.add_documents(load_text(TXT_TEXT, source="t1.txt", title="T1", doc_id="del-doc"))
    pipeline.add_documents(load_text("Another unrelated text about cats and dogs.", source="t2.txt", title="T2", doc_id="keep-doc"))

    assert pipeline.count() >= 2
    removed = pipeline.delete_document("del-doc")
    assert removed >= 1

    hits = pipeline.retrieve("retrieval augmented generation", top_k=10)
    assert not any(h.metadata.get("doc_id") == "del-doc" for h in hits)
    assert pipeline.count() >= 1


def test_list_documents_aggregates(pipeline: RAGPipeline) -> None:
    """list_documents 按 doc_id 聚合 chunk 数。"""
    pipeline.add_documents(load_text(TXT_TEXT, source="t1.txt", title="T1", doc_id="agg-doc"))
    items = pipeline.list_documents()
    assert any(item["document_id"] == "agg-doc" and item["chunk_count"] >= 1 for item in items)

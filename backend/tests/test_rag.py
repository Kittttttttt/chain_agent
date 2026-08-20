"""RAG 流水线单元测试（使用 MockEmbedding + 内存向量库）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.bm25 import BM25Index  # noqa: E402
from app.rag.chunker import parse_document, recursive_chunk_text  # noqa: E402
from app.rag.embedding import MockEmbeddingProvider  # noqa: E402
from app.rag.hybrid import rrf_fusion  # noqa: E402
from app.rag.pipeline import RAGPipeline  # noqa: E402
from app.rag.vectorstore import MemoryVectorStore, StoredDocument  # noqa: E402


def test_chunker_keeps_semantics():
    text = "第一句关于深度学习。第二句关于强化学习。第三句关于自然语言处理。" * 30
    chunks = recursive_chunk_text(text, chunk_size=100, chunk_overlap=10)
    assert len(chunks) > 1
    joined = "".join(chunks)
    assert "深度学习" in joined


def test_parse_document_removes_html():
    dirty = "<html><body>你好<b>世界</b></body></html>"
    assert "你好 世界" in parse_document(dirty)


def test_mock_embedding_deterministic():
    emb = MockEmbeddingProvider()
    r1 = emb.embed_one("hello world")
    r2 = emb.embed_one("hello world")
    r3 = emb.embed_one("different text")
    assert r1.vector == r2.vector
    assert r1.vector != r3.vector


def test_memory_vector_store_search():
    store = MemoryVectorStore(dimension=8)
    emb = MockEmbeddingProvider(8)
    docs = [
        StoredDocument(id="a", text="cat", vector=emb.embed_one("cat").vector),
        StoredDocument(id="b", text="dog", vector=emb.embed_one("dog").vector),
        StoredDocument(id="c", text="car", vector=emb.embed_one("car").vector),
    ]
    store.add(docs)
    res = store.search(emb.embed_one("kitten").vector, top_k=2)
    assert res[0].id == "a"


def test_bm25_ranks_lexical_match():
    idx = BM25Index()
    idx.index(
        [
            {"id": "1", "text": "the cat sat on the mat"},
            {"id": "2", "text": "machine learning models are powerful"},
        ]
    )
    res = idx.search("cat mat", top_k=1)
    assert res[0].id == "1"


def test_rrf_fusion_merges_rankings():
    from app.rag.vectorstore import RetrievedChunk

    dense = [
        RetrievedChunk(id="a", text="", score=1.0),
        RetrievedChunk(id="b", text="", score=0.9),
    ]
    bm25 = [
        RetrievedChunk(id="b", text="", score=1.0),
        RetrievedChunk(id="c", text="", score=0.8),
    ]
    fused = rrf_fusion(dense, bm25)
    ids = [c.id for c in fused]
    assert "b" in ids and "a" in ids and "c" in ids
    assert ids[0] == "b"


def test_rag_pipeline_full_flow():
    pipeline = RAGPipeline(
        embedding=MockEmbeddingProvider(32),
        vector_store=MemoryVectorStore(dimension=32),
        chunk_size=100,
        chunk_overlap=10,
    )
    pipeline.add_document("LangGraph is a library for building stateful agents with graphs.", {"doc_id": "d1"})
    pipeline.add_document("Retrieval augmented generation combines search with generation.", {"doc_id": "d2"})
    results = pipeline.retrieve("what is LangGraph", top_k=2)
    assert len(results) > 0
    assert "LangGraph" in results[0].text

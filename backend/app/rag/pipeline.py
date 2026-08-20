"""RAG Pipeline：组装 Embedding / VectorStore / BM25 / Hybrid / Rerank。"""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from loguru import logger

from app.rag.bm25 import BM25Index
from app.rag.chunker import parse_document, recursive_chunk_text
from app.rag.embedding import EmbeddingProvider, build_embedding_provider
from app.rag.hybrid import rrf_fusion
from app.rag.reranker import EmbeddingReranker
from app.rag.vectorstore import RetrievedChunk, StoredDocument, VectorStore, build_vector_store


class RAGPipeline:
    """完整 RAG 流水线：

    Document → Parsing → Chunking → Embedding → VectorStore(+BM25)
    查询 → Dense + BM25 → RRF Fusion → Rerank → Context Selection
    """

    def __init__(
        self,
        embedding: EmbeddingProvider,
        vector_store: VectorStore,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        top_k: int = 5,
        rerank_top_k: int = 3,
    ) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._top_k = top_k
        self._rerank_top_k = rerank_top_k
        self._bm25 = BM25Index()
        self._bm25_docs: list[dict] = []
        self._reranker = EmbeddingReranker(
            embed_fn=lambda texts: [r.vector for r in self._embedding.embed(texts)]
        )

    # ------------------------------------------------------------------
    # 入库
    # ------------------------------------------------------------------
    def add_document(self, text: str, metadata: dict[str, Any] | None = None) -> int:
        """解析并切块，embedding 后入库（向量 + BM25 同步）。"""
        clean = parse_document(text)
        chunks = recursive_chunk_text(clean, self._chunk_size, self._chunk_overlap)
        if not chunks:
            return 0
        metadata = metadata or {}
        chunk_ids: list[str] = []
        stored: list[StoredDocument] = []
        for i, chunk in enumerate(chunks):
            cid = f"{metadata.get('doc_id', uuid.uuid4().hex)}-{i}"
            vec = self._embedding.embed_one(chunk).vector
            stored.append(
                StoredDocument(id=cid, text=chunk, vector=vec, metadata={**metadata, "chunk_index": i})
            )
            chunk_ids.append(cid)
        self._vector_store.add(stored)
        self._bm25_docs.extend(
            [
                {"id": cid, "text": chunk, "metadata": {**metadata, "chunk_index": i}}
                for cid, i, chunk in zip(chunk_ids, range(len(chunks)), chunks)
            ]
        )
        self._bm25.index(self._bm25_docs)
        logger.info("入库文档: {} chunks", len(chunks))
        return len(chunks)

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------
    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k or self._top_k
        q_vec = self._embedding.embed_one(query).vector

        dense = self._vector_store.search(q_vec, top_k=top_k * 3)
        bm25 = self._bm25.search(query, top_k=top_k * 3)
        fused = rrf_fusion(dense, bm25)
        reranked = self._reranker.rerank(query, fused, top_k=self._rerank_top_k)
        return reranked

    def retrieve_detailed(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        """检索并返回各阶段明细（Dense / BM25 / Hybrid / Reranked）。

        供前端 RAG 检索面板展示真实的分阶段结果，而非只给最终 Top-K。
        """
        top_k = top_k or self._top_k
        q_vec = self._embedding.embed_one(query).vector

        dense = self._vector_store.search(q_vec, top_k=top_k * 3)
        bm25 = self._bm25.search(query, top_k=top_k * 3)
        fused = rrf_fusion(dense, bm25)
        reranked = self._reranker.rerank(query, fused, top_k=self._rerank_top_k)
        return {
            "query": query,
            "dense": [c.to_dict() for c in dense],
            "bm25": [c.to_dict() for c in bm25],
            "hybrid": [c.to_dict() for c in fused],
            "reranked": [c.to_dict() for c in reranked],
        }

    def count(self) -> int:
        return self._vector_store.count()


@lru_cache
def get_rag_pipeline() -> RAGPipeline:
    """懒加载全局 RAG Pipeline（测试与无状态场景可直接复用）。"""
    from app.config import get_settings

    s = get_settings()
    embedding = build_embedding_provider(
        provider=s.embedding_provider,
        dashscope_api_key=s.dashscope_api_key,
        openai_api_key=s.openai_api_key,
        openai_base_url=s.openai_base_url,
        embedding_model=s.embedding_model,
        ollama_base_url=s.ollama_base_url,
    )
    vector_store = build_vector_store(
        backend=s.vector_backend,
        url=s.qdrant_url,
        api_key=s.qdrant_api_key,
        path=s.qdrant_path,
        collection=s.qdrant_collection,
        dimension=s.embedding_dim,
    )
    return RAGPipeline(
        embedding=embedding,
        vector_store=vector_store,
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
        top_k=s.rag_top_k,
        rerank_top_k=s.rag_rerank_top_k,
    )

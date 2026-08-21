"""RAG Pipeline：组装 Embedding / VectorStore / BM25 / Hybrid / Rerank。"""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from loguru import logger

from app.rag.bm25 import BM25Index
from app.rag.chunker import chunk_document, parse_document, recursive_chunk_text
from app.rag.docloader import Document
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
    def add_documents(self, docs: list[Document]) -> dict[str, Any]:
        """统一文档入库入口：Loader 产物 → Cleaning → Chunking → Embedding → Qdrant + BM25。

        禁止绕过本方法直接写 Qdrant。每个 chunk 携带 doc_id/source/title/file_type/
        page/chunk_id 溯源 metadata，保证后续 Evidence 可追溯原文。

        Returns:
            {"document_id": str, "title": str, "chunks": int, "message": str}
        """
        if not docs:
            raise ValueError("没有可入库的文档（输入为空）")
        stored_all: list[StoredDocument] = []
        bm25_entries: list[dict[str, Any]] = []
        chunk_total = 0
        for doc in docs:
            if not doc.text.strip():
                continue
            chunks = chunk_document(doc, self._chunk_size, self._chunk_overlap)
            if not chunks:
                continue
            for chunk in chunks:
                vec = self._embedding.embed_one(chunk["text"]).vector
                meta = dict(chunk["metadata"])
                stored_all.append(
                    StoredDocument(id=meta["chunk_id"], text=chunk["text"], vector=vec, metadata=meta)
                )
                bm25_entries.append({"id": meta["chunk_id"], "text": chunk["text"], "metadata": meta})
                chunk_total += 1
        if not stored_all:
            raise ValueError("文档切块后无有效内容，无法入库")
        self._vector_store.add(stored_all)
        self._bm25_docs.extend(bm25_entries)
        self._bm25.index(self._bm25_docs)
        first_meta = docs[0].metadata
        logger.info("入库文档 {}: {} chunks", first_meta.get("doc_id"), chunk_total)
        return {
            "document_id": str(first_meta.get("doc_id", "")),
            "title": str(first_meta.get("title", "")),
            "chunks": chunk_total,
            "message": f"入库成功，共 {chunk_total} 个 chunk",
        }

    def add_document(self, text: str, metadata: dict[str, Any] | None = None) -> int:
        """兼容旧接口：单文档文本入库（内部走统一 add_documents 入口）。"""
        metadata = metadata or {}
        doc = Document(
            text=text,
            metadata={
                "doc_id": metadata.get("doc_id", uuid.uuid4().hex),
                "source": metadata.get("source", metadata.get("doc_id", "memory")),
                "title": metadata.get("title", "untitled"),
                "file_type": metadata.get("file_type", "txt"),
                "page": metadata.get("page"),
            },
        )
        result = self.add_documents([doc])
        return int(result["chunks"])

    def list_documents(self) -> list[dict[str, Any]]:
        """按文档聚合列出知识库中所有文档（doc_id / title / source / file_type / page 数 / chunk 数）。

        从向量库全量扫描，兼容旧数据（无 doc_id metadata 时按 chunk id 前缀推导）。
        """
        docs_map: dict[str, dict[str, Any]] = {}
        for stored in self._vector_store.all_docs():
            meta = stored.metadata
            doc_id = meta.get("doc_id") or _derive_doc_id(stored.id)
            entry = docs_map.setdefault(
                doc_id,
                {
                    "document_id": doc_id,
                    "title": meta.get("title") or _derive_title(doc_id),
                    "source": meta.get("source", ""),
                    "file_type": meta.get("file_type", "txt"),
                    "page_count": 0,
                    "chunk_count": 0,
                },
            )
            entry["chunk_count"] += 1
            page = meta.get("page")
            if isinstance(page, int) and page > entry["page_count"]:
                entry["page_count"] = page
        items = sorted(docs_map.values(), key=lambda x: x["document_id"])
        logger.info("知识库文档列表: {} 篇", len(items))
        return items

    def delete_document(self, doc_id: str) -> int:
        """删除指定文档全部 chunk（Qdrant + BM25 同步），返回删除条数。"""
        removed = self._vector_store.delete_by_doc_id(doc_id)
        if removed:
            self._bm25_docs = [d for d in self._bm25_docs if d.get("metadata", {}).get("doc_id") != doc_id]
            # 兼容旧数据：BM25 条目 metadata 缺失 doc_id 时按 chunk_id 前缀兜底
            self._bm25_docs = [
                d for d in self._bm25_docs
                if not (_derive_doc_id(d.get("id", "")) == doc_id and d.get("metadata", {}).get("doc_id") is None)
            ]
            self._bm25.index(self._bm25_docs)
        logger.info("删除文档 {}: {} chunks", doc_id, removed)
        return removed

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

    def rebuild_bm25(self) -> int:
        """从向量库全量重建 BM25 索引。

        BM25 索引为进程内存态，服务重启后丢失；向量仍持久化在 Qdrant。
        启动时调用本方法，保证 Hybrid 检索的 BM25 分支始终可用。
        """
        docs = self._vector_store.all_docs()
        self._bm25_docs = [
            {"id": d.id, "text": d.text, "metadata": d.metadata}
            for d in docs
            if d.text
        ]
        self._bm25.index(self._bm25_docs)
        logger.info("重建 BM25 索引: {} 条", len(self._bm25_docs))
        return len(self._bm25_docs)


def _derive_doc_id(chunk_id: str) -> str:
    """旧数据兼容：从 chunk id（形如 doc-rag-0）推导 doc_id（去掉末尾序号）。

    chunk_id 可能形如 `<doc_id>-p1-c0`（新格式）或 `<doc_id>-0`（旧格式）。
    """
    if "-p" in chunk_id:
        return chunk_id.split("-p")[0]
    parts = chunk_id.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return chunk_id


def _derive_title(doc_id: str) -> str:
    """旧数据兼容：用 doc_id 作为兜底标题。"""
    return doc_id


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
        siliconflow_api_key=s.siliconflow_api_key,
        siliconflow_base_url=s.siliconflow_base_url,
    )
    vector_store = build_vector_store(
        backend=s.vector_backend,
        url=s.qdrant_url,
        api_key=s.qdrant_api_key,
        path=s.qdrant_path,
        collection=s.qdrant_collection,
        dimension=s.embedding_dim,
    )
    pipe = RAGPipeline(
        embedding=embedding,
        vector_store=vector_store,
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
        top_k=s.rag_top_k,
        rerank_top_k=s.rag_rerank_top_k,
    )
    pipe.rebuild_bm25()  # 服务重启后重建内存 BM25 索引（向量库持久化于 Qdrant）
    return pipe

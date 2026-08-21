"""向量存储抽象：Qdrant 优先，未安装 qdrant-client 时回退到内存实现。

接口保持一致，业务代码不感知底层实现。
注意：内存实现使用纯 Python（避免 numpy 在部分环境/版本下的兼容问题），
语料量较小时性能足够，量级上升后请切换 Qdrant。
"""
from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


def _to_point_id(doc_id: str) -> str:
    """将任意字符串 id 稳定映射为 UUID 字符串。

    Qdrant 本地（local）模式强制 point id 为 UUID 格式，而远程服务模式接受
    任意 id。uuid5 保证同一 doc_id 幂等映射，重复 add 不产生重复点。
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"deepresearch:{doc_id}"))


@dataclass
class StoredDocument:
    """入库文档片段。"""

    id: str
    text: str
    vector: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """检索结果。"""

    id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "score": self.score, "metadata": self.metadata}


class VectorStore(ABC):
    """向量存储接口。"""

    @abstractmethod
    def add(self, docs: list[StoredDocument]) -> None: ...

    @abstractmethod
    def search(self, query_vector: list[float], top_k: int = 5) -> list[RetrievedChunk]: ...

    @abstractmethod
    def count(self) -> int: ...

    def all_docs(self) -> list[StoredDocument]:
        """全量返回库中文档（默认空，用于重建 BM25 等内存索引）。"""
        return []

    def delete_by_doc_id(self, doc_id: str) -> int:
        """删除指定文档 ID 的全部 chunk，返回删除条数。"""
        return 0

    def clear(self) -> None: ...


class MemoryVectorStore(VectorStore):
    """进程内向量库（纯 Python 实现，回退方案）。"""

    def __init__(self, dimension: int = 256) -> None:
        self._dimension = dimension
        self._docs: list[StoredDocument] = []

    def add(self, docs: list[StoredDocument]) -> None:
        for doc in docs:
            if doc.vector is None:
                raise ValueError(f"doc {doc.id} 缺少 vector")
            self._docs.append(doc)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[RetrievedChunk]:
        if not self._docs:
            return []
        scored: list[tuple[float, StoredDocument]] = []
        for doc in self._docs:
            score = _cosine_similarity(query_vector, doc.vector)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            RetrievedChunk(
                id=doc.id,
                text=doc.text,
                score=score,
                metadata=doc.metadata,
            )
            for score, doc in scored[:top_k]
        ]

    def count(self) -> int:
        return len(self._docs)

    def all_docs(self) -> list[StoredDocument]:
        return list(self._docs)

    def delete_by_doc_id(self, doc_id: str) -> int:
        before = len(self._docs)
        self._docs = [d for d in self._docs if d.metadata.get("doc_id") != doc_id]
        return before - len(self._docs)

    def clear(self) -> None:
        self._docs = []


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class QdrantVectorStore(VectorStore):
    """Qdrant 向量库封装（支持内存 / 本地文件 / 远程服务）。"""

    def __init__(self, url: str = "", api_key: str = "", path: str = "data/qdrant", collection: str = "research_documents") -> None:
        from qdrant_client import QdrantClient

        self._models = __import__("qdrant_client.http", fromlist=["models"]).models
        if url:
            self._client = QdrantClient(url=url, api_key=api_key or None)
        else:
            self._client = QdrantClient(path=path)
        self._collection = collection
        self._vector_size: int | None = None

    def _ensure_collection(self, vector_size: int) -> None:
        """按首个向量的维度创建集合（Qdrant 集合需固定向量维度）。"""
        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=self._models.VectorParams(
                size=vector_size,
                distance=self._models.Distance.COSINE,
            ),
        )

    def add(self, docs: list[StoredDocument]) -> None:
        if not docs:
            return
        vector_size = len(docs[0].vector)
        self._ensure_collection(vector_size)
        points = []
        for doc in docs:
            if doc.vector is None:
                raise ValueError(f"doc {doc.id} 缺少 vector")
            points.append(
                self._models.PointStruct(
                    id=_to_point_id(doc.id),
                    vector=doc.vector,
                    payload={"text": doc.text, "_source_id": doc.id, **doc.metadata},
                )
            )
        if points:
            self._client.upsert(self._collection, points)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[RetrievedChunk]:
        # qdrant-client >= 1.12：search 已并入通用 query_points 端点
        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=top_k,
        )
        hits = response.points
        results = []
        for hit in hits:
            payload = hit.payload or {}
            # 恢复原始文档 id（本地模式映射为 UUID，原始 id 存在 payload 中）
            doc_id = payload.get("_source_id", str(hit.id))
            results.append(
                RetrievedChunk(
                    id=str(doc_id),
                    text=payload.get("text", ""),
                    score=float(hit.score),
                    metadata={k: v for k, v in payload.items() if k not in ("text", "_source_id")},
                )
            )
        return results

    def count(self) -> int:
        return int(self._client.count(self._collection).count)

    def all_docs(self) -> list[StoredDocument]:
        """全量拉取集合中文档（payload 还原原始 id 与文本，用于重建 BM25 索引）。"""
        docs: list[StoredDocument] = []
        offset: Any = None
        while True:
            page, offset = self._client.scroll(
                collection_name=self._collection,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in page:
                payload = point.payload or {}
                docs.append(
                    StoredDocument(
                        id=str(payload.get("_source_id", point.id)),
                        text=payload.get("text", ""),
                        vector=None,
                        metadata={k: v for k, v in payload.items() if k not in ("text", "_source_id")},
                    )
                )
            if offset is None:
                break
        return docs

    def delete_by_doc_id(self, doc_id: str) -> int:
        """按 metadata.doc_id 删除全部 chunk；旧数据（无 doc_id）按 _source_id 前缀兜底。"""
        from qdrant_client import models

        filters = [
            models.Filter(
                must=[
                    models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))
                ]
            ),
            models.Filter(
                must=[
                    models.FieldCondition(key="_source_id", match=models.MatchText(text=doc_id))
                ]
            ),
        ]
        for flt in filters:
            points = self._client.scroll(
                collection_name=self._collection,
                limit=1000,
                scroll_filter=flt,
                with_payload=False,
                with_vectors=False,
            )[0]
            if points:
                self._client.delete(
                    collection_name=self._collection,
                    points_selector=models.FilterSelector(filter=flt),
                )
                return len(points)
        return 0

    def clear(self) -> None:
        self._client.delete_collection(self._collection)
        self._vector_size = None


def build_vector_store(
    backend: str = "auto",
    url: str = "",
    api_key: str = "",
    path: str = "data/qdrant",
    collection: str = "research_documents",
    dimension: int = 256,
) -> VectorStore:
    """构建向量库。backend 为 qdrant 或 auto 时优先 Qdrant（未装则内存回退）。"""
    if backend in ("qdrant", "auto"):
        try:
            store = QdrantVectorStore(url=url, api_key=api_key, path=path, collection=collection)
            logger.info("使用 Qdrant 向量库 (collection={})", collection)
            return store
        except ImportError:
            logger.warning("qdrant-client 未安装，回退到内存向量库")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant 初始化失败({}), 回退到内存向量库", exc)
    store = MemoryVectorStore(dimension=dimension)
    logger.info("使用内存向量库 (dim={})", dimension)
    return store

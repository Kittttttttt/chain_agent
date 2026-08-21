"""EmbeddingProvider 接口与实现。

设计要点：
- 业务逻辑只依赖 `EmbeddingProvider` 抽象，不绑定具体供应商
- 外部 API：dashscope(text-embedding) / openai(兼容端点) / ollama(本地)
- MockEmbedding：无外部 key 时兜底，保证链路可测
"""
from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from typing import Any, Iterable

from loguru import logger
from pydantic import BaseModel


class EmbeddingResult(BaseModel):
    text: str
    vector: list[float]
    model: str
    latency_ms: float = 0.0


class EmbeddingProvider(ABC):
    """向量化抽象。"""

    name: str = "base"
    dimension: int = 0

    @abstractmethod
    def embed(self, texts: list[str]) -> list[EmbeddingResult]:
        """批量向量化文本。"""
        raise NotImplementedError

    def embed_one(self, text: str) -> EmbeddingResult:
        return self.embed([text])[0]


class MockEmbeddingProvider(EmbeddingProvider):
    """确定性词袋哈希向量，用于测试/无 key 兜底。

    思路：对文本的每个 token 做 sha256 哈希并累加到向量（类似 hashing trick），
    使**共享 token 的文本相似度更高**，从而让余弦检索具备真实的词面语义区分能力。
    """

    name = "mock"
    dimension = 256

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[EmbeddingResult]:
        results: list[EmbeddingResult] = []
        for text in texts:
            vec = self._hash_vector(text, self.dimension)
            results.append(EmbeddingResult(text=text, vector=vec, model=self.name))
        return results

    def _hash_vector(self, text: str, dim: int) -> list[float]:
        import re

        vec = [0.0] * dim
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            return vec
        for token in tokens:
            h = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(h[:8], "big") % dim
            sign = 1.0 if (h[8] & 1) else -1.0
            vec[idx] += sign
        # 归一化
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


class DashScopeEmbeddingProvider(EmbeddingProvider):
    """DashScope（阿里云百炼）文本向量 API。"""

    name = "dashscope"
    _URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    def __init__(self, api_key: str, model: str = "text-embedding-v3", dimension: int = 1024) -> None:
        self._api_key = api_key
        self._model = model
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[EmbeddingResult]:
        import httpx

        results: list[EmbeddingResult] = []
        for text in texts:
            start = time.monotonic()
            payload = {"model": self._model, "input": text}
            headers = {"Authorization": f"Bearer {self._api_key}"}
            resp = httpx.post(self._URL, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            embedding = data["output"]["embeddings"][0]["embedding"]
            results.append(
                EmbeddingResult(
                    text=text,
                    vector=embedding,
                    model=self._model,
                    latency_ms=(time.monotonic() - start) * 1000,
                )
            )
        return results


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI 兼容 /v1/embeddings 端点（可指向 OpenAI、本地 vLLM 等）。"""

    name = "openai_compatible"

    def __init__(
        self, api_key: str, base_url: str, model: str = "text-embedding-3-small", dimension: int = 1536
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[EmbeddingResult]:
        import httpx

        url = f"{self._base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        results: list[EmbeddingResult] = []
        for text in texts:
            start = time.monotonic()
            resp = httpx.post(
                url,
                json={"model": self._model, "input": text},
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            results.append(
                EmbeddingResult(
                    text=text,
                    vector=data["data"][0]["embedding"],
                    model=self._model,
                    latency_ms=(time.monotonic() - start) * 1000,
                )
            )
        return results


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Ollama 本地 embedding（如 nomic-embed-text）。"""

    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text") -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def embed(self, texts: list[str]) -> list[EmbeddingResult]:
        import httpx

        results: list[EmbeddingResult] = []
        for text in texts:
            start = time.monotonic()
            resp = httpx.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
                timeout=60,
            )
            resp.raise_for_status()
            vec = resp.json()["embedding"]
            if not self.dimension:
                self.dimension = len(vec)
            results.append(
                EmbeddingResult(
                    text=text,
                    vector=vec,
                    model=self._model,
                    latency_ms=(time.monotonic() - start) * 1000,
                )
            )
        return results


def build_embedding_provider(
    provider: str = "mock",
    dashscope_api_key: str = "",
    openai_api_key: str = "",
    openai_base_url: str = "",
    embedding_model: str = "text-embedding-v3",
    ollama_base_url: str = "http://localhost:11434",
    siliconflow_api_key: str = "",
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1/",
) -> EmbeddingProvider:
    """按配置构建 Embedding Provider（可插拔）。"""
    if provider == "dashscope" and dashscope_api_key:
        logger.info("使用 DashScope Embedding: {}", embedding_model)
        return DashScopeEmbeddingProvider(dashscope_api_key, model=embedding_model)
    if provider == "openai" and openai_api_key:
        logger.info("使用 OpenAI 兼容 Embedding: {}", embedding_model)
        return OpenAICompatibleEmbeddingProvider(openai_api_key, openai_base_url, model=embedding_model)
    if provider == "siliconflow" and siliconflow_api_key:
        logger.info("使用 SiliconFlow（OpenAI 兼容）Embedding: {}", embedding_model)
        # BAAI/bge-m3 输出 1024 维向量
        return OpenAICompatibleEmbeddingProvider(
            siliconflow_api_key, siliconflow_base_url, model=embedding_model, dimension=1024
        )
    if provider == "ollama":
        logger.info("使用 Ollama Embedding: {}", embedding_model)
        return OllamaEmbeddingProvider(ollama_base_url, model=embedding_model)
    logger.warning("使用 MockEmbedding（未配置真实 Embedding Provider，仅用于测试/演示）")
    return MockEmbeddingProvider()

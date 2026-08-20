"""统一 Tool Layer。

所有 Research Tool 均实现 `BaseResearchTool` 接口：
- 结构化 Pydantic 输入/输出 Schema
- 异常处理
- Timeout
- 记录 Tool Call（latency / success / error / retry）
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict


class ToolResult(BaseModel):
    """工具统一输出结构。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool: str
    success: bool
    data: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    retries: int = 0
    truncated: bool = False

    def to_observation(self) -> str:
        """转换为可供 LLM 阅读的 Observation 文本。"""
        if not self.success:
            return f"[tool:{self.tool}] FAILED: {self.error}"
        return f"[tool:{self.tool}] OK ({self.latency_ms:.0f}ms): {self.data}"


class BaseResearchTool(ABC):
    """Research Tool 抽象基类。"""

    name: str = ""
    description: str = ""
    args_schema: type[BaseModel] = BaseModel
    timeout_seconds: float = 30.0
    max_retries: int = 2

    def __init__(self, timeout_seconds: float | None = None, max_retries: int | None = None) -> None:
        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds
        if max_retries is not None:
            self.max_retries = max_retries

    @abstractmethod
    def _execute(self, **kwargs: Any) -> Any:
        """子类实现具体逻辑。"""
        raise NotImplementedError

    def invoke(self, **kwargs: Any) -> ToolResult:
        """统一入口：校验参数 → 带重试/超时执行 → 记录结果。"""
        start = time.monotonic()
        # Pydantic 参数校验
        validated = self.args_schema(**kwargs)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                data = self._execute(**validated.model_dump())
                latency_ms = (time.monotonic() - start) * 1000
                logger.debug("tool={} success latency={:.0f}ms", self.name, latency_ms)
                return ToolResult(
                    tool=self.name,
                    success=True,
                    data=data,
                    latency_ms=latency_ms,
                    retries=attempt,
                )
            except Exception as exc:  # noqa: BLE001 - 工具层统一兜底
                last_error = exc
                logger.warning("tool={} attempt={} error={}", self.name, attempt, exc)
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
        latency_ms = (time.monotonic() - start) * 1000
        return ToolResult(
            tool=self.name,
            success=False,
            error=str(last_error),
            latency_ms=latency_ms,
            retries=self.max_retries,
        )

    async def ainvoke(self, **kwargs: Any) -> ToolResult:
        """异步统一入口（内部复用同步实现，避免重复逻辑）。"""
        return self.invoke(**kwargs)

    def to_langchain_tool(self):
        """转换为 LangChain StructuredTool，供 Agent 直接调用。"""
        from langchain_core.tools import StructuredTool

        return StructuredTool.from_function(
            func=self.invoke,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            return_direct=False,
        )

"""日志配置（loguru）。

统一输出格式，将 Agent 执行轨迹、Tool 调用、异常堆栈写入日志。
"""
from __future__ import annotations

import sys

from loguru import logger

_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """初始化全局日志配置。重复调用会自动去重。"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=_FORMAT,
        backtrace=True,
        diagnose=False,
    )
    if log_file:
        logger.add(
            log_file,
            level="DEBUG",
            format=_FORMAT,
            rotation="10 MB",
            retention="7 days",
            encoding="utf-8",
            enqueue=True,
        )
    # 避免重复添加 sink
    logger.add = lambda *a, **k: None  # type: ignore[assignment]

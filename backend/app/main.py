"""FastAPI 应用入口。

启动：
    cd backend
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api.routes import router
from app.config import get_settings
from app.logging_config import setup_logging
from app.observability import setup_langsmith


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level, log_file="data/deepresearch.log")
    setup_langsmith(s)  # 启动时注入 LangSmith 环境变量
    logger.info("{} v{} 启动", s.app_name, s.app_version)
    yield
    logger.info("应用关闭")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.app_name,
        version=s.app_version,
        description="基于 LangGraph 的多阶段自主深度研究智能体",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()

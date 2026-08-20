"""pytest 共享夹具。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402


@pytest.fixture()
def mock_settings(monkeypatch):
    """强制使用 Mock 模型，保证测试不依赖外部 API。"""
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "mock")
    monkeypatch.setattr(s, "embedding_provider", "mock")
    monkeypatch.setattr(s, "search_provider", "duckduckgo")
    monkeypatch.setattr(s, "vector_backend", "memory")
    return s

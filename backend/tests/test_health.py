"""健康检查与 FastAPI 集成测试。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "DeepResearch Agent"


def test_research_not_found():
    client = TestClient(app)
    resp = client.get("/api/research/nonexistent")
    assert resp.status_code == 404

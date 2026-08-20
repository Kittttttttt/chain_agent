"""LangGraph Agent Graph 集成测试（Mock 模型，不依赖外部 API）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402


def test_build_graph_compiles():
    from app.graph.graph import build_graph

    graph = build_graph()
    assert graph is not None


def test_graph_runs_with_mock(mock_settings):
    """使用 Mock 模型跑通整个 Graph（Agent Loop + Sufficiency + Report）。"""
    from app.graph.graph import build_graph
    from app.graph.state import initial_state

    graph = build_graph()
    state = initial_state("什么是 LangGraph？", depth="quick", max_iterations=2)
    final = graph.invoke(state, config={"recursion_limit": 30})

    assert "final_report" in final
    # 无论证据是否充分，都必须能收敛到报告
    assert final.get("iteration_count", 0) >= 1
    assert final["final_report"] != ""


def test_sufficiency_check_logic():
    from app.agents.evaluator import is_sufficient

    # 无证据 → 不充分
    ok, _ = is_sufficient([], threshold=0.6, min_evidence=3, iteration=0, max_iterations=8)
    assert not ok
    # 达到最大迭代 → 强制充分
    ok, _ = is_sufficient([], threshold=0.99, min_evidence=10, iteration=8, max_iterations=8)
    assert ok

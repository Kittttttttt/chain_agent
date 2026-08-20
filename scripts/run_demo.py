"""演示脚本：命令行运行一次深度研究。

用法：
    python scripts/run_demo.py "你的研究问题" [--max-iterations 4]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.graph.graph import build_graph  # noqa: E402
from app.graph.state import initial_state  # noqa: E402
from app.observability import setup_langsmith  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepResearch Agent 演示")
    parser.add_argument("question", nargs="?", default="什么是 LangGraph 的 StateGraph？")
    parser.add_argument("--max-iterations", type=int, default=4)
    args = parser.parse_args()

    s = get_settings()
    setup_logging(s.log_level)
    setup_langsmith(s)  # 注入 LangSmith 环境变量，使图运行自动被追踪

    print(f"问题: {args.question}")
    print(f"LLM: {s.llm_provider} | 搜索: {s.search_provider} | Embedding: {s.embedding_provider}")
    print("=" * 60)

    graph = build_graph()
    state = initial_state(args.question, depth="standard", max_iterations=args.max_iterations)
    final = graph.invoke(state)

    print("\n" + "=" * 60)
    print("最终报告:")
    print(final.get("final_report", "(空)"))

    print("\n" + "=" * 60)
    print(f"迭代次数: {final.get('iteration_count')}")
    print(f"证据数: {len(final.get('evidence', []))}")
    print(f"工具调用: {len(final.get('tool_calls', []))}")
    print(f"充分性得分: {final.get('sufficiency_score')}")
    print(f"执行元数据: {json.dumps(final.get('execution_metadata', {}), ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()

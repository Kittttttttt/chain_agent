"""基线与评测执行器。

Baseline 1：单次 LLM 直接回答（无检索）
Baseline 2：搜索 + LLM
Full：DeepResearch Agent（LangGraph 多阶段）

产出 eval/reports/benchmark_report.md（真实运行数据）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# 项目根（backend 与 eval 均在根下）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))
sys.path.insert(0, str(_PROJECT_ROOT))

from app.agents.llm import get_llm  # noqa: E402
from app.graph.graph import build_graph  # noqa: E402
from app.graph.state import initial_state  # noqa: E402
from app.tools.web_search import build_search_provider  # noqa: E402
from eval.metrics import (  # noqa: E402
    citation_coverage,
    keyword_coverage,
    tool_success_rate,
)

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "questions.json"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
SAMPLE_QUESTION_IDS = ["q1", "q2", "q5", "q9"]


def load_dataset() -> list[dict]:
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


def baseline_single_llm(question: str, llm=None) -> dict:
    """Baseline 1：单次 LLM 直接回答。"""
    llm = llm or get_llm()
    start = time.monotonic()
    resp = llm.invoke(f"请回答：{question}")
    latency = time.monotonic() - start
    return {"answer": str(resp.content), "latency_s": latency, "tool_calls": []}


def baseline_search_llm(question: str, llm=None) -> dict:
    """Baseline 2：搜索 + LLM（单轮）。"""
    from app.config import get_settings

    s = get_settings()
    provider = build_search_provider(s.search_provider, s.tavily_api_key, 5)
    results = provider.search(question, max_results=5)
    context = "\n".join(f"- {r.title}: {r.snippet}" for r in results)
    llm = llm or get_llm()
    start = time.monotonic()
    resp = llm.invoke(f"基于以下资料回答：{question}\n资料：\n{context}")
    latency = time.monotonic() - start
    return {"answer": str(resp.content), "latency_s": latency, "tool_calls": []}


def run_deepresearch(question: str, max_iterations: int = 4) -> dict:
    """Full：DeepResearch Agent。"""
    graph = build_graph()
    state = initial_state(question, depth="standard", max_iterations=max_iterations)
    start = time.monotonic()
    final = graph.invoke(state)
    latency = time.monotonic() - start
    return {
        "answer": final.get("final_report", ""),
        "latency_s": latency,
        "tool_calls": final.get("tool_calls", []),
        "evidence": final.get("evidence", []),
        "citations": final.get("citations", []),
        "iterations": final.get("iteration_count", 0),
        "sufficiency_score": final.get("sufficiency_score", 0.0),
    }


def main() -> None:
    dataset = load_dataset()
    # 默认只跑 4 条子集；--full 跑全部
    use_all = "--full" in sys.argv
    items = dataset if use_all else [d for d in dataset if d["id"] in SAMPLE_QUESTION_IDS]

    rows = []
    for item in items:
        qid, question = item["id"], item["question"]
        kws = item.get("expected_keywords", [])
        print(f"[{qid}] {question[:60]}")

        b1 = baseline_single_llm(question)
        b2 = baseline_search_llm(question)
        dr = run_deepresearch(question)

        rows.append(
            {
                "question_id": qid,
                "baseline1_keyword_coverage": round(keyword_coverage(b1["answer"], kws), 3),
                "baseline1_latency_s": round(b1["latency_s"], 2),
                "baseline2_keyword_coverage": round(keyword_coverage(b2["answer"], kws), 3),
                "baseline2_latency_s": round(b2["latency_s"], 2),
                "agent_keyword_coverage": round(keyword_coverage(dr["answer"], kws), 3),
                "agent_latency_s": round(dr["latency_s"], 2),
                "agent_iterations": dr["iterations"],
                "agent_tool_success_rate": round(tool_success_rate(dr["tool_calls"]), 3),
                "agent_citation_coverage": round(citation_coverage(dr["answer"], dr["citations"]), 3),
                "agent_sufficiency": dr["sufficiency_score"],
            }
        )

    # 汇总
    def avg(key: str) -> float:
        vals = [r[key] for r in rows]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    summary = {
        "avg_baseline1_coverage": avg("baseline1_keyword_coverage"),
        "avg_baseline2_coverage": avg("baseline2_keyword_coverage"),
        "avg_agent_coverage": avg("agent_keyword_coverage"),
        "avg_baseline1_latency_s": avg("baseline1_latency_s"),
        "avg_baseline2_latency_s": avg("baseline2_latency_s"),
        "avg_agent_latency_s": avg("agent_latency_s"),
        "avg_agent_tool_success_rate": avg("agent_tool_success_rate"),
        "avg_agent_citation_coverage": avg("agent_citation_coverage"),
        "avg_agent_iterations": avg("agent_iterations"),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "benchmark_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# DeepResearch Agent Benchmark Report\n\n")
        f.write("> 数据来源：真实运行（mock/真实模型），非编造。\n\n")
        f.write("## 逐问题结果\n\n| 指标 | 值 |\n|---|---|\n")
        for row in rows:
            f.write("| " + " | ".join(str(v) for v in row.values()) + " |\n")
        f.write("\n## 汇总\n\n")
        for k, v in summary.items():
            f.write(f"- {k}: {v}\n")
        f.write("\n## 结论\n\nBaseline vs DeepResearch Agent 对比（关键词覆盖率为忠实度代理指标）。\n")

    print("\n=== Summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()

<script setup lang="ts">
// Agent 执行事件流（Trace）面板：Planner → Tool Call → RAG → Evidence → Report
import { computed } from "vue";
import { useResearchStore } from "@/stores/research";
import type { AgentEvent } from "@/api/types";

const store = useResearchStore();

const phaseLabel: Record<string, string> = {
  web_search: "Web Search",
  arxiv_search: "ArXiv Search",
  github_search: "GitHub Search",
  read_source: "Read Source",
  rag_retrieval: "RAG Retrieval",
  tool_call: "Tool Call",
};

const nodeLabel: Record<string, string> = {
  research_intake: "Intake",
  planner: "Planner",
  research_worker: "Research Worker",
  evidence_extraction: "Evidence Extraction",
  evidence_evaluation: "Evidence Evaluation",
  report_writer: "Report Writer",
  citation_verification: "Citation Verification",
  evaluator: "Evaluator",
};

interface Row {
  icon: string;
  color: string;
  text: string;
  sub: string;
  latency?: string;
  time: string;
}

const rows = computed<Row[]>(() => {
  const out: Row[] = [];
  for (const e of store.events) {
    const t = new Date(e.ts * 1000).toLocaleTimeString("zh-CN", { hour12: false });
    switch (e.type) {
      case "node_start": {
        out.push({
          icon: "right",
          color: "var(--dr-accent)",
          text: nodeLabel[e.node ?? ""] ?? e.node ?? "",
          sub: "节点开始",
          time: t,
        });
        break;
      }
      case "node_end": {
        out.push({
          icon: "check",
          color: "var(--dr-success)",
          text: nodeLabel[e.node ?? ""] ?? e.node ?? "",
          sub: "节点完成",
          latency: e.latency_ms != null ? `${(e.latency_ms / 1000).toFixed(1)}s` : undefined,
          time: t,
        });
        break;
      }
      case "planner_plan": {
        const subtasks = e.plan?.subtasks ?? [];
        out.push({
          icon: "files",
          color: "var(--dr-warn)",
          text: "生成研究计划",
          sub: `${subtasks.length} 个子任务`,
          time: t,
        });
        break;
      }
      case "tool_call": {
        const ok = e.success !== false;
        out.push({
          icon: "tools",
          color: ok ? "var(--dr-text)" : "var(--dr-danger)",
          text: `${phaseLabel[e.phase ?? ""] ?? e.phase ?? ""} · ${e.tool ?? ""}`,
          sub: e.error ?? e.output_summary ?? JSON.stringify(e.input ?? {}),
          latency: e.latency_ms != null ? `${(e.latency_ms / 1000).toFixed(1)}s` : undefined,
          time: t,
        });
        break;
      }
      case "rag_retrieval": {
        out.push({
          icon: "search",
          color: "var(--dr-accent)",
          text: "RAG Hybrid Retrieval",
          sub: `Top-K: ${e.reranked?.length ?? 0} 片段 · Query: ${(e.query ?? "").slice(0, 60)}`,
          time: t,
        });
        break;
      }
      case "evidence_evaluated": {
        out.push({
          icon: "data-analysis",
          color: "var(--dr-success)",
          text: "证据充分性评估",
          sub: `score=${e.sufficiency_score?.toFixed(2)} · evidence=${e.evidence_count} · threshold=${e.threshold}`,
          time: t,
        });
        break;
      }
      case "report_generated": {
        out.push({
          icon: "document",
          color: "var(--dr-warn)",
          text: "报告生成",
          sub: `${e.length ?? 0} 字符`,
          time: t,
        });
        break;
      }
      case "citation_verified": {
        out.push({
          icon: "link",
          color: "var(--dr-success)",
          text: "引用校验",
          sub: `verified=${e.verified_count} · unverified=${e.unverified_count}`,
          time: t,
        });
        break;
      }
      case "evaluator_done": {
        const m = e.metrics ?? {};
        out.push({
          icon: "finished",
          color: "var(--dr-success)",
          text: "执行指标汇总",
          sub: `total=${m.total_latency_s ?? "?"}s · tools=${m.tool_call_count ?? 0} · evidence=${m.evidence_count ?? 0} · iterations=${m.iteration_count ?? 0}`,
          time: t,
        });
        break;
      }
    }
  }
  return out;
});
</script>

<template>
  <el-empty
    v-if="rows.length === 0"
    description="暂无执行事件 —— 任务尚未开始"
    :image-size="72"
  />
  <el-timeline v-else class="trace-timeline">
    <el-timeline-item
      v-for="(row, i) in rows"
      :key="i"
      :timestamp="row.time"
      placement="top"
    >
      <div class="trace-row">
        <div class="trace-row__head">
          <el-icon :style="{ color: row.color }"><component :is="row.icon" /></el-icon>
          <span class="trace-row__text">{{ row.text }}</span>
          <span v-if="row.latency" class="trace-row__latency mono">{{ row.latency }}</span>
        </div>
        <div class="trace-row__sub mono">{{ row.sub }}</div>
      </div>
    </el-timeline-item>
  </el-timeline>
</template>

<style scoped>
.trace-timeline {
  padding-left: 4px;
}
.trace-row__head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.trace-row__text {
  font-weight: 600;
  font-size: 13px;
}
.trace-row__latency {
  color: var(--dr-text-dim);
  background: var(--dr-bg-soft);
  border: 1px solid var(--dr-border);
  border-radius: 4px;
  padding: 0 6px;
}
.trace-row__sub {
  margin-top: 3px;
  color: var(--dr-text-dim);
  word-break: break-all;
  line-height: 1.5;
}
</style>

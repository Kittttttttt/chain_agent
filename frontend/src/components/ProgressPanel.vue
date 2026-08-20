<script setup lang="ts">
// Agent 执行阶段进度面板（从实时事件流派生，非静态假数据）
import { computed } from "vue";
import { useResearchStore } from "@/stores/research";
import type { AgentEvent } from "@/api/types";

const store = useResearchStore();

interface StageDef {
  key: string;
  label: string;
  desc: string;
}

const stageDefs: StageDef[] = [
  { key: "planner", label: "Planning", desc: "任务拆解" },
  { key: "research_worker", label: "Research & Tools", desc: "搜索 / 阅读 / 检索" },
  { key: "evidence_evaluation", label: "Evidence Evaluation", desc: "充分性评分" },
  { key: "report_writer", label: "Report Generation", desc: "结构化报告" },
  { key: "citation_verification", label: "Citation Verification", desc: "引用校验" },
  { key: "evaluator", label: "Evaluation", desc: "指标汇总" },
];

const stages = computed(() => {
  const events = store.events;
  const startTs = (node: string) =>
    events.find((e) => e.type === "node_start" && e.node === node)?.ts;
  const endEv = (node: string) =>
    events.find((e) => e.type === "node_end" && e.node === node);
  const toolFailed = events.some(
    (e) => e.type === "tool_call" && e.success === false,
  );

  return stageDefs.map((def, idx) => {
    const started = startTs(def.key) !== undefined;
    const done = !!endEv(def.key);
    let status: "done" | "running" | "pending" | "failed" = "pending";
    if (store.status === "failed") status = "failed";
    else if (done) status = "done";
    else if (started) status = "running";
    else if (idx > 0 && stageDefs.slice(0, idx).some((d) => !!endEv(d.key))) {
      // 前置阶段已完成，本阶段等待
    }
    const latency = endEv(def.key)?.latency_ms;
    return {
      ...def,
      status,
      latency,
      toolFailed,
    };
  });
});

const statusIcon = (s: string) =>
  s === "done" ? "circle-check" : s === "running" ? "loading" : s === "failed" ? "circle-close" : "circle";
</script>

<template>
  <div class="progress">
    <div v-for="(stage, i) in stages" :key="stage.key" class="progress__stage">
      <div class="progress__rail" :class="{ active: stage.status === 'running' }">
        <el-icon class="progress__icon" :class="stage.status">
          <component :is="statusIcon(stage.status)" />
        </el-icon>
        <div class="progress__text">
          <span class="progress__label">{{ stage.label }}</span>
          <span class="progress__desc">
            {{ stage.status === "done" && stage.latency ? `${(stage.latency / 1000).toFixed(1)}s` : stage.desc }}
          </span>
        </div>
      </div>
      <div v-if="i < stages.length - 1" class="progress__line" :class="{ lit: stage.status === 'done' }" />
    </div>
  </div>
</template>

<style scoped>
.progress {
  display: flex;
  align-items: flex-start;
  gap: 0;
  flex-wrap: wrap;
}
.progress__stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 130px;
  flex: 1;
}
.progress__rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}
.progress__icon {
  font-size: 22px;
  color: var(--dr-text-dim);
}
.progress__icon.done {
  color: var(--dr-success);
}
.progress__icon.running {
  color: var(--dr-accent);
}
.progress__icon.failed {
  color: var(--dr-danger);
}
.progress__label {
  font-size: 12.5px;
  font-weight: 600;
}
.progress__desc {
  font-size: 11px;
  color: var(--dr-text-dim);
}
.progress__line {
  flex: 1;
  min-width: 20px;
  height: 2px;
  background: var(--dr-border);
  margin: 12px 4px 0;
}
.progress__line.lit {
  background: var(--dr-success);
}
</style>

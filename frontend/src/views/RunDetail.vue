<script setup lang="ts">
// Run Detail：任务详情 = Agent Trace + Sources/Evidence + RAG + Final Report
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useResearchStore } from "@/stores/research";
import AgentTracePanel from "@/components/AgentTracePanel.vue";
import SourcesPanel from "@/components/SourcesPanel.vue";
import RagRetrievalPanel from "@/components/RagRetrievalPanel.vue";
import ReportViewer from "@/components/ReportViewer.vue";

const route = useRoute();
const store = useResearchStore();

const activeTab = ref("trace");
const highlightIndex = ref<number | undefined>(undefined);
const loading = ref(false);
const loadError = ref("");

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    await store.loadRun(route.params.id as string);
  } catch (e) {
    loadError.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => route.params.id, load);

const statusType = computed<"success" | "danger" | "primary" | "info">(() => {
  switch (store.status) {
    case "completed":
      return "success";
    case "failed":
      return "danger";
    case "running":
      return "primary";
    default:
      return "info";
  }
});

const meta = computed(() => {
  const m = store.metrics ?? {};
  const exec = (m.execution_metadata ?? {}) as Record<string, unknown>;
  return [
    { label: "Sufficiency Score", value: m.sufficiency_score != null ? (m.sufficiency_score as number).toFixed(2) : "—" },
    { label: "Iterations", value: m.iteration_count ?? "—" },
    { label: "Evidence", value: m.evidence_count ?? "—" },
    { label: "Tool Calls", value: m.tool_call_count ?? "—" },
    { label: "Total Latency", value: exec.total_latency_s != null ? `${(exec.total_latency_s as number).toFixed(1)}s` : "—" },
  ];
});

/** 报告 [来源N] 点击 → 切到 Sources 面板并高亮对应来源 */
function onLocate(n: number) {
  activeTab.value = "sources";
  highlightIndex.value = n - 1;
  setTimeout(() => (highlightIndex.value = undefined), 2500);
}
</script>

<template>
  <div class="page">
    <!-- 加载 / 错误 -->
    <el-empty v-if="loadError" :description="`加载失败: ${loadError}`">
      <el-button @click="load">重试</el-button>
    </el-empty>

    <template v-else>
      <!-- 头部 -->
      <div class="dr-card">
        <div class="run-header">
          <el-tag :type="statusType" size="large">{{ store.status }}</el-tag>
          <span class="run-header__id mono">{{ store.researchId }}</span>
          <span v-if="store.connected" class="run-header__live">● LIVE</span>
        </div>
        <div class="run-header__q">{{ store.question }}</div>
        <div class="meta-grid">
          <div v-for="m in meta" :key="m.label" class="meta">
            <span class="meta__value">{{ m.value }}</span>
            <span class="meta__label">{{ m.label }}</span>
          </div>
        </div>
        <el-alert
          v-if="store.error"
          :title="store.error"
          type="error"
          :closable="false"
          style="margin-top: 10px"
        />
      </div>

      <el-tabs v-model="activeTab" class="run-tabs">
        <el-tab-pane name="trace">
          <template #label>
            <el-icon><list /></el-icon> Agent Trace
          </template>
          <AgentTracePanel />
        </el-tab-pane>

        <el-tab-pane name="sources">
          <template #label>
            <el-icon><collection /></el-icon> Sources / Evidence
          </template>
          <SourcesPanel :highlight-index="highlightIndex" />
        </el-tab-pane>

        <el-tab-pane name="rag">
          <template #label>
            <el-icon><search /></el-icon> RAG Retrieval
          </template>
          <RagRetrievalPanel />
        </el-tab-pane>

        <el-tab-pane name="report">
          <template #label>
            <el-icon><document /></el-icon> Final Report
          </template>
          <ReportViewer :report="store.report" @locate="onLocate" />
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<style scoped>
.run-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.run-header__id {
  color: var(--dr-text-dim);
}
.run-header__live {
  color: var(--dr-success);
  font-size: 12px;
  animation: blink 1.2s infinite;
}
@keyframes blink {
  50% {
    opacity: 0.3;
  }
}
.run-header__q {
  font-size: 18px;
  font-weight: 600;
  margin-top: 12px;
}
.meta-grid {
  display: flex;
  gap: 32px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.meta {
  display: flex;
  flex-direction: column;
}
.meta__value {
  font-size: 22px;
  font-weight: 700;
  color: var(--dr-accent);
}
.meta__label {
  font-size: 11px;
  color: var(--dr-text-dim);
}
.run-tabs {
  margin-top: 16px;
}
</style>

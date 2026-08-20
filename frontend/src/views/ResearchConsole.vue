<script setup lang="ts">
// Research Console：输入问题 → 选择模式 → 开始 / 停止 → 实时进度
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useResearchStore } from "@/stores/research";
import type { ResearchDepth } from "@/api/types";
import ProgressPanel from "@/components/ProgressPanel.vue";
import AgentTracePanel from "@/components/AgentTracePanel.vue";

const router = useRouter();
const store = useResearchStore();

const question = ref("");
const depth = ref<ResearchDepth>("standard");
const iterations = ref<number | null>(null);

const depthOptions = [
  { value: "quick", label: "Quick", desc: "快速 · 1-2 轮" },
  { value: "standard", label: "Standard", desc: "标准 · 默认" },
  { value: "deep", label: "Deep", desc: "深度 · 多轮" },
];

const canStart = computed(() => question.value.trim().length > 0 && !store.isActive);

async function onStart() {
  if (!canStart.value) return;
  try {
    await store.start({
      question: question.value.trim(),
      depth: depth.value,
      max_iterations: iterations.value,
    });
    ElMessage.success(`研究任务已受理: ${store.researchId}`);
  } catch (e) {
    ElMessage.error(`启动失败: ${(e as Error).message}`);
  }
}

function onStop() {
  store.reset();
  ElMessage.info("已断开订阅（后端任务会继续执行至完成）");
}
</script>

<template>
  <div class="page console-page">
    <!-- 输入区 -->
    <div class="dr-card">
      <div class="dr-card__title">Research Question</div>
      <el-input
        v-model="question"
        type="textarea"
        :rows="3"
        placeholder="输入要研究的问题，例如：What is LangGraph? How does it work?"
        :disabled="store.isActive"
      />
      <div class="console-options">
        <el-radio-group v-model="depth" :disabled="store.isActive">
          <el-radio-button v-for="d in depthOptions" :key="d.value" :value="d.value">
            {{ d.label }} <span class="depth-desc">{{ d.desc }}</span>
          </el-radio-button>
        </el-radio-group>
        <div class="iterations">
          <span class="mono">Max Iterations</span>
          <el-input-number
            v-model="iterations"
            :min="1"
            :max="50"
            :disabled="store.isActive"
            size="small"
          />
        </div>
      </div>
      <div class="console-actions">
        <el-button
          type="primary"
          size="large"
          :loading="store.starting"
          :disabled="!canStart"
          @click="onStart"
        >
          开始研究
        </el-button>
        <el-button v-if="store.isActive" size="large" @click="onStop">停止订阅</el-button>
        <el-button
          v-if="store.researchId && store.status === 'completed'"
          size="large"
          type="success"
          @click="router.push(`/runs/${store.researchId}`)"
        >
          查看完整详情 →
        </el-button>
      </div>
    </div>

    <!-- 运行状态 -->
    <div v-if="store.researchId" class="dr-card">
      <div class="dr-card__title">
        <el-tag
          :type="store.status === 'completed' ? 'success' : store.status === 'failed' ? 'danger' : 'primary'"
        >
          {{ store.status }}
        </el-tag>
        <span class="run-id mono">{{ store.researchId }}</span>
        <span v-if="store.connected" class="live">● LIVE</span>
        <el-alert
          v-if="store.error"
          :title="`任务失败: ${store.error}`"
          type="error"
          :closable="false"
          class="console-error"
        />
      </div>
      <ProgressPanel />
    </div>

    <!-- 实时事件流 -->
    <div v-if="store.researchId" class="dr-card">
      <div class="dr-card__title">Agent Execution Trace（实时）</div>
      <AgentTracePanel />
    </div>
  </div>
</template>

<style scoped>
.console-page {
  max-width: 1100px;
}
.console-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.depth-desc {
  font-size: 11px;
  opacity: 0.7;
  margin-left: 4px;
}
.iterations {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--dr-text-dim);
  font-size: 12px;
}
.console-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
.run-id {
  color: var(--dr-text-dim);
}
.live {
  color: var(--dr-success);
  font-size: 12px;
  animation: blink 1.2s infinite;
}
@keyframes blink {
  50% {
    opacity: 0.3;
  }
}
.console-error {
  margin-top: 8px;
}
</style>

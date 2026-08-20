<script setup lang="ts">
// 设置页：只读展示后端运行配置（来自 /health），前端不直连数据库/LLM
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { useSettingsStore } from "@/stores/settings";

const store = useSettingsStore();
const loading = ref(false);

const providerMeta = [
  {
    key: "llm_provider",
    label: "LLM Provider",
    desc: "负责 Planner / Worker / Report Writer / Evaluator 等 Agent 节点的模型推理。",
  },
  {
    key: "search_provider",
    label: "Search Provider",
    desc: "Web 搜索后端（DuckDuckGo / Tavily），供 Search Web 工具检索开放网页。",
  },
  {
    key: "vector_backend",
    label: "Vector Backend",
    desc: "向量数据库后端（Qdrant 本地模式），用于文档切块后的向量索引与检索。",
  },
  {
    key: "embedding_provider",
    label: "Embedding Provider",
    desc: "文本嵌入模型，负责将 Query 与文档片段编码为向量，支撑 Dense Retrieval。",
  },
] as const;

async function refresh() {
  loading.value = true;
  await store.refresh();
  loading.value = false;
  if (!store.backendOnline) {
    ElMessage.warning("后端服务未在线，无法读取配置");
  }
}

onMounted(refresh);
</script>

<template>
  <div class="settings-page">
    <el-page-header content="设置" @back="$router.push('/research')" />

    <el-alert
      v-if="!store.backendOnline"
      class="offline-alert"
      type="warning"
      :closable="false"
      show-icon
      title="后端服务未在线"
      description="请确认 FastAPI 服务已在 127.0.0.1:8000 启动，前端只通过 API 读取配置。"
    />

    <div class="toolbar">
      <h3>运行配置（只读）</h3>
      <el-button :loading="loading" size="small" @click="refresh">刷新</el-button>
    </div>

    <el-descriptions
      v-if="store.health"
      :column="2"
      border
      class="health-table"
    >
      <el-descriptions-item label="服务状态">
        <el-tag size="small" type="success">{{ store.health.status }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="应用">{{ store.health.app }}</el-descriptions-item>
      <el-descriptions-item label="版本">{{ store.health.version }}</el-descriptions-item>
      <el-descriptions-item
        v-for="m in providerMeta"
        :key="m.key"
        :label="m.label"
      >
        {{ (store.health as any)[m.key] }}
      </el-descriptions-item>
    </el-descriptions>

    <div v-if="store.health" class="provider-cards">
      <el-card v-for="m in providerMeta" :key="m.key" shadow="hover" class="provider-card">
        <template #header>
          <div class="card-header">
            <span>{{ m.label }}</span>
            <el-tag size="small" type="info">{{ (store.health as any)[m.key] }}</el-tag>
          </div>
        </template>
        <p class="card-desc">{{ m.desc }}</p>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}
.offline-alert {
  margin-top: 16px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20px 0 12px;
}
.toolbar h3 {
  margin: 0;
}
.health-table {
  margin-bottom: 24px;
}
.provider-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}
.card-desc {
  margin: 0;
  color: var(--dr-text-dim, #8a8f98);
  font-size: 13px;
  line-height: 1.6;
}
</style>

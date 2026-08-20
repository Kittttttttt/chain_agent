<script setup lang="ts">
// 历史任务列表
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/api/client";
import type { RunSummary } from "@/api/types";

const router = useRouter();
const items = ref<RunSummary[]>([]);
const loading = ref(false);

const statusType: Record<string, "success" | "danger" | "primary" | "info"> = {
  completed: "success",
  failed: "danger",
  running: "primary",
  queued: "info",
};

const depthLabel: Record<string, string> = { quick: "Quick", standard: "Standard", deep: "Deep" };

async function load() {
  loading.value = true;
  try {
    const data = await api.listRuns();
    items.value = data.items;
  } finally {
    loading.value = false;
  }
}

function fmtTime(ts: number): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false });
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="dr-card">
      <div class="dr-card__title">
        历史任务
        <el-button size="small" :loading="loading" @click="load" style="margin-left: 8px">刷新</el-button>
      </div>
      <el-empty v-if="!loading && items.length === 0" description="暂无历史任务 —— 去 Research Console 发起一个吧" />
      <el-table v-else v-loading="loading" :data="items" size="large">
        <el-table-column prop="research_id" label="ID" width="140">
          <template #default="{ row }">
            <router-link :to="`/runs/${row.research_id}`" class="mono">{{ row.research_id }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="question" label="问题" min-width="280" show-overflow-tooltip />
        <el-table-column label="深度" width="100">
          <template #default="{ row }">{{ depthLabel[row.depth] ?? row.depth }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType[row.status] ?? 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="充分性" width="100">
          <template #default="{ row }">
            {{ row.sufficiency_score != null ? row.sufficiency_score.toFixed(2) : "—" }}
          </template>
        </el-table-column>
        <el-table-column label="证据" width="80">
          <template #default="{ row }">{{ row.evidence_count ?? "—" }}</template>
        </el-table-column>
        <el-table-column label="工具调用" width="90">
          <template #default="{ row }">{{ row.tool_call_count ?? "—" }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="router.push(`/runs/${row.research_id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

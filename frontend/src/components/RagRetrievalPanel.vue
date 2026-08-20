<script setup lang="ts">
// RAG 检索面板：Query → Dense / BM25 / Hybrid / Rerank → Top-K
import { computed } from "vue";
import { useResearchStore } from "@/stores/research";
import type { RetrievedChunk } from "@/api/types";

const store = useResearchStore();

const retrievals = computed(() => store.ragRetrievals);

const stages: { key: "dense" | "bm25" | "hybrid" | "reranked"; label: string; color: string }[] = [
  { key: "dense", label: "Dense Retrieval", color: "var(--dr-accent)" },
  { key: "bm25", label: "BM25 (Keyword)", color: "var(--dr-warn)" },
  { key: "hybrid", label: "Hybrid (RRF Fusion)", color: "var(--dr-success)" },
  { key: "reranked", label: "Reranked · Top-K", color: "#a78bfa" },
];

function fmtScore(s?: number): string {
  return (s ?? 0).toFixed(4);
}
</script>

<template>
  <div v-if="retrievals.length === 0" class="dr-card">
    <el-empty
      description="本任务未触发文档库检索 —— 仅当 Agent 调用 retrieve_documents 工具时展示真实 RAG 明细"
      :image-size="72"
    />
  </div>

  <div v-for="(rag, ri) in retrievals" :key="ri" class="dr-card">
    <div class="dr-card__title">
      <el-icon color="var(--dr-accent)"><search /></el-icon>
      RAG Retrieval #{{ ri + 1 }}
      <span class="rag-query mono">{{ rag.query }}</span>
    </div>

    <el-row :gutter="12">
      <el-col v-for="stage in stages" :key="stage.key" :xs="24" :sm="12" :md="6">
        <div class="rag-stage">
          <div class="rag-stage__head" :style="{ borderColor: stage.color }">
            <span class="rag-stage__dot" :style="{ background: stage.color }" />
            <span class="rag-stage__label">{{ stage.label }}</span>
            <span class="rag-stage__count">({{ (rag[stage.key] ?? []).length }})</span>
          </div>
          <div class="rag-stage__body">
            <el-empty
              v-if="(rag[stage.key] ?? []).length === 0"
              description="无结果"
              :image-size="40"
            />
            <div
              v-for="(chunk, ci) in (rag[stage.key] ?? []) as RetrievedChunk[]"
              :key="ci"
              class="rag-chunk"
            >
              <div class="rag-chunk__meta mono">
                <span class="rag-chunk__id">{{ chunk.id }}</span>
                <span class="rag-chunk__score">score {{ fmtScore(chunk.score) }}</span>
              </div>
              <div class="rag-chunk__text">{{ chunk.text }}</div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.rag-query {
  color: var(--dr-text-dim);
  font-weight: 400;
  margin-left: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}
.rag-stage {
  border: 1px solid var(--dr-border);
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}
.rag-stage__head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: var(--dr-bg-soft);
  border-bottom: 2px solid var(--dr-border);
}
.rag-stage__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.rag-stage__label {
  font-size: 12px;
  font-weight: 600;
}
.rag-stage__count {
  font-size: 11px;
  color: var(--dr-text-dim);
}
.rag-stage__body {
  max-height: 320px;
  overflow: auto;
  padding: 8px;
}
.rag-chunk {
  border: 1px solid var(--dr-border);
  border-radius: 6px;
  padding: 6px 8px;
  margin-bottom: 6px;
}
.rag-chunk__meta {
  display: flex;
  justify-content: space-between;
  color: var(--dr-text-dim);
}
.rag-chunk__id {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}
.rag-chunk__score {
  color: var(--dr-accent);
}
.rag-chunk__text {
  font-size: 12px;
  line-height: 1.5;
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

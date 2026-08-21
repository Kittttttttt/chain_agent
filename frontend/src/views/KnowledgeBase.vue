<script setup lang="ts">
// 知识库管理：上传文档 → 自动解析/切块/Embedding/入库；列表；删除；检索测试
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, ref } from "vue";
import { api } from "@/api/client";
import type { KnowledgeDocument, KnowledgeTestResponse, RetrievedChunk } from "@/api/types";

const uploading = ref(false);
const indexing = ref(false);
const testing = ref(false);
const listLoading = ref(false);
const docs = ref<KnowledgeDocument[]>([]);
const urlInput = ref("");
const testQuery = ref("");
const testResult = ref<KnowledgeTestResponse | null>(null);

const acceptExts = ".txt,.md,.markdown,.pdf,.html,.htm";

const fileTypeLabel: Record<string, string> = {
  txt: "TXT",
  markdown: "Markdown",
  pdf: "PDF",
  html: "HTML",
};

async function refresh() {
  listLoading.value = true;
  try {
    docs.value = await api.listKnowledge();
  } catch (e) {
    ElMessage.error(`获取知识库列表失败: ${(e as Error).message}`);
  } finally {
    listLoading.value = false;
  }
}

async function handleUpload(file: File): Promise<boolean> {
  uploading.value = true;
  try {
    const res = await api.uploadKnowledge(file);
    ElMessage.success(`${res.message}（${file.name} → ${res.chunks} chunks）`);
    await refresh();
    return true;
  } catch (e) {
    const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? (e as Error).message;
    ElMessage.error(`上传失败: ${msg}`);
    return false;
  } finally {
    uploading.value = false;
  }
}

function onUploadChange(u: { file: File }) {
  if (u.file && u.file.name) {
    void handleUpload(u.file);
  }
}

async function handleIndexUrl() {
  const url = urlInput.value.trim();
  if (!url) return;
  indexing.value = true;
  try {
    const res = await api.indexKnowledge({ url });
    ElMessage.success(`${res.message}`);
    urlInput.value = "";
    await refresh();
  } catch (e) {
    const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? (e as Error).message;
    ElMessage.error(`URL 入库失败: ${msg}`);
  } finally {
    indexing.value = false;
  }
}

async function handleDelete(doc: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm(
      `删除文档「${doc.title || doc.document_id}」及其全部 ${doc.chunk_count} 个 chunk？`,
      "删除确认",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return; // 用户取消
  }
  try {
    const res = await api.deleteKnowledge(doc.document_id);
    ElMessage.success(res.message);
    await refresh();
  } catch (e) {
    const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? (e as Error).message;
    ElMessage.error(`删除失败: ${msg}`);
  }
}

async function handleTest() {
  const query = testQuery.value.trim();
  if (!query) return;
  testing.value = true;
  try {
    testResult.value = await api.testKnowledge({ query, top_k: 5 });
  } catch (e) {
    ElMessage.error(`检索测试失败: ${(e as Error).message}`);
  } finally {
    testing.value = false;
  }
}

const testStages: { key: "dense" | "bm25" | "hybrid" | "reranked"; label: string; color: string }[] = [
  { key: "dense", label: "Dense Retrieval", color: "var(--dr-accent)" },
  { key: "bm25", label: "BM25 (Keyword)", color: "var(--dr-warn)" },
  { key: "hybrid", label: "Hybrid (RRF Fusion)", color: "var(--dr-success)" },
  { key: "reranked", label: "Reranked · Top-K", color: "#a78bfa" },
];

function fmtScore(s?: number): string {
  return (s ?? 0).toFixed(4);
}

onMounted(refresh);
</script>

<template>
  <div class="kb-page">
    <!-- 上传区 -->
    <div class="dr-card">
      <div class="dr-card__title">
        <el-icon color="var(--dr-accent)"><upload-filled /></el-icon>
        文档入库
        <span class="dr-card__sub">Loader → Cleaning → Chunking → BGE-M3 Embedding → Qdrant + BM25</span>
      </div>

      <el-upload
        drag
        multiple
        :accept="acceptExts"
        :auto-upload="false"
        :show-file-list="false"
        :disabled="uploading"
        @change="onUploadChange"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 TXT / Markdown / PDF / HTML（PDF 需后端已安装 pypdf），上传后自动解析并入库</div>
        </template>
      </el-upload>

      <div class="kb-url-row">
        <el-input
          v-model="urlInput"
          placeholder="或输入网页 URL，抓取后作为 HTML 文档入库"
          clearable
          :disabled="indexing"
          @keyup.enter="handleIndexUrl"
        >
          <template #append>
            <el-button :loading="indexing" @click="handleIndexUrl">URL 入库</el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 文档列表 -->
    <div class="dr-card">
      <div class="dr-card__title">
        <el-icon color="var(--dr-accent)"><collection /></el-icon>
        知识库文档
        <el-button size="small" text class="dr-card__refresh" @click="refresh">刷新</el-button>
      </div>

      <el-table :data="docs" v-loading="listLoading" size="small">
        <el-table-column label="标题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="kb-doc-title">{{ row.title || row.document_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.file_type === 'pdf' ? 'danger' : row.file_type === 'markdown' ? 'success' : 'info'">
              {{ fileTypeLabel[row.file_type] ?? row.file_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Chunks" width="90" prop="chunk_count" align="center" />
        <el-table-column label="Pages" width="80" prop="page_count" align="center" />
        <el-table-column label="Document ID" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono kb-doc-id">{{ row.document_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button size="small" type="danger" text @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!listLoading && docs.length === 0" description="知识库为空，请先上传文档" :image-size="64" />
    </div>

    <!-- 检索测试 -->
    <div class="dr-card">
      <div class="dr-card__title">
        <el-icon color="var(--dr-accent)"><search /></el-icon>
        检索测试
        <span class="dr-card__sub">Dense + BM25 → Hybrid (RRF) → Reranker → Top-K</span>
      </div>

      <div class="kb-test-row">
        <el-input
          v-model="testQuery"
          placeholder="输入测试查询，观察各检索阶段真实命中（如：RAG 混合检索 重排序）"
          clearable
          :disabled="testing"
          @keyup.enter="handleTest"
        >
          <template #append>
            <el-button type="primary" :loading="testing" @click="handleTest">检索</el-button>
          </template>
        </el-input>
      </div>

      <template v-if="testResult">
        <div class="kb-test-query mono">Query: {{ testResult.query }}</div>
        <el-row :gutter="12">
          <el-col v-for="stage in testStages" :key="stage.key" :xs="24" :sm="12" :md="6">
            <div class="rag-stage">
              <div class="rag-stage__head" :style="{ borderColor: stage.color }">
                <span class="rag-stage__dot" :style="{ background: stage.color }" />
                <span class="rag-stage__label">{{ stage.label }}</span>
                <span class="rag-stage__count">({{ (testResult[stage.key] ?? []).length }})</span>
              </div>
              <div class="rag-stage__body">
                <el-empty
                  v-if="(testResult[stage.key] ?? []).length === 0"
                  description="无结果"
                  :image-size="40"
                />
                <div
                  v-for="(chunk, ci) in (testResult[stage.key] ?? []) as RetrievedChunk[]"
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
      </template>
    </div>
  </div>
</template>

<style scoped>
.kb-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.kb-url-row,
.kb-test-row {
  margin-top: 14px;
}
.kb-doc-title {
  font-weight: 500;
}
.kb-doc-id {
  font-size: 12px;
  color: var(--dr-text-dim);
}
.kb-test-query {
  margin: 12px 0;
  color: var(--dr-text-dim);
  font-size: 13px;
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
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

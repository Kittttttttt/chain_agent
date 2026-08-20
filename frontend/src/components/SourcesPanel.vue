<script setup lang="ts">
// Sources / Evidence / Citations 面板（Claim → Evidence → Source 映射）
import { computed } from "vue";
import { useResearchStore } from "@/stores/research";

const store = useResearchStore();

const stats = computed(() => ({
  sources: store.sources.length,
  evidence: store.evidence.length,
  citations: store.citations.length,
  verified: store.citations.filter((c) => c.status === "verified").length,
  unverified: store.citations.filter((c) => c.status === "unverified").length,
}));

const typeLabel: Record<string, string> = {
  web: "网页",
  arxiv: "论文",
  github: "代码",
  document: "文档",
};

function fmtTime(t?: string | null): string {
  if (!t) return "—";
  return t.slice(0, 10);
}

function typeTag(t?: string): "primary" | "success" | "warning" | "info" {
  switch (t) {
    case "web":
      return "primary";
    case "arxiv":
      return "success";
    case "github":
      return "warning";
    default:
      return "info";
  }
}
</script>

<template>
  <div v-if="stats.citations + stats.evidence + stats.sources === 0" class="dr-card">
    <el-empty description="暂无来源 / 证据" :image-size="72" />
  </div>

  <template v-else>
    <!-- 统计 -->
    <div class="dr-card">
      <div class="stats">
        <div class="stat"><span class="stat__num">{{ stats.sources }}</span><span class="stat__label">来源</span></div>
        <div class="stat"><span class="stat__num">{{ stats.evidence }}</span><span class="stat__label">证据</span></div>
        <div class="stat">
          <span class="stat__num">{{ stats.citations }}</span><span class="stat__label">引用</span>
          <span class="stat__sub verified">✓ {{ stats.verified }}</span>
          <span class="stat__sub unverified">? {{ stats.unverified }}</span>
        </div>
      </div>
    </div>

    <!-- 引用（Claim → Source 映射） -->
    <div v-if="store.citations.length" class="dr-card">
      <div class="dr-card__title">
        Citations <el-tag size="small" type="success">verified {{ stats.verified }}</el-tag>
        <el-tag size="small" type="warning">unverified {{ stats.unverified }}</el-tag>
      </div>
      <el-table :data="store.citations" size="small" max-height="360">
        <el-table-column prop="claim" label="Claim" min-width="240" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'verified' ? 'success' : 'warning'" size="small">
              {{ row.status === "verified" ? "verified" : "unverified" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="90">
          <template #default="{ row }">{{ (row.confidence ?? 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="来源" min-width="220">
          <template #default="{ row }">
            <a :href="row.source?.url" target="_blank" rel="noopener">{{ row.source?.title || row.source?.url }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="校验说明" min-width="180" show-overflow-tooltip />
      </el-table>
    </div>

    <!-- 证据（Evidence ↔ Claim 对应） -->
    <div v-if="store.evidence.length" class="dr-card">
      <div class="dr-card__title">Evidence</div>
      <el-table :data="store.evidence" size="small" max-height="360">
        <el-table-column prop="claim" label="Claim" min-width="260" show-overflow-tooltip />
        <el-table-column label="来源" min-width="220">
          <template #default="{ row }">
            <div>
              <a :href="row.source?.url" target="_blank" rel="noopener">{{ row.source?.title || row.source?.url }}</a>
              <div class="src-meta">
                <el-tag size="small" :type="typeTag(row.source?.source_type)" effect="plain">
                  {{ typeLabel[row.source?.source_type] ?? row.source?.source_type }}
                </el-tag>
                <span v-if="row.source?.published_at" class="mono"> {{ fmtTime(row.source.published_at) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Relevance" width="110">
          <template #default="{ row }">
            <el-progress :percentage="Math.round((row.relevance ?? 0) * 100)" :stroke-width="6" />
          </template>
        </el-table-column>
        <el-table-column label="Confidence" width="110">
          <template #default="{ row }">
            <el-progress :percentage="Math.round((row.confidence ?? 0) * 100)" :stroke-width="6" />
          </template>
        </el-table-column>
        <el-table-column label="验证" width="90">
          <template #default="{ row }">
            <el-tag :type="row.verified ? 'success' : 'info'" size="small">
              {{ row.verified ? "verified" : "—" }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 来源列表 -->
    <div v-if="store.sources.length" class="dr-card">
      <div class="dr-card__title">Sources</div>
      <el-table :data="store.sources" size="small" max-height="360">
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTag(row.source_type)" effect="plain">
              {{ typeLabel[row.source_type] ?? row.source_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="URL" min-width="260">
          <template #default="{ row }">
            <a :href="row.url" target="_blank" rel="noopener" class="mono">{{ row.url }}</a>
          </template>
        </el-table-column>
        <el-table-column label="发布日期" width="110">
          <template #default="{ row }">{{ fmtTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column prop="snippet" label="摘要" min-width="200" show-overflow-tooltip />
      </el-table>
    </div>
  </template>
</template>

<style scoped>
.stats {
  display: flex;
  gap: 40px;
}
.stat {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.stat__num {
  font-size: 26px;
  font-weight: 700;
  color: var(--dr-accent);
}
.stat__label {
  color: var(--dr-text-dim);
}
.stat__sub {
  font-size: 12px;
}
.stat__sub.verified {
  color: var(--dr-success);
}
.stat__sub.unverified {
  color: var(--dr-warn);
}
.src-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
}
</style>

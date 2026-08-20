<script setup lang="ts">
// 最终报告：Markdown 渲染 + [来源N] 引用定位 + unverified 高亮
import { computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { useResearchStore } from "@/stores/research";

const props = defineProps<{ report: string }>();
const emit = defineEmits<{ (e: "locate", index: number): void }>();

const store = useResearchStore();

/** 被标记为 unverified 的来源 URL 集合 */
const unverifiedUrls = computed(
  () => new Set(store.citations.filter((c) => c.status === "unverified").map((c) => c.source.url)),
);

const html = computed(() => {
  const withRefs = props.report.replace(
    /\[来源(\d+)\]/g,
    (m, n) => `<span class="citation-ref" data-cite="${n}">${m}</span>`,
  );
  const raw = marked.parse(withRefs, { async: false, breaks: true }) as string;
  return DOMPurify.sanitize(raw);
});

function onBodyClick(e: MouseEvent) {
  const el = (e.target as HTMLElement).closest(".citation-ref") as HTMLElement | null;
  if (!el) return;
  const n = Number(el.dataset.cite);
  if (n >= 1) emit("locate", n);
}
</script>

<template>
  <div v-if="!report" class="dr-card">
    <el-empty description="报告尚未生成" :image-size="72" />
  </div>
  <div v-else class="dr-card">
    <div class="dr-card__title">
      <el-icon color="var(--dr-warn)"><document /></el-icon>
      Final Report
      <span class="report-meta mono">{{ report.length }} 字符</span>
    </div>
    <div
      class="markdown-body"
      v-html="html"
      @click="onBodyClick"
    />
  </div>
</template>

<style scoped>
.report-meta {
  color: var(--dr-text-dim);
  font-weight: 400;
}
</style>

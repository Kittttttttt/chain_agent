<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useSettingsStore } from "@/stores/settings";

const settings = useSettingsStore();
const route = useRoute();
const activePath = ref(route.path);

const nav = [
  { path: "/research", label: "Research Console" },
  { path: "/runs", label: "历史任务" },
  { path: "/knowledge", label: "知识库" },
  { path: "/settings", label: "配置" },
];

onMounted(() => settings.refresh());
</script>

<template>
  <el-container class="shell">
    <el-header class="shell__header">
      <div class="brand">
        <span class="brand__dot" />
        <span class="brand__name">DeepResearch Agent Console</span>
      </div>
      <el-menu
        :default-active="activePath"
        mode="horizontal"
        class="shell__menu"
        :ellipsis="false"
        router
        @select="(p: string) => (activePath = p)"
      >
        <el-menu-item v-for="item in nav" :key="item.path" :index="item.path">
          {{ item.label }}
        </el-menu-item>
      </el-menu>
      <div class="backend-status" :class="{ offline: !settings.backendOnline }">
        <span class="dot" />
        {{ settings.backendOnline ? "Backend Online" : "Backend Offline" }}
      </div>
    </el-header>
    <el-main class="shell__main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style scoped>
.shell {
  height: 100vh;
}
.shell__header {
  display: flex;
  align-items: center;
  gap: 24px;
  background: var(--dr-bg-soft);
  border-bottom: 1px solid var(--dr-border);
  padding: 0 24px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  letter-spacing: 0.3px;
  white-space: nowrap;
}
.brand__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--dr-accent);
  box-shadow: 0 0 8px var(--dr-accent);
}
.shell__menu {
  flex: 1;
  border-bottom: none;
  background: transparent;
}
.backend-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--dr-success);
  white-space: nowrap;
}
.backend-status .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dr-success);
}
.backend-status.offline {
  color: var(--dr-danger);
}
.backend-status.offline .dot {
  background: var(--dr-danger);
}
.shell__main {
  padding: 0;
  overflow: auto;
  background: var(--dr-bg);
}
</style>

// 设置 Store：读取后端运行配置（只读展示，不直连数据库/LLM）
import { defineStore } from "pinia";
import { api } from "@/api/client";
import type { HealthInfo } from "@/api/types";

export const useSettingsStore = defineStore("settings", {
  state: () => ({
    health: null as HealthInfo | null,
    backendOnline: false,
  }),
  actions: {
    async refresh() {
      try {
        this.health = await api.health();
        this.backendOnline = true;
      } catch {
        this.backendOnline = false;
      }
    },
  },
});

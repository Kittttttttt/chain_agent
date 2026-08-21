import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/research" },
    {
      path: "/research",
      name: "research",
      component: () => import("@/views/ResearchConsole.vue"),
    },
    {
      path: "/runs",
      name: "runs",
      component: () => import("@/views/RunsList.vue"),
    },
    {
      path: "/knowledge",
      name: "knowledge",
      component: () => import("@/views/KnowledgeBase.vue"),
    },
    {
      path: "/runs/:id",
      name: "run-detail",
      component: () => import("@/views/RunDetail.vue"),
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("@/views/SettingsView.vue"),
    },
  ],
});

export default router;

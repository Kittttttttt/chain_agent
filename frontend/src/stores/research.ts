// ---------------------------------------------------------------------------
// 研究任务 Store：SSE 实时事件流 + 完整结果
// ---------------------------------------------------------------------------
import { defineStore } from "pinia";
import { api, subscribeRunStream } from "@/api/client";
import type {
  AgentEvent,
  Citation,
  Evidence,
  ResearchDepth,
  ResearchRequest,
  ResearchResult,
  ResearchStatus,
  Source,
  SseEventFrame,
} from "@/api/types";

interface ResearchState {
  researchId: string | null;
  status: ResearchStatus;
  question: string;
  depth: ResearchDepth;
  events: AgentEvent[];
  report: string;
  sources: Source[];
  evidence: Evidence[];
  citations: Citation[];
  metrics: Record<string, unknown>;
  error: string | null;
  connected: boolean;
  starting: boolean;
}

export const useResearchStore = defineStore("research", {
  state: (): ResearchState => ({
    researchId: null,
    status: "idle",
    question: "",
    depth: "standard",
    events: [],
    report: "",
    sources: [],
    evidence: [],
    citations: [],
    metrics: {},
    error: null,
    connected: false,
    starting: false,
  }),

  getters: {
    isActive: (s) => s.status === "running" || s.status === "queued",
    /** 聚合后的 Trace 面板条目（从实时事件流派生） */
    traceEntries(state): Array<Record<string, unknown>> {
      return state.events.map((ev) => ({ ...ev }));
    },
    /** RAG 检索明细事件（供检索面板展示） */
    ragRetrievals(state): AgentEvent[] {
      return state.events.filter((e) => e.type === "rag_retrieval");
    },
  },

  actions: {
    reset() {
      this.$patch({
        researchId: null,
        status: "idle",
        question: "",
        depth: "standard",
        events: [],
        report: "",
        sources: [],
        evidence: [],
        citations: [],
        metrics: {},
        error: null,
        connected: false,
        starting: false,
      });
    },

    /** 提交新研究并订阅 SSE */
    async start(req: ResearchRequest) {
      this.reset();
      this.starting = true;
      this.question = req.question;
      this.depth = req.depth;
      try {
        const resp = await api.startResearch(req);
        this.researchId = resp.research_id;
        this.subscribe(resp.research_id);
      } finally {
        this.starting = false;
      }
    },

    /** 订阅 SSE 实时事件 */
    subscribe(id: string) {
      this.connected = false;
      subscribeRunStream(
        id,
        (frame) => this.onFrame(frame),
        () => {
          this.connected = false;
        },
      );
    },

    onFrame(frame: SseEventFrame) {
      if (frame.event === "agent") {
        this.events.push(frame.data as AgentEvent);
      } else if (frame.event === "status") {
        const d = frame.data as { status: ResearchStatus };
        this.status = d.status;
      } else if (frame.event === "done") {
        this.applyResult(frame.data as ResearchResult);
      } else if (frame.event === "error") {
        const d = frame.data as { detail: string };
        this.error = d.detail;
        this.status = "failed";
      }
    },

    /** 从完整结果填充（done 事件或 GET 拉取） */
    applyResult(r: ResearchResult) {
      this.researchId = r.research_id;
      this.status = r.status;
      this.question = r.question;
      this.report = r.report;
      this.sources = r.sources;
      this.evidence = r.evidence;
      this.citations = r.citations;
      this.metrics = r.metrics;
      this.error = r.error;
      if (r.events?.length) this.events = r.events;
    },

    /** 历史任务详情页：加载完整结果 + 事件流 */
    async loadRun(id: string) {
      this.reset();
      this.researchId = id;
      const r = await api.getRun(id);
      this.applyResult(r);
      // running 中则订阅实时事件
      if (r.status === "running" || r.status === "queued") {
        this.subscribe(id);
      }
    },
  },
});

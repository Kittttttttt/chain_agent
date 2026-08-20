// ---------------------------------------------------------------------------
// 与后端 FastAPI 契约对齐的类型定义
// ---------------------------------------------------------------------------

/** 信息源（网页 / 论文 / 代码仓库） */
export interface Source {
  url: string;
  title: string;
  source_type: "web" | "arxiv" | "github" | "document";
  published_at?: string | null;
  snippet: string;
  metadata?: Record<string, unknown>;
}

/** 证据：一个可被引用的信息片段 */
export interface Evidence {
  claim: string;
  source: Source;
  relevance: number;
  confidence: number;
  verified: boolean;
  verification_note: string;
}

/** 引用：报告中的关键声明与来源的映射 */
export interface Citation {
  claim: string;
  source: Source;
  status: "verified" | "unverified";
  confidence: number;
  reason: string;
}

/** Planner 子任务 */
export interface Subtask {
  id: string;
  question: string;
  priority: "high" | "medium" | "low";
  required_sources: string[];
  status: "pending" | "in_progress" | "done" | "failed";
  result_summary: string;
}

export interface ResearchPlan {
  goal: string;
  subtasks: Subtask[];
}

/** 检索片段（RAG 各阶段结果） */
export interface RetrievedChunk {
  id: string;
  text: string;
  score: number;
  metadata: Record<string, unknown>;
}

export type ResearchDepth = "quick" | "standard" | "deep";
export type ResearchStatus = "idle" | "queued" | "running" | "completed" | "failed";

export interface ResearchRequest {
  question: string;
  depth: ResearchDepth;
  max_iterations?: number | null;
}

export interface ResearchResponse {
  research_id: string;
  status: string;
  message: string;
}

/** 一次研究的完整结果 */
export interface ResearchResult {
  research_id: string;
  status: ResearchStatus;
  question: string;
  report: string;
  sources: Source[];
  evidence: Evidence[];
  citations: Citation[];
  metrics: Record<string, unknown>;
  trace: Array<Record<string, unknown>>;
  events: AgentEvent[];
  error: string | null;
}

/** 历史任务摘要 */
export interface RunSummary {
  research_id: string;
  question: string;
  depth: ResearchDepth;
  status: ResearchStatus;
  created_at: number;
  sufficiency_score?: number | null;
  evidence_count?: number | null;
  tool_call_count?: number | null;
}

export interface HealthInfo {
  status: string;
  app: string;
  version: string;
  llm_provider: string;
  search_provider: string;
  vector_backend: string;
  embedding_provider: string;
}

// ---------------------------------------------------------------------------
// Agent 执行事件（SSE / agent 事件）
// ---------------------------------------------------------------------------

/** 工具调用 → 执行阶段（后端权威映射） */
export type ToolPhase =
  | "web_search"
  | "arxiv_search"
  | "github_search"
  | "read_source"
  | "rag_retrieval"
  | "tool_call";

/** Agent Trace 节点 */
export type AgentNode =
  | "research_intake"
  | "planner"
  | "research_worker"
  | "evidence_extraction"
  | "evidence_evaluation"
  | "report_writer"
  | "citation_verification"
  | "evaluator";

export interface AgentEvent {
  type:
    | "node_start"
    | "node_end"
    | "planner_plan"
    | "tool_call"
    | "rag_retrieval"
    | "evidence_evaluated"
    | "report_generated"
    | "citation_verified"
    | "evaluator_done";
  ts: number;
  // 通用
  node?: AgentNode;
  latency_ms?: number;
  status?: string;
  // planner_plan
  plan?: ResearchPlan;
  // tool_call
  tool?: string;
  phase?: ToolPhase;
  input?: Record<string, unknown>;
  success?: boolean;
  output_summary?: string;
  error?: string;
  // rag_retrieval
  query?: string;
  dense?: RetrievedChunk[];
  bm25?: RetrievedChunk[];
  hybrid?: RetrievedChunk[];
  reranked?: RetrievedChunk[];
  // evidence_evaluated
  sufficiency_score?: number;
  evidence_count?: number;
  threshold?: number;
  // report_generated
  length?: number;
  // citation_verified
  citations?: Citation[];
  verified_count?: number;
  unverified_count?: number;
  // evaluator_done
  metrics?: Record<string, unknown>;
}

/** SSE 事件帧（EventSource 的命名事件） */
export type SseEventFrame = {
  event: "agent" | "status" | "done" | "error";
  data: unknown;
};

// ---------------------------------------------------------------------------
// 前端派生类型
// ---------------------------------------------------------------------------

/** Trace 面板：聚合后的节点/阶段条目 */
export interface TraceEntry {
  key: string;
  phase: string;
  label: string;
  status: "pending" | "running" | "done" | "failed";
  latencyMs?: number;
  detail: string;
  extra?: AgentEvent;
}

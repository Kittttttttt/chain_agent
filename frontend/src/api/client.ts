// ---------------------------------------------------------------------------
// API 客户端：axios 调用 FastAPI（前端仅通过后端 API 通信）
// ---------------------------------------------------------------------------
import axios from "axios";
import type {
  HealthInfo,
  KnowledgeDocument,
  KnowledgeIndexRequest,
  KnowledgeTestRequest,
  KnowledgeTestResponse,
  KnowledgeUploadResponse,
  ResearchRequest,
  ResearchResponse,
  ResearchResult,
  RunSummary,
  SseEventFrame,
} from "./types";

const http = axios.create({
  baseURL: "/", // 走 vite proxy → http://127.0.0.1:8000
  timeout: 120_000,
});

export const api = {
  health: () => http.get<HealthInfo>("/health").then((r) => r.data),

  /** 发起异步研究任务 */
  startResearch: (req: ResearchRequest) =>
    http.post<ResearchResponse>("/api/research", req).then((r) => r.data),

  /** 历史任务列表 */
  listRuns: () =>
    http.get<{ items: RunSummary[]; total: number }>("/api/research").then((r) => r.data),

  /** 单个任务完整结果 */
  getRun: (id: string) =>
    http.get<ResearchResult>(`/api/research/${id}`).then((r) => r.data),

  // -------------------------------------------------------------------------
  // 知识库
  // -------------------------------------------------------------------------

  /** 上传文档（TXT/Markdown/PDF/HTML）→ 自动解析/切块/Embedding/入库 */
  uploadKnowledge: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return http
      .post<KnowledgeUploadResponse>("/api/knowledge/upload", form, {
        timeout: 180_000,
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  /** 从文本 / URL 索引入库 */
  indexKnowledge: (req: KnowledgeIndexRequest) =>
    http.post<KnowledgeUploadResponse>("/api/knowledge/index", req, { timeout: 120_000 }).then((r) => r.data),

  /** 知识库文档列表 */
  listKnowledge: () =>
    http.get<KnowledgeDocument[]>("/api/knowledge/documents").then((r) => r.data),

  /** 删除文档（Qdrant + BM25 同步） */
  deleteKnowledge: (documentId: string) =>
    http
      .delete<{ document_id: string; deleted_chunks: number; message: string }>(
        `/api/knowledge/${encodeURIComponent(documentId)}`,
      )
      .then((r) => r.data),

  /** 检索测试（Dense/BM25/Hybrid/Rerank 各阶段明细） */
  testKnowledge: (req: KnowledgeTestRequest) =>
    http.post<KnowledgeTestResponse>("/api/knowledge/test", req).then((r) => r.data),
};

/**
 * 订阅研究任务 SSE 流。
 * 返回取消函数。onFrame 收到已解析的命名事件帧。
 */
export function subscribeRunStream(
  id: string,
  onFrame: (frame: SseEventFrame) => void,
  onError: (err: unknown) => void,
): () => void {
  const es = new EventSource(`/api/research/${id}/stream`);
  const handlers: Record<string, (raw: string) => void> = {
    agent: (raw) => onFrame({ event: "agent", data: JSON.parse(raw) }),
    status: (raw) => onFrame({ event: "status", data: JSON.parse(raw) }),
    done: (raw) => onFrame({ event: "done", data: JSON.parse(raw) }),
    error: (raw) => onFrame({ event: "error", data: JSON.parse(raw) }),
  };
  for (const name of Object.keys(handlers)) {
    es.addEventListener(name, (e) => {
      const msg = e as MessageEvent;
      try {
        handlers[name](msg.data);
      } catch (err) {
        onError(err);
      }
    });
  }
  es.onerror = (e) => onError(e);
  return () => es.close();
}

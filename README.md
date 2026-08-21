# DeepResearch Agent

基于 **LangGraph** 的多阶段自主深度研究智能体（Deep Research Agent）+ 自研 RAG 知识库。

用户输入一个复杂研究问题，系统自动完成：任务拆解 → 制定研究计划 → 并行执行子任务 →
调用 Web/ArXiv/GitHub 工具 → 网页/论文阅读 → RAG 检索（Dense + BM25 + Hybrid + Rerank）→
证据抽取 → 充分性判断 → 迭代研究 → 报告生成 → 引用校验 → 执行评估。

输出不是普通聊天答案，而是**结构化、可引用、可验证、带来源的深度研究报告**。

---

## 核心特性

| 模块 | 说明 |
|---|---|
| Agent Loop | LangGraph StateGraph：Planner → Worker → Tool → Observation → Evaluation → Continue/Finish 真实循环 |
| Tool Calling | 统一 Tool 层（Pydantic Schema / 超时 / 重试 / 错误处理 / 调用记录），LLM 自主选工具 |
| RAG Retrieval | Dense Retrieval + BM25 + Hybrid(RRF) + Rerank → Top-K Evidence，可插拔 Embedding / 向量库 |
| Document Ingestion | 自研统一 Loader（TXT / Markdown / PDF(pypdf) / HTML+URL）→ Cleaning → Chunking → 入库，不依赖 LangChain |
| Chunking | 标题 → 段落 → 句子 → 固定长度 逐级切分（默认 512/64），chunk 保留 source/page/chunk_id 溯源 |
| Knowledge Base | 上传/URL 入库、文档列表、删除、检索测试 API + Vue 前端页面 |
| Embedding | 默认 BGE-M3（1024 维，OpenAI 兼容接口），支持 DashScope / Mock 切换 |
| Citation | Claim → Evidence → Source 映射，无法验证的引用标记 `unverified`，禁止编造 |
| Memory | 短时记忆（LangGraph Checkpointer）+ 长时记忆（SQLite）+ Context 压缩 |
| MCP | FastMCP Server 独立暴露 search/arxiv/github/document 工具 |
| Evaluation | 基线对比（单 LLM / 搜索+LLM）+ 指标 + Benchmark 报告 |
| Observability | LangSmith Tracing（llm_provider / tools / tokens / latency） |

## 架构

```text
User → FastAPI → LangGraph(Planner → Worker ⟲ Sufficiency) → RAG → Report → Citation → Evaluator
                                     │
                          Tool Layer: search_web / search_arxiv / search_github / read_webpage / retrieve_documents
                                     │
                          ┌──────────▼─────────── RAG Pipeline（自研，无 LangChain）──────────┐
                          │  Document Loader → Cleaning → Chunking → BGE-M3 Embedding        │
                          │  → Qdrant(向量) + BM25(关键词) → Dense+BM25 → RRF Hybrid → Rerank │
                          └──────────────────────────────────────────────────────────────────┘
```

## 目录结构

```text
backend/           FastAPI 应用（app/api agents graph tools rag memory models services config + data + tests）
frontend/          Vue3 + TypeScript + Vite + Element Plus 前端（研究控制台 / 历史任务 / 知识库 / 配置）
mcp_servers/       FastMCP 独立 MCP Server
eval/              数据集 + 基线 + 指标 + Benchmark 报告
scripts/           演示脚本
docker/            Dockerfile
```

## 快速开始

### 1. 安装依赖

```bash
conda activate lchain_demo
pip install -r requirements.txt
# 若 qdrant-client 未安装成功，手动安装（可选，未装自动回退内存向量库）：
python -m pip install qdrant-client
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env：填入 DEEPSEEK_API_KEY；RAG 使用 BGE-M3 时填 SILICONFLOW_API_KEY
#   EMBEDDING_PROVIDER=siliconflow / EMBEDDING_MODEL=BAAI/bge-m3 / EMBEDDING_DIM=1024
```

### 3. 运行演示（命令行）

```bash
python scripts/run_demo.py "什么是 LangGraph 的 StateGraph？"
```

> 未配置 LLM Key 时自动使用 Mock 模型，可跑通完整链路（演示 Agent 状态机）。

### 4. 启动后端 API

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 5. 启动前端（新终端，端口 5173）

```powershell
cd D:\some_code\trae_code\DeepResearch\frontend
npm install
npm run dev
# 浏览器打开 http://localhost:5173
```

## API 一览

### 研究任务

| 端点 | 说明 |
|---|---|
| `GET /health` | 健康检查 |
| `POST /api/research` | 异步受理研究任务 |
| `POST /api/research/sync` | 同步执行（测试用） |
| `GET /api/research/{id}` | 研究结果 |
| `GET /api/research/{id}/trace` | 执行轨迹 |
| `GET /api/research/{id}/sources` | 来源列表 |
| `GET /api/research/{id}/evaluation` | 评估指标 |
| `GET /api/research/{id}/stream` | SSE 流式进度 |

### 知识库

| 端点 | 说明 |
|---|---|
| `POST /api/knowledge/upload` | 上传文件（TXT/Markdown/PDF/HTML），自动解析 → Chunk → Embedding → 入库 |
| `POST /api/knowledge/index` | 文本或 URL 入库 |
| `GET /api/knowledge/documents` | 文档列表（标题/类型/Chunk 数/页数/ID） |
| `DELETE /api/knowledge/{document_id}` | 删除文档（同步清理 Qdrant + BM25） |
| `POST /api/knowledge/test` | 检索测试（Dense / BM25 / Hybrid / Reranked 各阶段） |

## 设计要点

- **Sufficiency Check**：根据证据数量、置信度、来源可用性计算得分，判断继续研究还是进入报告，非固定循环次数。
- **不编造引用**：报告引用必须映射到真实检索来源，无法验证标记 `unverified`。
- **RAG 禁止绕过 Pipeline**：所有入库必须走 Loader → Cleaning → Chunking → Embedding → Qdrant + BM25 统一入口，不允许直写向量库。
- **可追溯**：每个 chunk 携带 `doc_id / source / page / chunk_id`，Evidence 与 Citation 可回溯到原文。
- **BM25 中文支持**：单字 + bigram 双字组 tokenizer，服务启动时从 Qdrant 重建。
- **可插拔**：搜索（DDG/Tavily）、Embedding（SiliconFlow-BGE-M3/DashScope/Mock）、向量库（Qdrant/内存）、记忆（SQLite）均通过接口切换。
- **Context 管理**：滚动窗口 + 摘要压缩 + Token 预算裁剪，避免 Context 无限增长。

## 运行测试

```bash
cd backend
pytest -v          # 单元 + 集成测试（含 TXT/Markdown/PDF 解析与入库）
```

## 运行评测

```bash
python eval/run_evaluation.py        # 4 条子集
python eval/run_evaluation.py --full # 全部 20 题
```

## 技术栈

Python 3.11+（开发环境 3.14.3） · LangGraph · LangChain · FastAPI · Qdrant · pypdf · FastMCP · LangSmith ·
Vue3 · TypeScript · Vite · Element Plus · Pinia · Pydantic · SQLite · pytest

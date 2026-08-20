# DeepResearch Agent

基于 **LangGraph** 的多阶段自主深度研究智能体（Deep Research Agent）。

用户输入一个复杂研究问题，系统自动完成：任务拆解 → 制定研究计划 → 并行执行子任务 →
调用 Web/ArXiv/GitHub 工具 → 网页/论文阅读 → RAG 检索（Dense + BM25 + Hybrid + Rerank）→
证据抽取 → 充分性判断 → 迭代研究 → 报告生成 → 引用校验 → 执行评估。

输出不是普通聊天答案，而是**结构化、可引用、可验证、带来源的深度研究报告**。

---

## 核心特性

| 模块          | 说明                                                                                                     |
| ------------- | -------------------------------------------------------------------------------------------------------- |
| Agent Loop    | LangGraph StateGraph：Planner → Worker → Tool → Observation → Evaluation → Continue/Finish 真实循环 |
| Tool Calling  | 统一 Tool 层（Pydantic Schema / 超时 / 重试 / 错误处理 / 调用记录），LLM 自主选工具                      |
| RAG           | Dense Retrieval + BM25 + Hybrid(RRF) + Rerank，可插拔 Embedding / 向量库                                 |
| Citation      | Claim → Evidence → Source 映射，无法验证的引用标记`unverified`，禁止编造                             |
| Memory        | 短时记忆（LangGraph Checkpointer）+ 长时记忆（SQLite/PostgreSQL）+ Context 压缩                          |
| MCP           | FastMCP Server 独立暴露 search/arxiv/github/document 工具                                                |
| Evaluation    | 基线对比（单 LLM / 搜索+LLM）+ 指标 + Benchmark 报告                                                     |
| Observability | LangSmith Tracing（llm_provider / tools / tokens / latency）                                             |

## 架构

```text
User → FastAPI → LangGraph(Planner → Worker ⟲ Sufficiency) → RAG → Report → Citation → Evaluator
                                     │
                          Tool Layer: search_web / search_arxiv / search_github / read_webpage / retrieve_documents
```

## 目录结构

```text
backend/           FastAPI 应用（app/api agents graph tools rag memory models services config）
mcp_servers/       FastMCP 独立 MCP Server
eval/              数据集 + 基线 + 指标 + Benchmark 报告
scripts/           演示脚本
docs/              文档
docker/            Dockerfile
tests/             pytest 单元 + 集成测试
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
# 编辑 .env：填入 DEEPSEEK_API_KEY 等
```

### 3. 运行演示（命令行）

```bash
python scripts/run_demo.py "什么是 LangGraph 的 StateGraph？"
```

> 未配置 LLM Key 时自动使用 Mock 模型，可跑通完整链路（演示 Agent 状态机）。

### 4. 启动 API

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

| 端点                                  | 说明               |
| ------------------------------------- | ------------------ |
| `GET /health`                       | 健康检查           |
| `POST /api/research`                | 异步受理研究任务   |
| `POST /api/research/sync`           | 同步执行（测试用） |
| `GET /api/research/{id}`            | 研究结果           |
| `GET /api/research/{id}/trace`      | 执行轨迹           |
| `GET /api/research/{id}/sources`    | 来源列表           |
| `GET /api/research/{id}/evaluation` | 评估指标           |
| `GET /api/research/{id}/stream`     | SSE 流式进度       |



```powershell
# 3. 启动前端 Vite（新终端，端口 5173）
cd D:\some_code\trae_code\DeepResearch\frontend
npm run dev
```

### 5. 运行 MCP Server

```bash
python mcp_servers/research_server.py
```

### 6. 运行测试

```bash
cd backend && pytest -v
```

### 7. 运行评测

```bash
python eval/run_evaluation.py        # 4 条子集
python eval/run_evaluation.py --full # 全部 20 题
```

## 设计要点

- **Sufficiency Check**：根据证据数量、置信度、来源可用性计算得分，判断继续研究还是进入报告，非固定循环次数。
- **不编造引用**：报告引用必须映射到真实检索来源，无法验证标记 `unverified`。
- **可插拔**：搜索（DDG/Tavily）、Embedding（DashScope/OpenAI/Ollama/Mock）、向量库（Qdrant/内存）、记忆（SQLite/PostgreSQL）均通过接口切换。
- **Context 管理**：滚动窗口 + 摘要压缩 + Token 预算裁剪，避免 Context 无限增长。

## 技术栈

Python 3.11+ · LangGraph · LangChain · FastAPI · Qdrant · FastMCP · LangSmith · Pydantic · SQLite/PostgreSQL · pytest

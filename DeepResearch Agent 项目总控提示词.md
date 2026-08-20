# DeepResearch Agent —— AI Agent 深度研究系统

你现在是一名资深 AI Agent Engineer，同时具备 Python 后端、LLM、RAG、LangGraph、MCP、Agent Evaluation 和生产级系统设计经验。

你的任务是：**从零开始帮我开发一个可以写进 AI Agent 开发实习简历、能够经得起技术面试追问的 DeepResearch Agent 项目。**

不要把它实现成简单的“LLM + 搜索 API + RAG 聊天机器人”。

我要的是一个具有真实 Agent Engineering 特征的、可运行、可测试、可评估、可部署的工程项目。

---

# 一、项目目标

项目名称：

**DeepResearch Agent —— 基于 LangGraph 的多阶段自主深度研究智能体**

核心目标：

用户输入一个复杂研究问题后，系统能够自主完成：

1. 理解用户研究目标
2. 自动拆解研究任务
3. 制定 Research Plan
4. 并行执行多个子任务
5. 调用 Web Search / ArXiv / GitHub 等工具
6. 获取和读取网页、论文、代码仓库等信息
7. 对资料进行 RAG 检索
8. 对检索结果进行 Rerank
9. 提取关键 Evidence
10. 对关键事实进行交叉验证
11. 判断信息是否足够
12. 必要时继续搜索
13. 汇总多个 Agent 的研究结果
14. 生成结构化研究报告
15. 为关键结论生成引用
16. 对最终报告进行 Citation Verification
17. 保存研究历史和用户偏好
18. 记录完整 Agent Trace
19. 对 Agent 的执行过程进行 Evaluation

最终输出不是普通聊天答案，而是一份：

**结构化、可引用、可验证、带来源的深度研究报告。**

---

# 二、核心设计原则

必须遵守以下原则：

## 1. Agent First

不要把所有逻辑写死。

需要让 LLM 真正参与：

- Task Planning
- Tool Selection
- Research Strategy
- Evidence Evaluation
- Iterative Search
- Final Synthesis

---

## 2. 不要伪造 Agent

禁止出现：

```text
LLM → 固定调用 search → 固定调用 RAG → LLM
```

这种伪 Agent。

必须具有：

```text
State
↓
Planner
↓
Action
↓
Tool
↓
Observation
↓
Evaluation
↓
Next Action
```

的真实 Agent Loop。

---

## 3. 所有关键决策必须具有 State

使用 LangGraph StateGraph 管理 Agent State。

State 至少包括：

```python
research_question
research_plan
subtasks
current_task
search_queries
documents
evidence
claims
citations
verification_results
research_notes
final_report
messages
tool_calls
iteration_count
token_usage
execution_metadata
```

---

# 三、推荐技术栈

后端：

- Python 3.11+
- FastAPI
- Pydantic
- Uvicorn

Agent：

- LangGraph
- LangChain Core
- LLM Tool Calling

模型：

优先设计成可配置：

- OpenAI
- DeepSeek
- Claude
- Qwen

通过 `.env` 控制，不允许把 API Key 写死。

RAG：

- Qdrant
- Embedding Model
- BM25
- Hybrid Retrieval
- Reranker

数据：

- PostgreSQL
- Redis

工具：

- Web Search
- ArXiv
- GitHub
- Web Reader
- Document Reader

协议：

- MCP

Observability：

- Langfuse

部署：

- Docker
- Docker Compose

测试：

- pytest

---

# 四、系统总体架构

请实现类似以下架构：

```text
                         User
                           │
                           ▼
                    FastAPI Gateway
                           │
                           ▼
                    Research Agent
                           │
                    ┌──────┴──────┐
                    │             │
                    ▼             ▼
                 Planner      Memory
                    │
                    ▼
              Research Plan
                    │
                    ▼
              Task Scheduler
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
      Search      Arxiv     GitHub
       Agent       Agent      Agent
          │         │         │
          └─────────┼─────────┘
                    ▼
              Document Reader
                    │
                    ▼
              RAG Pipeline
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
     Dense Retrieval       BM25
          │                   │
          └─────────┬─────────┘
                    ▼
                  Rerank
                    │
                    ▼
             Evidence Extractor
                    │
                    ▼
             Claim Verification
                    │
               ┌────┴────┐
               │         │
            Enough?      No
               │         │
              Yes        └──→ Continue Research
               │
               ▼
          Report Writer
               │
               ▼
       Citation Verification
               │
               ▼
        Final Research Report
               │
               ▼
          Evaluation
```

请在项目中真正实现，而不是只在 README 中画图。

---

# 五、Agent Graph

使用 LangGraph 构建明确的 StateGraph。

建议至少包含：

```text
START
  ↓
Research Intake
  ↓
Planner
  ↓
Task Decomposition
  ↓
Task Scheduler
  ↓
Research Worker
  ↓
Tool Selection
  ↓
Tool Execution
  ↓
Document Processing
  ↓
Evidence Extraction
  ↓
Evidence Evaluation
  ↓
Research Sufficiency Check
  ├── insufficient → Planner / Research Worker
  └── sufficient
          ↓
      Report Writer
          ↓
   Citation Verification
          ↓
       Evaluator
          ↓
        END
```

Research Sufficiency Check 必须能够决定：

```text
继续研究
```

或者：

```text
研究完成
```

不要简单使用固定循环次数。

---

# 六、Planner Agent

Planner 的职责：

输入：

```text
User Research Question
```

输出结构化：

```json
{
  "goal": "...",
  "subtasks": [
    {
      "id": "task_1",
      "question": "...",
      "priority": "high",
      "required_sources": ["web", "arxiv"],
      "status": "pending"
    }
  ]
}
```

Planner 必须考虑：

- 问题范围
- 时间范围
- 信息来源
- 子问题依赖关系
- 是否需要论文
- 是否需要 GitHub
- 是否需要最新信息

---

# 七、Research Worker

Research Worker 是核心 Agent。

它需要自主决定：

```text
Search
Read
Retrieve
Verify
Search Again
```

而不是固定执行一次。

实现类似：

```text
while not sufficient:

    analyze_current_state()

    decide_next_action()

    call_tool()

    observe_result()

    update_state()

    evaluate_evidence()
```

但是不要使用简单的无限 while。

必须：

- 设置最大 iteration
- 设置 timeout
- 检查重复搜索
- 检查工具错误
- 检查 Token Cost
- 支持 graceful termination

---

# 八、Tool Calling

实现统一 Tool Interface。

至少包括：

```python
search_web(query)
search_arxiv(query)
search_github(query)
read_webpage(url)
retrieve_documents(query)
search_code_repository(query)
```

每个 Tool 必须：

1. 有清晰的 Pydantic 输入 Schema
2. 有结构化输出
3. 有错误处理
4. 有 timeout
5. 记录 Tool Call
6. 记录 latency
7. 记录成功/失败状态

不要让 Agent 直接操作 HTTP 请求。

使用统一 Tool Layer。

---

# 九、MCP

实现 MCP Server。

至少提供：

```text
search
arxiv
github
document
```

等工具。

Agent 可以通过 MCP 获取外部工具。

MCP 与普通 LangChain Tool 的区别需要在代码结构上体现出来。

README 中解释：

- MCP 是什么
- 为什么使用 MCP
- MCP Server 与 Agent 的关系
- MCP Tool Discovery
- MCP Tool Calling

---

# 十、RAG Pipeline

不要实现最简单的：

```text
Embedding → Vector Search → TopK
```

实现：

```text
Document
    ↓
Parsing
    ↓
Cleaning
    ↓
Semantic Chunking
    ↓
Embedding
    ↓
Vector DB
```

查询：

```text
User Query
     │
     ├──────────────→ Dense Retrieval
     │
     └──────────────→ BM25
                       │
                       ▼
                 Hybrid Fusion
                       │
                       ▼
                    Reranker
                       │
                       ▼
                Context Selection
```

需要实现：

- Dense Retrieval
- BM25
- Hybrid Retrieval
- Reranking
- Top-K
- Metadata Filtering

---

# 十一、Citation System

这是项目非常重要的功能。

每个 Evidence 必须记录：

```json
{
  "claim": "...",
  "source": "...",
  "url": "...",
  "title": "...",
  "published_at": "...",
  "relevance": 0.91,
  "confidence": 0.88
}
```

最终报告中的关键 Claim 必须可以映射到 Source。

实现：

```text
Claim
 ↓
Evidence
 ↓
Source
 ↓
Citation
```

禁止生成不存在的引用。

如果找不到可靠来源：

```text
citation_status = "unverified"
```

而不是编造引用。

---

# 十二、Evidence Verification

实现 Evidence Evaluator。

评价：

```text
Relevance
Reliability
Recency
Consistency
Citation Availability
```

可以设计：

```text
Evidence Score =
0.30 × Relevance
+
0.25 × Reliability
+
0.20 × Recency
+
0.15 × Consistency
+
0.10 × Citation Availability
```

具体权重可以调整。

需要在 README 中说明设计依据。

---

# 十三、Memory

实现两种 Memory。

## Short-term Memory

保存：

```text
Current Research State
Messages
Current Plan
Tool Results
Evidence
```

## Long-term Memory

保存：

```text
User Research History
User Preferences
Previous Research Topics
Previous Sources
```

可以使用：

```text
PostgreSQL
+
Redis
```

不要把所有历史消息无限塞进 Context。

必须设计 Context Compression / Summarization。

---

# 十四、Context Engineering

实现：

```text
Raw History
     ↓
Memory Retrieval
     ↓
Relevant Context
     ↓
Context Compression
     ↓
Agent Prompt
```

需要避免：

- Context 爆炸
- 重复文档
- 重复 Tool Result
- 无关历史信息

记录：

```text
input_tokens
context_tokens
output_tokens
total_tokens
```

---

# 十五、Evaluation

这是项目必须完成的模块。

建立 Evaluation Dataset。

例如：

```text
eval/
├── questions.json
├── expected_sources.json
└── expected_claims.json
```

至少准备 20 个研究问题。

评估：

### Retrieval

```text
Recall@K
MRR
NDCG
```

### Agent

```text
Task Completion Rate
Tool Success Rate
Planning Accuracy
Iteration Count
```

### Answer

```text
Answer Correctness
Faithfulness
Citation Accuracy
Citation Coverage
```

### Engineering

```text
Latency
Token Usage
Cost
Failure Rate
```

---

# 十六、Baseline

必须实现至少一个 Baseline。

例如：

```text
Baseline:
User Question
      ↓
Single LLM
      ↓
Answer
```

以及：

```text
Baseline 2:
Question
 ↓
Search
 ↓
LLM
```

最终：

```text
Baseline
VS
DeepResearch Agent
```

生成 Evaluation Table。

例如：

```text
Metric                 Baseline    DeepResearch
------------------------------------------------
Task Completion          72%          91%
Citation Accuracy        68%          94%
Retrieval Recall@5       61%          86%
Tool Success              -           95%
Average Latency          8.2s         18.7s
Average Cost             0.03$        0.11$
```

这些数字必须来自真实实验。

**禁止伪造 Benchmark 数据。**

---

# 十七、Observability

使用 Langfuse。

记录：

```text
Trace
 ├── Planner
 ├── Research Worker
 ├── Tool Call
 ├── Retrieval
 ├── Rerank
 ├── Verification
 └── Report Generation
```

记录：

- latency
- tokens
- model
- tool
- error
- cost

最终能够查看一次完整 Research Run。

---

# 十八、API

使用 FastAPI。

至少提供：

```text
POST /api/research
GET  /api/research/{id}
GET  /api/research/{id}/trace
GET  /api/research/{id}/sources
GET  /api/research/{id}/evaluation
```

Research API 支持：

```json
{
  "question": "...",
  "depth": "deep",
  "max_iterations": 10
}
```

返回：

```json
{
  "research_id": "...",
  "status": "completed",
  "report": "...",
  "sources": [],
  "metrics": {}
}
```

---

# 十九、前端

如果时间允许，实现一个简单 Web UI。

技术：

- Vue 3
- TypeScript
- Vite

页面：

```text
Research Page

┌─────────────────────────────────────┐
│ Research Question                   │
│                                     │
│ [.................................] │
│                                     │
│              [Start Research]       │
└─────────────────────────────────────┘

Research Progress

✓ Planning
✓ Searching
✓ Reading Sources
✓ Retrieving
✓ Verifying
● Writing Report

Sources

1. ...
2. ...
3. ...

Final Report
---------------------------------------
...
---------------------------------------
```

重点展示：

- Agent Progress
- Research Steps
- Sources
- Citations
- Final Report
- Token Usage
- Latency

不要花大量时间做视觉设计。

---

# 二十、项目目录

建议：

```text
deep-research-agent/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── graph/
│   │   ├── tools/
│   │   ├── rag/
│   │   ├── memory/
│   │   ├── evaluation/
│   │   ├── models/
│   │   ├── services/
│   │   ├── config/
│   │   └── main.py
│   │
│   └── tests/
│
├── mcp_servers/
│
├── frontend/
│
├── eval/
│
├── scripts/
│
├── docs/
│
├── docker/
│
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

如果你认为有更合理的目录结构，可以调整，但必须保持模块职责清晰。

---

# 二十一、工程要求

必须：

- 类型提示
- Pydantic Schema
- Async IO
- Logging
- Exception Handling
- Retry
- Timeout
- Config Management
- Unit Test
- Integration Test
- Docker
- `.env`
- `.env.example`

禁止：

- API Key 写死
- 超长单文件
- 所有逻辑写在 main.py
- 大量全局变量
- 裸 except
- 无意义的抽象
- 为了炫技加入不必要的框架

---

# 二十二、开发方式

**非常重要：不要一次生成整个项目。**

严格按照以下阶段执行。

## Phase 0 —— 项目设计

先不要写代码。

先输出：

1. 完整系统架构
2. Agent Graph
3. State Schema
4. Tool Architecture
5. RAG Architecture
6. Memory Architecture
7. Evaluation Architecture
8. Database Schema
9. API Design
10. 项目目录

然后等待我的确认。

---

## Phase 1 —— Backend Skeleton

实现：

- FastAPI
- Config
- Logging
- Pydantic
- Database
- Health Check

确保：

```text
GET /health
```

可以正常运行。

---

## Phase 2 —— Agent Core

实现：

- LangGraph
- State
- Planner
- Research Worker
- Agent Loop

先使用 Mock Tools。

确保 Graph 可以运行。

---

## Phase 3 —— Tools

逐步实现：

- Web Search
- Arxiv
- GitHub
- Web Reader

每个 Tool 单独测试。

---

## Phase 4 —— RAG

实现：

- Document Parsing
- Chunking
- Embedding
- Qdrant
- BM25
- Hybrid Retrieval
- Reranker

---

## Phase 5 —— Evidence & Citation

实现：

- Evidence Extraction
- Claim Extraction
- Citation Mapping
- Citation Verification

---

## Phase 6 —— Memory

实现：

- Short-term Memory
- Long-term Memory
- Memory Retrieval
- Context Compression

---

## Phase 7 —— MCP

实现 MCP Server。

让 Agent 可以调用 MCP Tools。

---

## Phase 8 —— Evaluation

实现：

- Dataset
- Baseline
- Metrics
- Evaluation Pipeline
- Benchmark Report

---

## Phase 9 —— Observability

接入：

- Langfuse
- Trace
- Token
- Latency
- Cost

---

## Phase 10 —— Frontend

最后再做 Vue UI。

---

## Phase 11 —— Docker

最终实现：

```text
docker compose up
```

能够启动：

```text
Backend
Frontend
PostgreSQL
Redis
Qdrant
Langfuse
MCP Server
```

---

# 二十三、代码质量要求

每完成一个 Phase：

1. 运行测试
2. 检查类型
3. 检查 lint
4. 检查异常处理
5. 检查日志
6. 检查 API
7. 更新 README
8. 告诉我修改了哪些文件
9. 告诉我如何运行
10. 告诉我当前还有什么问题

如果某个依赖存在版本兼容问题：

不要随便修改整个项目。

先分析：

```text
Package
Version
Python Version
Compatibility
```

然后选择稳定方案。

---

# 二十四、重要：不要为了“看起来高级”堆功能

优先级：

```text
Agent Loop
    >
Tool Calling
    >
Research Planning
    >
RAG
    >
Evidence Verification
    >
Evaluation
    >
Memory
    >
MCP
    >
Observability
    >
Frontend
```

如果时间有限，宁愿把前面的功能做扎实，也不要做一个华而不实的 UI。

---

# 二十五、最终验收标准

项目完成后必须满足：

## Agent

- [ ] 能自主拆解复杂任务
- [ ] 能自主选择 Tool
- [ ] 能循环研究
- [ ] 能判断是否需要继续搜索
- [ ] 能处理 Tool Error
- [ ] 能结束 Agent Loop

## RAG

- [ ] Dense Retrieval
- [ ] BM25
- [ ] Hybrid Search
- [ ] Reranker

## Research

- [ ] Web
- [ ] Arxiv
- [ ] GitHub
- [ ] Evidence
- [ ] Citation
- [ ] Verification

## Memory

- [ ] Short-term
- [ ] Long-term
- [ ] Context Compression

## MCP

- [ ] MCP Server
- [ ] MCP Tool
- [ ] Agent MCP Calling

## Evaluation

- [ ] Dataset
- [ ] Baseline
- [ ] Retrieval Metrics
- [ ] Agent Metrics
- [ ] Answer Metrics
- [ ] Cost
- [ ] Latency

## Engineering

- [ ] FastAPI
- [ ] PostgreSQL
- [ ] Redis
- [ ] Docker
- [ ] Logging
- [ ] Testing
- [ ] Langfuse

---

# 二十六、最终输出

项目完成后，请帮助我生成：

1. 系统架构图
2. Agent Workflow 图
3. README
4. API 文档
5. Evaluation Report
6. Benchmark Table
7. Demo 示例
8. 项目运行说明
9. 技术难点说明
10. 简历项目描述

其中简历项目描述必须突出：

```text
Agent Architecture
Tool Calling
RAG
MCP
Memory
Evaluation
Observability
Docker
```

不要写成简单的“调用大模型实现智能问答”。

---

# 二十七、你的工作方式

从现在开始：

**不要直接开始大量生成代码。**

首先执行：

### Phase 0：Architecture Design

只输出：

1. 系统总体架构
2. LangGraph Agent Graph
3. State Schema
4. Tool Architecture
5. RAG Architecture
6. Memory Architecture
7. Evaluation Architecture
8. Database Schema
9. API Design
10. Project Directory

然后暂停，等待我确认。

之后严格按照 Phase 1 → Phase 11 执行。

每一个阶段都必须：

**先解释设计 → 再修改代码 → 再运行测试 → 再汇报结果。**

最终目标不是生成一个“能聊天的 Demo”，而是完成一个能够作为 **AI Agent Developer 实习核心项目**、可以进行技术面试和现场演示的完整 Agent Engineering 项目。
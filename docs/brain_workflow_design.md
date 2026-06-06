# 阶段 8 Brain 中控层与 RAG Workflow 配置化设计

## 目标

阶段 8 的目标是把阶段 7 已经稳定的 RAG 和 Agent 能力收拢到一个轻量 Brain 中控层，并用配置显式描述 RAG 问答流程。

本阶段不是照搬 Quivr，也不引入复杂 LangGraph workflow。第一版 Brain 采用普通 Python service：它复用现有 keyword、vector、hybrid、prompt、chat model、citation、qa_logs 和 Agent 工具链路，把原本藏在 `CitationAnswerService` 内部的流程拆成可配置、可测试、可评测的 workflow steps。

核心链路：

```text
用户问题
-> BrainService
-> RetrievalConfig / WorkflowConfig
-> filter_history
-> rewrite_query
-> retrieve
-> optional_rerank
-> generate_answer
-> CitationAnswerResult
-> /chat 与 Agent answer_with_citations 复用
```

## 参照 Quivr 的取舍

Quivr 的核心启发：

| Quivr 概念 | 本项目阶段 8 对应 | 取舍 |
|------------|------------------|------|
| `Brain` | `app/services/brain/BrainService` | 保留“中控层”概念，但不引入 Quivr 依赖 |
| `RetrievalConfig` | 本项目 `RetrievalConfig` | 保留检索、历史、重排、prompt、模型配置 |
| `WorkflowConfig` | 本项目 `WorkflowConfig` | 保留步骤顺序，不使用 LangGraph 图执行 |
| `filter_history -> rewrite -> retrieve -> generate_rag` | `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer` | 增加显式重排占位，命名贴合本项目 |
| reranker config | `rerank_top_n` | 第一版只做可解释的候选截断，不接外部 reranker |
| LLMEndpoint | `ChatModelProvider` | 继续复用阶段 3 已有模型适配层 |

为什么不照搬 Quivr：

- 本项目当前是 FastAPI + SQLite + 原生 service 分层，直接引入 LangGraph 会让阶段 8 过早复杂化。
- 本项目已有 `CitationAnswerService`、`HybridSearchService`、`ChatModelProvider` 和评测脚本，Brain 应该组合这些能力，而不是替换它们。
- 阶段 8 的重点是“配置化和可复用”，不是追求复杂 Agent planning。

## Brain 层职责

`BrainService` 是阶段 8 的中控层。

它负责：

- 接收用户问题和 `RetrievalConfig`。
- 按 `WorkflowConfig` 执行 RAG workflow。
- 调用现有 keyword、vector、hybrid 检索服务。
- 调用 `build_rag_prompt()` 构造带编号来源的上下文。
- 调用 `ChatModelProvider` 生成回答。
- 提取 citations 并保留 sources。
- 继续写入 `qa_logs`。
- 返回兼容 `CitationAnswerResult` 的问答结果。
- 额外记录 workflow step 执行摘要，供配置化评测使用。

它不负责：

- 不直接写 SQL。
- 绕过 `documents/chunks` 或 `sources`。
- 不自动执行 source reindex。
- 不联网爬取新资料。
- 替代 API schema。
- 替代 Agent 工具权限约束。

## 配置模型

阶段 8 新增 Brain 配置模型。

`RetrievalConfig` 至少包含：

```text
retrieval_mode: auto | keyword | vector | hybrid
top_k
min_score
max_history
rerank_top_n
prompt_profile
model_provider
workflow_config
```

字段含义：

- `retrieval_mode`：选择检索模式。
- `top_k`：最终送入回答链路的候选数量。
- `min_score`：低于该分数的片段会被过滤。
- `max_history`：保留多少轮历史，第一版暂不启用复杂历史，但保留字段。
- `rerank_top_n`：重排后保留多少条结果，第一版可用截断实现。
- `prompt_profile`：选择 prompt 策略，第一版默认 `citation_default`。
- `model_provider`：记录模型供应商配置名，第一版继续复用现有 provider。
- `workflow_config`：描述 workflow step 顺序。

`WorkflowConfig` 默认步骤：

```text
filter_history
rewrite_query
retrieve
optional_rerank
generate_answer
```

允许的步骤必须白名单校验，避免配置里出现未知步骤导致运行时行为不可控。

## Workflow Steps

### filter_history

作用：处理对话历史。

第一版行为：no-op。也就是不改变问题，只返回空历史摘要和 step 记录。

为什么保留：Quivr 的 RAG workflow 会先过滤历史。后续做多轮问答时，本步骤可以根据 `max_history` 截取历史。

### rewrite_query

作用：把依赖上下文的问题改写成可独立检索的问题。

第一版行为：no-op。直接把原问题作为 `rewritten_query`。

为什么保留：后续接真实 LLM 后，可以把“继续说它的施工质量”改写成“堆石混凝土施工质量如何控制”。

### retrieve

作用：按 `retrieval_mode` 召回资料片段。

当前映射：

```text
keyword -> KeywordSearchService
vector  -> VectorSearchService
hybrid  -> HybridSearchService
auto    -> 保持 CitationAnswerService 旧语义，先 vector，有结果则用 vector，否则 fallback 到 keyword
```

### optional_rerank

作用：对候选结果做重排或截断。

第一版行为：如果 `rerank_top_n > 0`，保留前 `rerank_top_n` 条；否则不改变候选顺序。

为什么这样设计：先保留 rerank 配置和评测字段，后续可以接真实 reranker。

### generate_answer

作用：生成引用式回答。

步骤：

```text
retrieved results
-> build_rag_prompt()
-> ChatModelProvider.generate()
-> extract_citations()
-> CitationAnswerResult
-> qa_logs
```

资料不足或 prompt 构造失败时，仍复用现有拒答文本：

```text
当前资料库中没有找到足够可靠的依据。
```

## Chat 与 Agent 复用

阶段 8 的关键改造是让 `/chat` 和 Agent 的 `answer_with_citations` 复用同一条 Brain workflow。

```text
POST /chat
-> CitationAnswerService.answer()
-> BrainService.answer()
-> CitationAnswerResult
-> ChatResponse
```

```text
POST /agent/query
-> AgentService
-> AgentToolbox.answer_with_citations()
-> CitationAnswerService.answer()
-> BrainService.answer()
-> AgentToolResult
```

这样做的好处：

- `CitationAnswerService` 继续作为外部兼容入口。
- `/chat` 的 API 不需要改变。
- Agent 不需要知道 workflow 内部细节。
- 后续调整检索、重写、重排、prompt 时，chat 和 Agent 可以同时受益。

## 配置化评测

阶段 8 新增 Brain workflow 配置化评测。

建议文件：

```text
scripts/evaluate_brain_workflow.py
data/evaluation/brain_workflow_results.csv
```

至少比较三种配置：

| config_name | retrieval_mode | rerank_top_n | 用途 |
|-------------|----------------|--------------|------|
| `default_hybrid` | `hybrid` | `5` | 阶段 6 质量最好的默认路径 |
| `keyword_baseline` | `keyword` | `5` | 保留关键词 baseline |
| `vector_only` | `vector` | `5` | 保留向量 baseline |

评测字段应包含：

```text
query_id
config_name
question
passed
retrieval_mode
used_retrieval_mode
workflow_steps
source_count
citations
citations_valid
expected_source_hit
refused
refusal_matched
answer
error
```

完成标准不是让所有配置都同分，而是能清楚比较不同配置的质量和风险。

## 完成标准

- `docs/brain_workflow_design.md` 存在并覆盖 Brain、RetrievalConfig、WorkflowConfig、workflow steps、Quivr 取舍、chat/agent 复用和配置化评测。
- `app/services/brain/` 新增配置模型和 Brain workflow。
- `CitationAnswerService` 通过 Brain workflow 执行问答。
- Agent 的 `answer_with_citations` 通过同一问答入口复用 Brain workflow。
- 旧 search/vector/hybrid/chat/agent/sources/frontend API 和测试不被破坏。
- 新增配置化评测脚本和结果文件。
- 阶段 8 收尾文档和 Obsidian 知识库完成。

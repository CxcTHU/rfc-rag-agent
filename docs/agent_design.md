# 阶段 7 Agent 化设计

## 目标

阶段 7 的目标是把阶段 6 已经稳定的 RAG 能力包装成受控、可测试、可追踪的 Agent 工具调用链路。

本阶段不是让模型自由规划所有动作，也不是引入复杂 LangGraph workflow。第一版 Agent 采用轻量规则式编排：根据用户问题选择已有工具，调用已有 service，返回答案、来源、引用、工具调用记录和可审计摘要。

核心链路：

```text
- 用户问题
-> Agent API
-> Agent 编排服务
-> Agent 工具
-> keyword / hybrid search / citation chat / sources repository
-> 结构化响应
-> 评测脚本回归
```

## 工具边界

阶段 7 最小工具集：

| 工具名 | 类型 | 复用能力 | 用途 |
|--------|------|----------|------|
| `search_knowledge` | 只读 | `KeywordSearchService` | 执行关键词检索，保留阶段 1 baseline 能力 |
| `hybrid_search_knowledge` | 只读 | `HybridSearchService` | 执行阶段 6 质量最好的混合检索 |
| `answer_with_citations` | 只读加日志 | `CitationAnswerService` | 生成带 citations 和 sources 的引用式回答 |
| `list_sources` | 只读 | `SourceRepository.list_sources()` | 查询来源登记库 |
| `get_source_detail` | 只读 | `SourceRepository.get_by_source_id()` | 查询单条来源详情 |

工具不得绕过以下链路：

- 不直接拼接 SQL 查询 chunks。
- 不直接读取 `data/app.sqlite` 文件。
- 不直接生成没有 citations 的回答。
- 不跳过 `sources`、`documents/chunks`、`hybrid search`、`chat citation` 和拒答机制。

## 权限约束

阶段 7 优先只读工具。

允许：

- 查询已有来源。
- 查询已有 documents/chunks 的检索结果。
- 调用引用式问答。
- 返回工具调用记录和来源信息。

不自动允许：

- `POST /sources/{source_id}/reindex`。
- 批量同步来源。
- 写入或删除资料。
- 联网爬取新资料。
- 修改 `sources`、`documents`、`chunks`、`chunk_embeddings`。

如果后续要把 reindex 做成 Agent 工具，必须新增显式请求字段，例如 `allow_write_actions=true`，并补充独立测试。本阶段默认不做。

## 调用流程

```text
AgentQueryRequest
-> validate question/top_k/max_tool_calls
-> intent routing
-> execute selected tool
-> collect tool_calls
-> normalize answer/sources/citations/refused
-> return AgentQueryResponse
```

第一版意图路由规则：

| 用户意图 | 判定线索 | 工具 |
|----------|----------|------|
| 引用式问答 | 问句中包含 what/how/why/什么/如何/为什么/影响/区别等 | `answer_with_citations` |
| 检索资料 | 包含 search/find/检索/搜索/查找/相关资料 | `hybrid_search_knowledge` |
| 来源列表 | 包含 sources/list sources/来源列表/资料来源 | `list_sources` |
| 来源详情 | 包含 source_id 或 “来源详情” | `get_source_detail` |

默认策略：如果意图不明确，优先使用 `answer_with_citations`。这样回答仍然经过引用、拒答和日志链路。

## 响应结构

`POST /agent/query` 应返回：

```text
question
answer
tool_calls
sources
citations
refused
refusal_reason
reasoning_summary
```

`tool_calls` 至少包含：

```text
tool_name
input_summary
output_summary
succeeded
error
```

`reasoning_summary` 是面向用户和评测的可审计摘要，用来说明本次选择了哪个工具以及为什么。它不是模型隐藏推理链，不应暴露内部敏感推理。

## 失败处理

- 问题为空：返回 400。
- `top_k <= 0`：返回 400。
- 工具找不到来源：返回正常 Agent 响应，`refused=true`，并在 tool call 中记录失败。
- 检索不到资料：复用 `CitationAnswerService` 的拒答文本。
- 工具异常：捕获为工具调用失败，返回可理解错误，不让整个服务静默失败。

## 评测方式

阶段 7 新增 Agent 评测：

```text
data/evaluation/agent_queries.csv
scripts/evaluate_agent.py
data/evaluation/agent_results.csv
```

评测字段应覆盖：

- `query_id`
- `question`
- `passed`
- `expected_tool`
- `actual_tools`
- `expected_refused`
- `refused`
- `citations_valid`
- `expected_source_hit`
- `source_count`
- `tool_call_count`

评测目标：

- Agent 问答类问题不降低 chat 评测的引用和拒答质量。
- Agent 搜索类问题能调用 `hybrid_search_knowledge`。
- Agent 来源类问题能调用 `list_sources` 或 `get_source_detail`。
- 工具调用记录可审计。

## 完成标准

- Agent 设计文档存在并覆盖工具边界、权限约束、调用流程、失败处理和评测方式。
- 最小工具集实现并复用现有 service。
- `POST /agent/query` 可返回结构化 Agent 响应。
- Agent 评测脚本可运行并输出 CSV。
- 旧 search/vector/hybrid/chat/sources/frontend/evaluation 测试不被破坏。
- 阶段 7 收尾文档和 Obsidian 知识库完成。

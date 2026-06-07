# 阶段 14 设计：真实 Embedding 与回答覆盖校准

## 目标

阶段 14 的目标是在阶段 13 Decompose 与证据合并已经稳定的基础上，校准两件事：

1. 真实 embedding 与 deterministic baseline 在检索、用户问题和 Decompose 场景下的差异。
2. 真实模型或人工审阅下的 Answer Coverage、Faithfulness 和 Citation Quality。

本阶段不是替换默认 RAG 链路，也不是把真实 API 调用变成自动回归前提。默认开发和 CI 仍以 deterministic provider 为稳定 baseline；真实模型配置只在本地显式配置完整时运行，缺失、限流、余额不足或网络失败时必须 graceful skip 或记录 error，不伪造成功结果。

核心链路：

```text
sources/documents/chunks/chunk_embeddings
-> deterministic baseline
-> provider/model/dimension 配置复核
-> 真实 embedding 索引重建或读取已生成结果
-> vector / hybrid / user question / decompose 指标对比
-> chat / brain / agent 回答覆盖校准
-> Decompose provenance / rerank explanation 可读化
-> 质量结论和下一阶段依据
```

## 阶段输入

阶段 14 复用已有资料库和评测产物：

```text
data/evaluation/keyword_queries.csv
data/evaluation/user_questions.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/user_question_results.csv
data/evaluation/stage13_decompose_results.csv
data/evaluation/stage12_quality_review_results.csv
docs/model_provider_evaluation.md
docs/stage12_quality_review.md
docs/stage13_decompose_plan.md
```

阶段 14 不新增文献来源，不新增爬虫链路，不保存受限全文，不保存 API key。

## 真实 Embedding 对比

真实 embedding 对比要回答：同一批问题在 deterministic embedding 与真实 embedding provider 下，vector、hybrid、user question 和 Decompose 评测结果有什么差异。

输出表：

```text
data/evaluation/stage14_embedding_comparison.csv
```

建议字段：

```text
config_name
suite
status
passed
total
failed
pass_rate
embedding_provider
embedding_model_name
embedding_dimension
chat_provider
chat_model_name
source_file
failed_queries
skipped_reason
notes
```

其中：

- `deterministic_baseline` 必须存在，作为稳定回归口径。
- `real_config` 可存在为 completed、skipped 或 error。
- 真实 embedding 配置必须按 provider/model/dimension 重建索引后再评测。
- 真实 API 不可用时，写 skipped 或 error，不伪造 passed/total。
- vector-only 失败边界必须保留，不用静默 fallback 到 hybrid 掩盖。

## Answer Coverage 校准

Answer Coverage 校准要回答：检索证据和回答文本是否覆盖用户问题中的核心技术点。

输出表：

```text
data/evaluation/stage14_answer_coverage_review.csv
```

建议字段：

```text
review_id
query_id
config_name
question
expected_answer_points
answer
evidence_titles
evidence_source_ids
faithfulness
answer_coverage
citation_quality
risk_level
review_method
skipped_reason
recommendation
notes
```

Rubric 继续复用阶段 12：

| 维度 | pass | review | fail |
|---|---|---|---|
| Faithfulness | 回答没有引入来源外事实 | 看起来可信但需要人工或真实模型复核 | 出现资料外断言或与来源冲突 |
| Answer Coverage | 覆盖 `expected_answer_points` 的核心技术点 | 命中来源但回答文本未充分展开 | 缺少关键技术点或证据明显不足 |
| Citation Quality | 引用能映射到支持关键说法的来源 | 支持关系偏弱或来源主题不完全匹配 | 引用缺失、无法追溯或不支持回答 |

默认情况下，阶段 14 可以先生成人工审阅友好的校准表，并用 deterministic answer 做稳定占位；如果真实 chat provider 配置完整，可以额外生成真实模型回答审阅行。真实模型缺失时必须 graceful skip。

## Decompose Provenance 可读化

阶段 13 已经记录：

```text
sub_queries
deduplicated_count
provenance_present
rerank_explanations
```

阶段 14 要把这些字段组织得更适合审阅，至少能看出：

- 原始问题拆成了哪些 sub query。
- 每个 top evidence 由哪些 sub query 召回。
- 去重前后候选数量变化。
- rerank explanation 中的 topic_terms、both_match、source_type、raw_score、final_score。
- unsupported 问题没有被误拆成可回答问题。

这项工作优先落在评测 CSV 或审阅表中。若前端需要展示，只做最小只读展示，不改变旧 API schema，不做前端重构。

## Graceful Skip 规则

真实模型相关脚本必须遵守：

- 缺少 `CHAT_MODEL_PROVIDER`、`CHAT_MODEL_NAME`、`CHAT_MODEL_API_KEY`、`CHAT_MODEL_BASE_URL` 时，真实 chat 配置 skipped。
- 缺少 `EMBEDDING_PROVIDER`、`EMBEDDING_MODEL_NAME`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_DIMENSION` 时，真实 embedding 配置 skipped。
- HTTP 429、网络错误、超时、余额不足、维度不匹配等外部问题记录为 error 或 skipped，不写成 pass。
- 自动测试使用 deterministic 或 mock，不访问真实网络。
- CSV、文档、测试和 Obsidian 中不能保存 API key、Bearer token、供应商原始敏感响应或受限全文。

## API 与阶段边界

阶段 14 不改变以下入口的旧请求兼容性：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
```

阶段 14 不做：

- 不做写入型 Agent 工具。
- 不做复杂 LangGraph workflow。
- 不做登录系统。
- 不做部署优化。
- 不做 HyDE 默认链路或自动回归。
- 不做前端重构。

阶段 14 要做：

- 固化真实 embedding 对比设计。
- 生成 embedding comparison 结果表。
- 生成 Answer Coverage 校准结果表。
- 让 Decompose provenance / rerank explanation 更易审阅。
- 复跑 deterministic baseline 和阶段 14 相关测试。
- 完成普通文档、Obsidian、本地测试、提交和 `phase-14-complete` tag。

## 完成标准

- `docs/stage14_real_quality_calibration.md` 存在并覆盖目标、输入、指标、skip 规则、API 边界和完成标准。
- `data/evaluation/stage14_embedding_comparison.csv` 存在，包含 deterministic baseline 和 real_config completed/skipped/error 行。
- `data/evaluation/stage14_answer_coverage_review.csv` 存在，包含 Faithfulness、Answer Coverage、Citation Quality、risk_level 和 recommendation。
- Decompose provenance 与 rerank explanation 有更易审阅的结构化输出。
- 旧 search/vector/hybrid/chat/agent API 不被破坏。
- 阶段 14 测试、相关回归和最终全量测试通过。
- README、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD 和 Obsidian 本地知识库完成阶段收尾。

## 面试表达

阶段 14 我把质量提升从“检索有没有命中”推进到“真实模型配置下证据和回答是否更可靠”。做法是先保留 deterministic baseline，保证本地回归稳定；再把真实 embedding 按 provider、model、dimension 独立记录和对比，避免不同模型索引混用。真实 API 不可用时不伪造结果，而是明确 skipped 或 error。

回答质量上，我把 Answer Coverage、Faithfulness 和 Citation Quality 拆开审阅：来源命中只能说明找到了材料，不代表回答覆盖了用户要点。阶段 14 的校准表会把问题、期望要点、证据、回答、风险和建议放在一起，方便后续决定是换 embedding、改 rerank、补资料，还是调整回答生成策略。

# 阶段 15 设计：真实配置复跑与质量审阅报告

## 目标

阶段 15 的目标是在阶段 14 已经建立质量校准表之后，补齐三个可验证闭环：

1. 真实配置复跑：显式检查本地真实 embedding / chat provider 是否可用，并把 vector、hybrid、user_questions、decompose、chat、agent、brain_workflow 的真实配置结果输出到 `data/evaluation/stage14_real/`。
2. 回答质量复核：对 `data/evaluation/stage14_answer_coverage_review.csv` 中 `medium` / `review` 样例进行人工规则或真实模型辅助复核，明确 Faithfulness、Answer Coverage、Citation Quality 和风险等级。
3. 只读质量报告：把阶段 14/15 的质量表汇总成可读报告入口，说明哪些结果已验证、哪些是 skipped/error、哪些仍是发布前风险。

本阶段不是替换默认 RAG 链路，也不是把真实 API 调用变成自动回归前提。默认开发和 CI 仍以 deterministic baseline 为稳定口径；真实模型配置只在本地显式配置完整时运行，缺失、限流、余额不足或网络失败时必须 graceful skip 或记录 error，不伪造成功结果。

核心链路：

```text
stage14 quality tables
-> real provider readiness check
-> real_config rerun or graceful skip
-> stage15 answer coverage review
-> stage15 quality summary
-> read-only quality report
-> docs/progress / README / Obsidian quality conclusion
```

## 阶段输入

阶段 15 复用已有资料库和评测产物：

```text
data/evaluation/stage14_embedding_comparison.csv
data/evaluation/stage14_answer_coverage_review.csv
data/evaluation/stage14_decompose_provenance_review.csv
data/evaluation/user_questions.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/user_question_results.csv
data/evaluation/stage13_decompose_results.csv
docs/stage14_real_quality_calibration.md
docs/stage12_quality_review.md
```

阶段 15 不新增文献来源，不新增爬虫链路，不保存受限全文，不保存 API key。

## 真实配置复跑

真实配置复跑要回答：当前本地 `.env` 是否具备真实 embedding / chat provider 配置；如果具备，真实配置在现有评测集上的结果是什么；如果不具备，缺失原因是什么。

输出目录：

```text
data/evaluation/stage14_real/
```

建议输出文件：

```text
data/evaluation/stage14_real/real_config_status.csv
data/evaluation/stage14_real/vector_results.csv
data/evaluation/stage14_real/hybrid_results.csv
data/evaluation/stage14_real/user_question_results.csv
data/evaluation/stage14_real/decompose_results.csv
data/evaluation/stage14_real/chat_results.csv
data/evaluation/stage14_real/agent_results.csv
data/evaluation/stage14_real/brain_workflow_results.csv
```

`real_config_status.csv` 建议字段：

```text
suite
status
output_file
embedding_provider
embedding_model_name
embedding_dimension
chat_provider
chat_model_name
skipped_reason
error_summary
notes
```

其中：

- `completed` 表示真实配置结果文件已成功生成。
- `skipped` 表示真实配置缺失或用户未显式要求真实调用。
- `error` 表示真实配置存在但外部调用失败，例如 HTTP 429、超时、余额不足、维度不匹配。
- `missing_results` 表示比较脚本期待结果文件，但文件不存在。

真实配置复跑必须继续保留 deterministic baseline。`data/evaluation/stage14_embedding_comparison.csv` 应能同时展示 deterministic baseline 与 real_config completed/skipped/error 状态，不允许用静默 fallback 把 real_config 伪装成 deterministic 结果。

## Answer Coverage 复核

阶段 15 对阶段 14 的回答覆盖校准表进行复核，重点处理：

```text
risk_level = medium
answer_coverage = review
config_name = default_hybrid 或 real_config
```

输出表：

```text
data/evaluation/stage15_answer_coverage_review.csv
```

建议字段：

```text
review_id
source_review_id
query_id
config_name
question
expected_answer_points
answer_summary
evidence_titles
faithfulness
answer_coverage
citation_quality
risk_level
review_method
review_note
next_action
skipped_reason
```

复核规则继续复用阶段 12/14 的 rubric：

| 维度 | pass | review | fail |
|---|---|---|---|
| Faithfulness | 回答没有引入来源外事实 | 看起来可信但仍需人工确认 | 出现资料外断言或与来源冲突 |
| Answer Coverage | 覆盖 `expected_answer_points` 的核心技术点 | 命中来源但回答文本未充分展开 | 缺少关键技术点或证据明显不足 |
| Citation Quality | 引用能映射到支持关键说法的来源 | 支持关系偏弱或来源主题不完全匹配 | 引用缺失、无法追溯或不支持回答 |

`review_method` 可取：

```text
manual_rule
real_model_summary
skipped_no_real_answer
```

默认自动测试只使用 deterministic 或 mock 数据，不访问真实网络。真实模型回答如果进入复核表，只保存脱敏后的 `answer_summary`、指标和审阅备注，不保存供应商原始响应。

## 质量汇总

阶段 15 需要把多张质量表汇总成一个面向发布前判断的结果：

```text
data/evaluation/stage15_quality_summary.csv
```

建议字段：

```text
section
metric
status
value
baseline_value
risk_level
evidence_file
recommendation
```

至少覆盖：

- deterministic baseline 指标。
- real_config completed/skipped/error 状态。
- Answer Coverage 复核结果分布。
- Decompose provenance 可读化风险。
- 仍需下一阶段处理的问题。

质量汇总的目标不是制造一个“全部通过”的结论，而是把当前质量状态讲清楚：哪些已被自动回归证明，哪些被真实配置或人工复核验证，哪些仍然只是 review 或 skipped。

## 只读报告入口

阶段 15 可以实现只读报告页或导出报告入口。推荐优先级：

```text
1. 静态只读报告页：复用 FastAPI 前端静态资源，展示质量汇总、复核表和关键风险。
2. 导出 Markdown/HTML 报告：由脚本生成，便于离线审阅。
```

报告入口必须遵守：

- 只读展示，不触发真实 API 调用。
- 不改变核心 RAG API。
- 不重构已有前端工作台。
- 不显示 API key、Bearer token、供应商原始敏感响应或受限全文。
- 如果展示来源，只展示标题、source_id、短摘要和指标，不展示完整受限论文正文。

必须保持兼容的入口：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
```

## Graceful Skip 规则

真实模型相关脚本必须遵守：

- 缺少 `CHAT_MODEL_PROVIDER`、`CHAT_MODEL_NAME`、`CHAT_MODEL_API_KEY`、`CHAT_MODEL_BASE_URL` 时，真实 chat 配置 skipped。
- 缺少 `EMBEDDING_PROVIDER`、`EMBEDDING_MODEL_NAME`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_DIMENSION` 时，真实 embedding 配置 skipped。
- HTTP 429、网络错误、超时、余额不足、维度不匹配等外部问题记录为 error 或 skipped，不写成 pass。
- 自动测试使用 deterministic 或 mock，不访问真实网络。
- CSV、文档、测试、报告页和 Obsidian 中不能保存 API key、Bearer token、供应商原始敏感响应或受限全文。

## 阶段边界

阶段 15 不做：

- 不做写入型 Agent 工具。
- 不做复杂 LangGraph workflow。
- 不做登录系统。
- 不做部署优化。
- 不做 HyDE 默认链路或自动回归。
- 不做核心前端工作台重构。

阶段 15 要做：

- 固化真实配置复跑设计。
- 生成 `stage14_real` 真实配置状态或结果。
- 生成 Answer Coverage 复核结果表。
- 生成阶段 15 质量汇总表。
- 建立只读报告页或导出报告入口。
- 复跑 deterministic baseline 和阶段 15 相关测试。
- 完成普通文档、Obsidian、本地测试、提交和 `phase-15-complete` tag。

## 完成标准

- `docs/stage15_real_review_report.md` 存在并覆盖目标、输入、指标、skip 规则、复核表、质量汇总、报告边界和完成标准。
- `data/evaluation/stage14_real/` 存在，并包含真实配置 completed/skipped/error 状态文件。
- deterministic baseline 与 real_config 状态可清楚对比，不伪造真实配置成功。
- `data/evaluation/stage15_answer_coverage_review.csv` 存在，包含 Faithfulness、Answer Coverage、Citation Quality、risk_level、review_method 和 next_action。
- `data/evaluation/stage15_quality_summary.csv` 存在，说明已验证项、skipped/error 项和后续风险。
- 只读报告页或导出报告入口存在，并且不破坏现有 RAG API。
- 旧 search/vector/hybrid/chat/agent API 不被破坏。
- 阶段 15 测试、相关回归和最终全量测试通过。
- README、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD 判断和 Obsidian 本地知识库完成阶段收尾。

## 面试表达

阶段 15 我没有把真实模型调用混进默认自动回归，而是把真实配置当作发布前质量校准。系统先检查 provider、model、dimension 和 API 配置是否完整；能跑就把 vector、hybrid、用户问题、Decompose、chat、Agent 和 Brain workflow 的结果写入独立目录，不能跑就显式记录 skipped 或 error，不伪造成成功。

回答质量上，我把阶段 14 的 review 样例继续复核，分别判断 Faithfulness、Answer Coverage 和 Citation Quality。最后把 baseline、真实配置状态、回答复核和 Decompose provenance 汇总成只读报告，让后续能清楚判断是资料不足、检索不足、回答覆盖不足，还是只是缺少真实配置复跑结果。

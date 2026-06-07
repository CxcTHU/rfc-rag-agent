# 阶段 16 设计：真实质量风险闭环

## 目标

阶段 16 的目标是处理阶段 15 质量报告已经暴露的发布前风险，而不是继续扩展新功能。阶段 15 已经证明真实配置可以跑通 vector、hybrid、chat、agent 和 Brain workflow，但仍留下两个高优先级问题：

1. `real_config/decompose` 出现真实 embedding 请求 `SSL: UNEXPECTED_EOF_WHILE_READING`。
2. `data/evaluation/stage15_answer_coverage_review.csv` 中 1 条 high 风险样例和 8 条 medium 样例仍需要闭环复核。

阶段 16 要把这些风险从“报告里有 high/medium”推进到“每个风险都有根因分类、闭环判断、后续动作和质量门槛结论”。

核心链路：

```text
stage15 quality report
-> decompose real_config error diagnosis
-> stage16 answer coverage closure
-> stage16 quality closure summary
-> read-only report update
-> docs/progress / README / Obsidian conclusion
-> user manual verification before commit/tag/push
```

本阶段不把真实 API 调用变成默认回归前提。默认测试继续使用 deterministic 或 mock 数据；真实配置只允许在用户显式要求或本地显式运行时调用。

## 阶段输入

阶段 16 复用阶段 14/15 的质量产物：

```text
data/evaluation/stage14_embedding_comparison.csv
data/evaluation/stage14_real/real_config_status.csv
data/evaluation/stage15_answer_coverage_review.csv
data/evaluation/stage15_quality_summary.csv
docs/stage15_quality_report.md
data/evaluation/stage14_decompose_provenance_review.csv
```

阶段 16 不新增外部资料来源，不新增爬虫链路，不保存受限全文，不保存 API key。

## Decompose SSL EOF 排查

阶段 16 对 `real_config/decompose` 的 `SSL EOF` 做诊断闭环，而不是用 deterministic decompose 的 10/10 覆盖真实失败。

建议输出：

```text
data/evaluation/stage16_decompose_diagnostics.csv
```

建议字段：

```text
diagnostic_id
suite
status_before
status_after
error_type
root_cause
reproducibility
safe_to_retry
blocking_status
evidence
next_action
```

错误分类：

| error_type | root_cause | 说明 |
|---|---|---|
| ssl_eof | provider_network_ssl_eof | HTTPS 读取阶段被远端、代理或网络层中断 |
| timeout | provider_timeout | 请求超过配置或脚本等待时间 |
| configuration_missing | real_config_missing | provider、model、base_url、api_key 或 dimension 缺失 |
| provider_http_error | provider_response_error | 真实供应商返回 HTTP 错误，例如 429 或 5xx |
| script_orchestration | script_timeout_or_partial_output | 外层调度超时、子任务部分完成或状态合并失败 |
| unknown | needs_manual_review | 错误摘要不足，需要保留人工排查 |

处理规则：

- 如果能通过 timeout、retry 或错误分类改进修复，必须补测试并保留真实配置与 deterministic baseline 的边界。
- 如果判断为外部供应商或网络问题，记录为可重试或阻断状态，不能伪造成真实通过。
- 如果没有显式 `--run-real`，脚本必须 graceful skip，不访问真实网络。
- 错误摘要必须脱敏，不得写入 API key、Bearer token、供应商原始敏感响应或受限全文。

## Answer Coverage 闭环

阶段 16 对阶段 15 的 high/medium 复核行建立闭环表：

```text
data/evaluation/stage16_answer_coverage_closure.csv
```

建议字段：

```text
closure_id
source_review_id
query_id
risk_before
risk_after
faithfulness
answer_coverage
citation_quality
root_cause
evidence
decision
next_action
manual_review_note
```

复核对象：

- high：`user_mixed_itz_strength`
- medium：阶段 15 表中其余 8 条 medium 样例

闭环规则：

| 条件 | risk_after | decision |
|---|---|---|
| 真实回答缺失、超时、检索未返回、关键来源无法支持回答 | high | blocking |
| 来源匹配且回答摘要覆盖核心要点，但仍缺少细节或资料只到题录级 | medium | accepted_with_review |
| Faithfulness、Answer Coverage、Citation Quality 均为 pass | low | accepted |
| 证据不足但回答明确拒答且符合 expected_answer_points | low 或 medium | accepted_refusal 或 review |

`risk_after` 不能只凭来源命中自动降级。来源命中只说明找到了资料，Answer Coverage 要判断回答是否覆盖 `expected_answer_points`。

## 质量汇总与 Quality Gate

阶段 16 新增质量闭环汇总：

```text
data/evaluation/stage16_quality_closure_summary.csv
docs/stage16_quality_closure_report.md
```

建议字段：

```text
section
metric
status
value
baseline_value
risk_before
risk_after
evidence_file
recommendation
```

质量门槛：

```text
closure_ready/low
  没有 high 风险；medium 风险均有明确人工审阅结论和 next_action。

closure_ready/medium
  没有阻断型 high 风险；仍存在可接受的资料细节不足或人工审阅样例。

review_required/high
  仍存在真实配置错误未分类、真实回答超时未处理、关键问题无法回答或来源不支持回答。
```

阶段 16 的目标是尽量把阶段 15 的 `review_required/high` 降到更可接受状态；如果仍为 high，必须说明阻断原因。

## 只读报告边界

阶段 16 可以最小更新 `/quality-report` 展示阶段 16 闭环状态，但必须遵守：

- 只读展示，不触发真实 API 调用。
- 不写数据库，不触发 source reindex。
- 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。
- 不重构核心前端工作台。
- 不显示 API key、Bearer token、供应商原始敏感响应或受限全文。

## 阶段边界

阶段 16 不做：

- 不做写入型 Agent 工具。
- 不做复杂 LangGraph workflow。
- 不做登录系统。
- 不做部署优化。
- 不新增爬虫或外部资料来源。
- 不把 HyDE 接入默认链路或自动回归。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。

阶段 16 要做：

- 固化真实质量风险闭环设计。
- 排查或分类 real decompose SSL EOF。
- 对 1 条 high 和 8 条 medium Answer Coverage 样例建立闭环表。
- 生成阶段 16 质量闭环汇总和报告。
- 保证旧 API 和 deterministic baseline 不被破坏。
- 完成普通文档、Obsidian 草稿、测试验证，并停在用户人工核验前状态。

## 完成标准

- `docs/stage16_quality_risk_closure.md` 存在并覆盖目标、输入、风险分级、排查流程、复核标准、安全边界和完成标准。
- `data/evaluation/stage16_decompose_diagnostics.csv` 存在，说明 real decompose SSL EOF 的根因分类、是否阻断和 next_action。
- `data/evaluation/stage16_answer_coverage_closure.csv` 存在，覆盖阶段 15 的 1 条 high 和 8 条 medium 样例。
- `data/evaluation/stage16_quality_closure_summary.csv` 和 `docs/stage16_quality_closure_report.md` 存在，说明 risk_before/risk_after 和 quality gate。
- 保留 deterministic baseline 与 real_config 边界，不用 deterministic 结果掩盖真实失败。
- 旧 search/vector/hybrid/chat/agent API 和 `/quality-report` 不被破坏。
- 阶段 16 测试、相关回归和最终全量测试通过。
- README、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD 判断和 Obsidian 本地知识库完成阶段收尾。
- 最终停在未提交状态，等待用户人工核验。

## 面试表达

阶段 16 我没有继续加 RAG 新功能，而是处理发布前质量报告中的真实风险。阶段 15 已经能跑通多数真实配置，但 real decompose 发生 SSL EOF，Answer Coverage 还有 1 条 high 和 8 条 medium 样例。因此我把质量风险拆成两条闭环：一条是对真实 provider 错误做根因分类，区分网络、超时、配置和脚本编排；另一条是对回答覆盖做逐条复核，记录 risk_before、risk_after、根因、证据和 next_action。

这样做的好处是质量门槛不再只是“有几个 high”，而是能解释每个风险是否已处理、是否仍阻断、下一阶段应该怎么做。同时我保留 deterministic baseline 和 real_config 的边界，不用本地稳定结果掩盖真实模型失败，也不把真实 API 调用变成自动回归前提。

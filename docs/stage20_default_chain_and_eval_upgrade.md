# 阶段 20 设计：中文检索默认链路落地与评测判定增强

## 目标

阶段 19 已经证明：`source_type_reweight` 能把中文查询的 `deep_fulltext_top1_rate` 从 0.000 提高到 0.533-0.733，但旧 `precision@1` 判定偏向题录卡片，导致默认链路结论仍是 `keep_existing_hybrid`。阶段 20 的目标不是继续加语料或模型，而是把“能不能切默认链路”的判定口径变得更可靠，并补上阶段 19 暴露的工程责任拒答边界。

核心链路：

```text
阶段 19 中文难评测集与 source_type_reweight 候选
-> 答案级 coverage_ratio 判定
-> 真实 Jina query 端校验（不重做 chunk embedding）
-> 默认链路切换门槛判定
-> responsibility_gate 工程责任拒答
-> quality gate / 报告更新
-> 回归 + 文档 + Obsidian
```

阶段 20 只在数据证明充分时才把 `source_type_reweight` 接入默认 hybrid 链路；否则继续保持 `keep_existing_hybrid`，并写明阻断原因。

## 输入

阶段 20 复用以下阶段 19 产物：

```text
docs/stage19_chinese_analysis_retrieval_tuning.md
docs/stage19_literature_review.md
data/evaluation/stage19_chinese_hard_queries.csv
data/evaluation/stage19_retrieval_tuning_results.csv
data/evaluation/stage19_retrieval_tuning_summary.csv
scripts/evaluate_stage19_retrieval_tuning.py
app/services/retrieval/source_type_reweight.py
```

关键阶段 19 结论：

| Config | p@1 | deep_fulltext_top1 | refusal_accuracy | Stage 19 decision |
|---|---:|---:|---:|---|
| hybrid_baseline | 0.400 | 0.000 | 0.750 | baseline |
| hybrid_fulltext_boost | 0.333 | 0.533 | 0.750 | keep_existing_hybrid |
| hybrid_metadata_demote | 0.333 | 0.533 | 0.750 | keep_existing_hybrid |
| hybrid_topic_anchor_strict | 0.200 | 0.733 | 0.750 | keep_existing_hybrid |

阶段 20 还复用本地已有双索引：

```text
deterministic / hash-token-v1 / dim=64 / chunks=8918
openai-compatible / jina-embeddings-v3 / dim=1024 / chunks=8918
```

本阶段不重做 chunk embedding，只在显式真实校验模式下调用 Jina 生成 query embedding。

阶段 20 新增评测升级产物：

```text
scripts/evaluate_stage20_eval_upgrade.py
data/evaluation/stage20_eval_upgrade_results.csv
data/evaluation/stage20_eval_upgrade_summary.csv
data/evaluation/stage20_eval_upgrade_real_jina_results.csv
data/evaluation/stage20_eval_upgrade_real_jina_summary.csv
data/evaluation/stage20_default_chain_decision.csv
tests/test_stage20_eval_upgrade.py
tests/test_stage20_default_chain_decision.py
```

## 评测判定升级口径

阶段 19 的 `expected_source_hit` 更像“标题/正文关键词命中”，容易让题录卡片占便宜。阶段 20 新增答案级 `coverage_ratio`，用 `expected_answer_points` 判断检索证据是否覆盖答案要点。

基础规则：

```text
coverage_ratio = covered_answer_points / total_answer_points
hit = coverage_ratio >= threshold
```

默认阈值：

```text
threshold = 0.60
```

实现要求：

- 对非拒答题，用 top-1 或用于回答的候选证据计算 `coverage_ratio`。
- `expected_answer_points` 用分号分隔，按中英文归一化、大小写归一、空白归一后匹配。
- 可以保留 `expected_source_hit` 作为辅助诊断字段，但不能让它主导 `hit`。
- 可选 `llm_judge` 只能作为离线模式，不进入 CI、本地全量测试或默认回归。
- 每条结果必须显式记录 `judge_mode`，例如 `coverage_ratio`、`coverage_ratio_real_jina`、`llm_judge_offline`。

阶段 20 结果表至少包含：

```text
query_id
config
judge_mode
hit
coverage_ratio
deep_fulltext_top1
refusal_matched
decision
next_action
```

推荐扩展字段：

```text
top1_source_type
top1_document_title
covered_points
missing_points
real_config_status
error
```

当前 deterministic 复跑结果（Phase 2）：

| Config | p@1 (`coverage_ratio`) | avg_coverage | deep_fulltext_top1 | refusal_accuracy | Decision |
|---|---:|---:|---:|---:|---|
| hybrid_baseline | 0.133 | 0.323 | 0.267 | 1.000 | baseline |
| hybrid_fulltext_boost | 0.133 | 0.273 | 0.667 | 1.000 | keep_existing_hybrid |
| hybrid_metadata_demote | 0.133 | 0.273 | 0.667 | 1.000 | keep_existing_hybrid |
| hybrid_topic_anchor_strict | 0.133 | 0.273 | 0.733 | 1.000 | keep_existing_hybrid |

解释：升级判定后，候选配置仍能显著提高深度全文 top-1，但 `p@1` 没有超过 baseline（`Δp@1=0.000<0.10`），因此 deterministic 主结论仍是 `keep_existing_hybrid`。这不是失败，而是阶段 20 要求的诚实判定：默认链路切换必须同时证明答案覆盖增益和深度全文上浮。

真实 Jina query 端校验结果（Phase 3）：

| Config | real_config_status | p@1 (`coverage_ratio`) | avg_coverage | deep_fulltext_top1 | refusal_accuracy | Decision |
|---|---|---:|---:|---:|---:|---|
| hybrid_baseline | completed | 0.133 | 0.323 | 0.267 | 1.000 | baseline |
| hybrid_fulltext_boost | completed | 0.133 | 0.273 | 0.667 | 1.000 | keep_existing_hybrid |
| hybrid_metadata_demote | completed | 0.133 | 0.273 | 0.667 | 1.000 | keep_existing_hybrid |
| hybrid_topic_anchor_strict | completed | 0.133 | 0.273 | 0.733 | 1.000 | keep_existing_hybrid |

解释：真实 Jina 只在 query 端运行，复用已有 `jina-embeddings-v3` chunk 索引；本次校验为 `completed`，未记录真实错误。真实校验与 deterministic 主结论一致：候选仍未达到 `Δp@1>=0.10`，默认链路不应切换。

默认链路决策表（Phase 4）：

| Config | Deterministic Δp@1 | Real Jina Δp@1 | Deterministic Δdeep | Real Δdeep | Final decision | Blocker |
|---|---:|---:|---:|---:|---|---|
| hybrid_fulltext_boost | +0.000 | +0.000 | +0.400 | +0.400 | keep_existing_hybrid | `delta_precision_at_1=+0.000<0.10` |
| hybrid_metadata_demote | +0.000 | +0.000 | +0.400 | +0.400 | keep_existing_hybrid | `delta_precision_at_1=+0.000<0.10` |
| hybrid_topic_anchor_strict | +0.000 | +0.000 | +0.466 | +0.466 | keep_existing_hybrid | `delta_precision_at_1=+0.000<0.10` |

结论：阶段 20 不把 `source_type_reweight` 焊进默认 `HybridSearchService` / Brain hybrid 链路；该模块继续保留为候选/评测开关。由于没有切换默认链路，本阶段不需要新增默认链路回滚配置；后续若新评测集或人工判定证明 `Δp@1` 过门槛，再按本设计中的配置开关方案接入。

`responsibility_gate` 接入后，阶段 19 遗留的 `cn_hq_refusal_engineering_responsibility` 已在 deterministic 与真实 Jina query 校验结果中均达到 `refusal_matched=true`，四个配置的 refusal accuracy 均为 1.000。

## 真实 Jina Query 端校验

阶段 20 的真实 Jina 校验只验证 query 端，不重做 chunk embeddings。

允许做：

```text
query
-> Jina query embedding
-> 读取已有 jina-embeddings-v3 chunk embeddings
-> vector 或 hybrid 候选排序
-> coverage_ratio 判定
```

不允许做：

```text
重新为 8918 chunks 生成 embedding
把真实 API key 写入源码/CSV/文档/测试/Obsidian
把真实供应商原始响应写入任何可提交文件
让真实 API 成为 pytest 全量测试前提
```

真实配置状态必须诚实记录：

| Status | Meaning |
|---|---|
| completed | 真实 query embedding 调用成功，结果已写入脱敏 CSV |
| skipped | 本地未配置真实 Jina 所需环境变量 |
| error | 真实调用失败，已写入脱敏错误摘要 |

## 默认链路接入门槛与回滚

阶段 20 延续阶段 19 的严格切换门槛，但用升级后的 `coverage_ratio` 判定计算 `p@1`：

```text
candidate_switch_allowed =
  delta_precision_at_1 >= 0.10
  and delta_deep_fulltext_top1_rate >= 0.20
  and refusal_accuracy >= baseline_refusal_accuracy
```

解释：

- `delta_precision_at_1 >= 0.10`：升级后 top-1 判定必须真实提升。
- `delta_deep_fulltext_top1_rate >= 0.20`：中文深度全文必须明显上浮。
- `refusal_accuracy >= baseline_refusal_accuracy`：拒答边界不能退化。

若满足门槛：

- 将通过门槛的 `source_type_reweight` 配置接入默认 hybrid 链路。
- 接入位置优先放在 retrieval/Brain 共享边界，避免 `/chat` 与 Agent 各自复制逻辑。
- 提供配置开关，例如 `HYBRID_SOURCE_TYPE_REWEIGHT_ENABLED` 与 `HYBRID_SOURCE_TYPE_REWEIGHT_PROFILE`。
- 默认回滚方式是关闭开关，恢复旧 `HybridSearchService` 行为。
- 不改变 `POST /search/hybrid`、`POST /chat`、`POST /agent/query` 的响应 schema。

若不满足门槛：

- 保持 `keep_existing_hybrid`。
- 在结果表、quality gate 和文档中写明阻断项，例如 `delta_precision_at_1_below_threshold`、`refusal_regression`、`real_jina_error`。
- `source_type_reweight` 继续作为评测/配置候选保留。

## responsibility_gate 设计

`has_topic_anchor` 解决的是 off-topic 问题；阶段 19 遗留的 `cn_hq_refusal_engineering_responsibility` 属于另一类：问题与堆石混凝土同主题，但要求系统替代规范审查、工程设计、第三方检测或专家签字。

阶段 20 新增 `responsibility_gate`：

```text
question
-> responsibility_gate
-> evidence confidence / has_topic_anchor
-> generate_answer
```

触发问题示例：

```text
这个配合比是否符合规范？
请判定该工程是否合格。
能否出具质量评定结论？
这个设计方案是否可以直接用于工程？
帮我评定这份检测报告是否有效。
```

拒答提示原则：

- 明确系统不能替代规范审查、工程设计、第三方检测或专家签字。
- 可以建议用户把问题改成“资料中有哪些指标、试验方法或影响因素”。
- 不泄露或生成受限全文。

不应误拒的问题：

```text
堆石混凝土配合比通常关注哪些指标？
规范审查和文献问答有什么区别？
资料中提到的抗压强度影响因素有哪些？
自密实混凝土填充能力如何试验评价？
```

## Quality Gate 与报告

阶段 20 的 quality gate 至少记录以下结论：

| Section | Required conclusion |
|---|---|
| eval_judge_upgrade | `coverage_ratio` 是否已替代关键词偏置主判定 |
| real_jina_query_validation | 真实 query 端校验 completed/skipped/error |
| default_chain_decision | switch / keep_existing_hybrid 及原因 |
| responsibility_gate | 工程责任拒答遗留是否闭环 |
| api_regression | 核心 API 是否回归通过 |
| overall | pass / review_required / blocked |

如果更新 `/quality-report`，只能保持只读：

- 不触发真实 API。
- 不写数据库。
- 不新增登录系统。
- 不改变核心工作台行为。

## API 与兼容边界

阶段 20 必须保证以下入口不被破坏：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
GET /quality-report
```

默认链路改动后仍要保证：

- 请求字段兼容。
- 响应 schema 兼容。
- citation/source 返回结构兼容。
- deterministic baseline 仍可稳定回归。

## 数据安全边界

- 阶段 20 不新增爬虫或外部资料来源。
- 用户合法下载的中文全文继续只留在本地 `data/raw/`、`data/fulltext/`、`data/app.sqlite`，不进 Git。
- 真实 API key、Bearer token、供应商原始敏感响应不得写入源码、文档、CSV、测试或 Obsidian。
- 真实 Jina/MIMO 失败要显式记录，但错误摘要必须脱敏。
- 阶段 20 结果表只保存查询、配置、脱敏来源标题、指标、决策和 next_action。
- `obsidian-vault/` 是本地知识库，不提交到 Git。

## 完成标准

- 新增 `docs/stage20_default_chain_and_eval_upgrade.md` 并覆盖目标、输入、评测判定升级、默认链路门槛与回滚、`responsibility_gate`、安全边界和完成标准。
- 用 `coverage_ratio` 在阶段 19 中文难评测集上重跑，并生成阶段 20 结果表。
- 真实 Jina query 端校验可选可运行；未配置或失败时显式记录。
- 默认链路接入决策由升级后数据决定：过门槛才切，没过则保持 `keep_existing_hybrid`。
- `responsibility_gate` 闭环阶段 19 工程责任拒答遗留，并通过正反例测试证明不过度拒答。
- 更新 quality gate / 报告，使阶段 19 默认链路遗留与责任边界遗留有闭环状态。
- 保证核心 API 不被破坏。
- 阶段 20 聚焦测试与全量测试通过。
- 同步 README、docs/progress、docs/architecture、docs/data_sources、AGENT.MD 判断和 Obsidian 本地知识库。
- 最终不提交、不打 `phase-20-complete` tag、不 push、不 PR，停在用户人工核验前。

## 面试表达

阶段 20 我处理的是 RAG 系统从“调优候选”到“默认链路决策”的工程闭环。阶段 19 发现深度全文加权能显著提高中文全文 top-1，但旧 precision@1 偏向题录关键词，所以我先把评测判定升级为答案级 coverage ratio，再用真实 Jina 做 query 端校验，避免只看 deterministic 结果。默认链路是否切换不是拍脑袋，而是同时满足 p@1 增益、深度全文 top-1 增益和拒答不退化才接入，并且配置可关闭、可回滚。

另一个重点是责任边界。`has_topic_anchor` 只能挡 off-topic，不能挡“同主题但要求系统替代工程审查”的问题，所以我新增 `responsibility_gate`：资料问答可以解释指标、试验和影响因素，但不能替用户判定工程是否合格、是否符合规范或出具审查结论。这样既保留 RAG 的学习价值，也守住工程责任边界。

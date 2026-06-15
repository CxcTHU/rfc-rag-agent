# 阶段 36 设计：生成可靠性与多轮体验稳定化

## 目标

阶段 36 从阶段 35 已合并后的 `main -> dc751fb` 出发，目标是把真实用户能感知到的生成可靠性和多轮体验做稳，而不是继续追分。

核心链路：

```text
阶段 35 Judge gate FAIL 与拒答信息单薄
-> 拒答可解释性升级
-> 生产 smoke 一键自动化
-> Judge gate 离线攻坚（outline-first + answer provider A/B）
-> 多轮意图路由回归或按需模块化
-> 文档、Obsidian 与人工核验前收尾
```

阶段 36 的默认验收口径：

```text
Stage 30 = 91.52 / A / pass
Judge gate = 显式攻坚，不强行包装通过
生产 smoke = --execute 一键通过
多轮体验 = 转述、追问、来源、模型信息、拒答原因、闲聊、off-topic、正常领域问答均有回归
```

## 输入基线

```text
main / origin/main -> dc751fb Merge pull request #5 from CxcTHU/codex/phase35-multiturn-intent-router
phase-35-complete -> 7877308 Complete phase 35 remediation with Judge gate documented
phase-35-complete 已合并到 main
阶段 35 多轮意图路由补充 -> 0af4a87 Add phase 35 multiturn intent routing supplement
目标分支 -> codex/phase-36-generation-reliability-and-conversation-stability
```

阶段 35 的干净结论：

```text
Stage 30 overall=91.52 grade=A release_decision=pass
真实 Judge gate FAIL：answer_coverage=0.410 citation_support=0.635 safety_leak_check=1.000
citation_validator 已从生产 Brain 解耦，只保留为离线评测工具
```

## Phase 范围

### Phase 1：设计文档与评价口径

固定阶段 36 的主线、辅线、不做事项、安全边界和完成标准。新增 `tests/test_stage36_design.py`，确保文档明确不替换默认 provider、不接危险后处理、不引入外部数据源，并记录 Judge gate 离线时限。

### Phase 2：拒答可解释性升级

拒答分两类增强：

- `off_topic`：返回安全的改写建议，例如引导用户把问题改成 RFC、水利工程、混凝土材料、施工质量或工程案例相关问题。改写建议不能暴露内部规则原文、prompt 原文或关键词表。
- `evidence_insufficient`：返回真实检索命中的来源摘要，说明检索到了哪些来源、覆盖哪些方面、还缺什么关键词。摘要必须来自 source title、source_type 和短内容摘要，单条摘要不超过 200 字符，不暴露完整 chunk 全文。

该能力可以通过 metadata 兼容字段输出，不修改 `/agent/query` 外部响应 schema。不得让 LLM 编造检索摘要。

### Phase 3：生产 smoke 自动化

新增 `scripts/run_production_smoke.py`，默认 dry-run，显式 `--execute` 才访问真实端点。

覆盖端点：

```text
GET /health
GET /quality-report
GET /quality-report/data.json
POST /agent/query（正常 RAG）
POST /agent/query（多轮转述）
POST /agent/query（meta 模型信息）
POST /agent/query/stream
```

输出 `data/evaluation/stage36_production_smoke_results.csv`，字段只包含 endpoint、status、latency_ms、required_fields_present、refused、citation_count、validator_marker、sensitive_field_detected、error_summary 等安全字段。不得写入 API key、Bearer token、raw provider response、reasoning_content、hidden thought 或完整 chunk 全文。

### Phase 4：Judge gate 离线攻坚

只做离线实验，不接生产链路，不改默认 provider 拓扑。

A 方案：`outline-first` 答题策略。模型先输出覆盖要点 outline，并把每个要点 anchor 到 source chunk_id；第二步再填充答案。可新增 `app/services/generation/outline_first_strategy.py`，默认关闭。

B 方案：answer provider A/B。保留现有 planner 拓扑，把 `DeepSeek-V3.2-Thinking` 作为 V4-Pro 的离线对照，仍走现有 Paratera/OpenAI-compatible provider 配置边界。

Judge gate 攻坚时限为不超过 2 周。真实 Judge 样本不少于 20 条，至少包含 baseline、outline-first、answer provider A/B 三组。输出：

```text
data/evaluation/stage36_judge_strategy_ab_results.csv
data/evaluation/stage36_judge_strategy_ab_summary.csv
docs/stage36_judge_strategy_decision.md
```

若任一方案在不少于 20 条真实样本上满足 `answer_coverage >= 0.80`、`citation_support >= 0.80`、`safety_leak_check >= 0.80`，只写接入决策报告，由用户决定是否进入生产。若达不到，必须诚实归因，不强行包装为通过。

### Phase 5：多轮路由模块化辅线

多轮意图路由补充已经在 `0af4a87` 合并并人工验收。阶段 36 只判断是否需要模块化：

- 如果路由逻辑仍分散在 `app/api/agent.py` 且难以维护，可抽取 `app/services/agent/intent_router.py`。
- 如果现有代码已经清晰，则只补回归测试集和文档，不强制重构。

回归集至少覆盖 8 类意图：上一轮翻译、追问、问来源、问模型、问为什么拒答、闲聊、off-topic、正常领域问答。

### Phase 6：文档、Obsidian 与收尾验证

更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，新增 `docs/phase_reviews/phase-36.md`。统一补齐 Obsidian 阶段页、Phase 0-6 汇报、首页、阶段索引和阶段汇报索引。

收尾验证必须包括：

```text
python -m pytest -q
python scripts/score_stage30_quality.py
python scripts/run_production_smoke.py --execute
浏览器 smoke：桌面 + 390x844 移动端
```

`score_stage30_quality.py` 必须仍为 `91.52 / A / pass`。浏览器 smoke 必须确认 `/quality-report` 和 Agent 查询无横向溢出，console errors=0。

## 不做事项

阶段 36 不做：

- 不接 `citation_validator` 或任何 deterministic 后处理进生产链路。
- 不替换默认 chat provider。
- 不替换默认 embedding provider。
- 不替换默认 rerank provider。
- 不动 chat provider 拓扑。
- 不改 Stage 30 评分权重、等级阈值或 release_decision 规则。
- 不引入新外部数据源，不爬新网页，不下载新 PDF，不重切 chunk。
- 不做 tool-calling 协议迁移。
- 不做多用户隔离或 Conversation owner 权限系统。
- 不做写入型 Agent 工具。
- 不让真实 API 成为 CI 或本地全量 pytest 的前提。

## 安全边界

任何 CSV、文档、测试和 Obsidian 草稿不得写入：

- API key
- Bearer token
- Authorization header
- raw provider response
- `reasoning_content`
- hidden thought
- 完整 chunk 全文
- 受限全文

拒答解释、production smoke 和 Judge A/B 的输出只保存脱敏指标、短摘要、状态、错误摘要和必要的 provider/model 名称。真实 provider 调用必须显式执行，失败时记录 `skipped` 或 `error`，不能用 deterministic 结果冒充真实通过。

## 关键概念解释

`outline-first`：一种离线生成策略，先让模型列出答案要点和每个要点对应的 source/chunk，再生成正文。在本项目中它只作为 `app/services/generation/` 下的候选策略，用于修复 answer coverage 与 citation support 不稳定的问题。面试中可以说：我没有直接让模型自由生成，而是先约束答案骨架和证据锚点，再填充自然语言。

`answer provider A/B`：用同一批问题、同一批检索证据，对比不同 answer 模型的生成质量。在本项目中只作为 Stage 36 离线 Judge 实验，不替换生产默认 provider。面试中可以说：我把 provider 对比限制在 answer 层，避免把 planner、embedding、rerank 一起变成混杂变量。

`production smoke`：面向真实运行端点的最小可用性检查。它不是全量测试，而是验证 `/health`、`/quality-report`、`/agent/query` 和流式接口在生产配置下可用，并且不泄漏敏感字段。面试中可以说：pytest 保证代码逻辑，production smoke 保证真实服务链路没有断。

## 完成标准

- 阶段 36 分支从 `main -> dc751fb` 创建，`phase-35-complete -> 7877308` 未移动。
- 新增设计文档与设计测试，固定范围、边界和验收口径。
- 拒答可解释性落地：off-topic 有改写建议，evidence_insufficient 有脱敏检索摘要，单条摘要不超过 200 字符。
- 新增生产 smoke 脚本和测试，`--execute` 一键通过，CSV 含安全字段且不含敏感字段。
- Judge gate 显式完成 outline-first + answer provider A/B 的离线攻坚，真实样本不少于 20 条；通过则写决策报告，不通过则写诚实归因。
- 多轮路由至少补齐 8 类意图回归；是否抽取 `intent_router.py` 由代码状态决定。
- Stage 30 维持 `91.52 / A / pass`，评分规则、provider 和数据源均不变。
- 全量 pytest 通过；浏览器 smoke 桌面与 390x844 移动端通过。
- 最终停在用户人工核验前：不 `git add`，不 commit，不创建 `phase-36-complete` tag，不 push，不创建 PR。

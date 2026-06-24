# Phase 52 Real API Memory Evaluation Goal Prompt

## 目标

继续在 `G:\Codex\program\rfc-rag-agent` 完成 Phase 52 记忆模块的真实 API 测评阶段。目标是建立测评集、实现真实 API 测评脚本、运行 current vs legacy 对照、生成报告，并判断当前记忆系统是否满足目标、是否相对旧策略有进步。

正式测评结论必须来自真实 API。deterministic / offline 测试只能作为代码回归护栏，不能作为“是否满足目标”或“是否有进步”的依据。

## 开工核对

开始前必须完成：

1. 完整阅读 `AGENT.MD`。
2. 阅读 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
3. 阅读 `docs/stage52_agent_memory_context.md`、`docs/phase_reviews/phase-52.md`、`docs/stage52_semantic_upgrade_prompt.md`。
4. 阅读根目录 `task_plan.md`、`findings.md`、`progress.md`。
5. 运行 `git status -sb` 和 `git log --oneline -5`。
6. 确认仍在 `codex/phase-52-agent-memory-context` 或用户指定的 Phase 52 工作分支。

不要切换到 reranker 分支，不处理 reranker stash / worktree。未经用户核验，不执行 `git add`、commit、tag、push、PR。

## 证据等级

本阶段必须严格区分证据等级：

- 真实 API full evaluation：可用于正式质量结论。
- 真实 API smoke evaluation：可用于脚本与输出格式确认，不足以作为最终结论。
- deterministic / offline regression：只用于代码回归护栏，不可用于证明语义质量或进步。

所有正式测评集、最终指标、current vs legacy 结论，都必须来自真实 API。

## 安全与脱敏要求

- 真实 API 调用必须显式使用 `--execute`。
- 默认 dry-run 只能校验配置、schema 和用例，不可发起 API 请求。
- 不在任何文件中写入 API key。
- 不保存隐藏推理、完整模型原文、完整检索 chunk 或敏感会话内容。
- 结果文件只保存结构化标签、脱敏摘要、评分、错误类型、provider/model metadata、latency 和必要审计字段。
- 长期记忆必须保持默认禁用态，不发生默认写入。

## Phase 52L：测评方案与规划文件

任务：

- 编写或更新 `docs/stage52_memory_real_api_eval_prompt.md`。
- 更新根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 明确真实 API 测评目标、阶段拆分、指标和验收门槛。

自验收：

- 三份规划文件与 prompt 均明确正式结论必须来自真实 API。
- 后续每个小 phase 都有明确产物和验收标准。
- deterministic 测试被明确限定为代码回归护栏。

通过后，更新三份规划文件，再进入 Phase 52M。

## Phase 52M：建立真实 API 测评集

任务：

- 新建 `data/evaluation/phase52_memory_real_api_cases.csv`。
- 编写不少于 90 条人工标注用例。
- 覆盖 follow-up、新主题、纠错、stale anchor、长上下文 recency、证据不足、拒答边界、prior evidence citation 禁止、长期记忆禁用态。

建议 schema：

```text
case_id,category,turns_json,current_question,expected_intent,expected_prior_decision,expected_planner_action,expected_long_term_enabled,expected_citation_from_prior_allowed,expected_guardrail,baseline_failure_mode,tags,notes
```

自验收：

- 用例总数不少于 90。
- 每个 category 达到规划最低覆盖。
- 每条用例都有人工期望标签和 baseline failure mode。
- 用例不依赖外部知识库新增数据，不包含敏感信息。

通过后，更新三份规划文件，再进入 Phase 52N。

## Phase 52N：实现真实 API 测评脚本

任务：

- 新建 `scripts/evaluate_phase52_memory_real_api.py`。
- 支持 `--execute`、`--limit`、`--case-id`、`--resume`、`--mode current|legacy|both`、`--output-dir`。
- 调用真实 chat/planner API、真实 embedding API；需要主观质量判断时调用真实 judge API。
- 输出：
  - `data/evaluation/phase52_memory_real_api_results.csv`
  - `data/evaluation/phase52_memory_real_api_summary.csv`
  - `data/evaluation/phase52_memory_real_api_ablation.csv`
- 记录 provider、model、timestamp、latency、retry count、error/skipped reason。

自验收：

- 无 API key 时 dry-run 能给出清晰配置缺失提示。
- `--limit 3 --execute --mode current` 能完成真实 API smoke。
- 脚本错误不会覆盖已有结果，支持 resume。
- 输出不含密钥、隐藏推理、完整模型原文或完整 chunk。

通过后，更新三份规划文件，再进入 Phase 52O。

## Phase 52O：真实 API smoke / full / ablation

任务：

- 先运行 10 条真实 API smoke。
- smoke 通过后运行 full current evaluation。
- 运行 legacy / ablation，对比旧策略与当前策略。
- 汇总失败样本，区分系统缺陷、用例歧义、API 波动、judge 不稳定。

建议通过门槛：

```text
intent_accuracy >= 0.85
correction_recall >= 0.90
prior_reuse_precision >= 0.95
low_relevance_false_reuse_count == 0
stale_anchor_prior_reuse_count == 0
memory_citation_source_true_count == 0
long_term_enabled_count == 0
current_vs_legacy_improved == true
```

自验收：

- 完整结论基于真实 API full evaluation。
- current 与 legacy 至少完成一轮可比对照。
- 所有未达标项都有 case-level 说明和修复建议。

通过后，更新三份规划文件，再进入 Phase 52P。

## Phase 52P：报告、文档与代码回归护栏

任务：

- 编写 `docs/phase_reviews/phase-52-real-api-memory-eval.md`。
- 必要时更新 `docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 运行 deterministic memory regression、pytest、Stage30、`git diff --check` 等代码护栏。
- 在报告中明确：这些 offline 结果不是正式语义质量证据。

建议命令：

```powershell
python scripts/evaluate_phase52_memory.py
python -m pytest tests/test_agent_memory_context.py tests/test_phase52_memory_eval.py tests/test_phase52_memory_intent_classifier.py tests/test_phase52_prior_relevance_gate.py tests/test_session_memory.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_nodes.py -q
python -m pytest -q
python scripts/score_stage30_quality.py
git diff --check
git status -sb
```

自验收：

- 真实 API 报告完成并引用真实结果文件。
- 普通文档和规划文件一致。
- 代码回归护栏结果已记录。
- 停在用户核验前，不提交。

## 最终交付格式

最终回复用户时只总结：

- 新增 / 修改了哪些测评集、脚本、报告和规划文件。
- 真实 API 测评是否完成，关键指标是否达标。
- current vs legacy 是否有进步。
- 哪些 offline 测试作为代码护栏运行过。
- 当前 git 状态和是否等待人工核验。

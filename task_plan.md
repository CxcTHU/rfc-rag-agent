# 阶段 52L-52P 任务计划：真实 API 记忆测评

## 总目标

以完成 Phase 52 记忆系统为目标，建立并运行一套使用真实 API 的记忆能力测评集，判断当前 AgentMemoryContext / planner 记忆语义升级是否满足目标、是否相对旧策略有可验证进步。

正式测评结论必须来自真实 API。deterministic / offline 测试只作为代码回归与 CI 护栏，不能作为“是否满足目标”或“是否有进步”的证据。

## 当前结论

状态：完成，等待用户人工核验。

最终真实 API 测评：

```text
current -> rows=100 completed=100 gate=pass
intent_accuracy=0.9200
correction_recall=1.0000
prior_reuse_precision=1.0000
planner_action_accuracy=0.9700
low_relevance_false_reuse_count=0
stale_anchor_prior_reuse_count=0
memory_citation_source_true_count=0
long_term_enabled_count=0

legacy -> rows=100 completed=100 gate=blocked
prior_reuse_precision=0.7317
low_relevance_false_reuse_count=11
```

## 当前边界

- 工作分支：`codex/phase-52-agent-memory-context`
- 不切换到 reranker 开发分支，不处理 reranker 相关 stash / worktree。
- 不执行 `git add`、commit、tag、push、PR，停在用户核验前。
- 不新增外部知识库或外部数据源；测评用例为人工编写的会话与问题场景。
- 真实 API 测评脚本默认 dry-run，只有显式 `--execute` 才调用真实 API。
- 测评输出已脱敏：不得写入 API key、隐藏推理、完整模型原文、完整检索 chunk 或敏感会话内容。

## 目标产物

- `docs/stage52_memory_real_api_eval_prompt.md`：完成
- `data/evaluation/phase52_memory_real_api_cases.csv`：完成，100 条
- `scripts/evaluate_phase52_memory_real_api.py`：完成
- `data/evaluation/phase52_memory_real_api_results.csv`：完成，200 行 current/legacy
- `data/evaluation/phase52_memory_real_api_summary.csv`：完成
- `data/evaluation/phase52_memory_real_api_ablation.csv`：完成
- `docs/phase_reviews/phase-52-real-api-memory-eval.md`：完成
- 更新 `task_plan.md`、`findings.md`、`progress.md`：完成
- 更新 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`：完成

## 阶段拆分

### Phase 52L：真实 API 测评方案与 prompt

状态：完成

验收：

- 三份规划文件与 prompt 明确要求正式测评全部使用真实 API。
- 文件中包含每个后续小 phase 的自验收节点。
- 文件中包含“通过一个重要小 phase 后，更新规划文件再继续”的循环要求。

### Phase 52M：人工标注真实 API 测评集

状态：完成

验收：

- 用例总数 100。
- 覆盖 followup=20、new_topic=20、correction=15、stale_recency=15、refusal_boundary=10、citation_boundary=10、low_relevance_context=10。
- 每条用例都有人工期望标签。
- 未引入外部语料或未授权敏感数据。

### Phase 52N：真实 API 测评脚本

状态：完成

验收：

- 支持 `--execute`、`--limit`、`--case-id`、`--resume`、`--mode current|legacy|both`。
- dry-run 不发起真实 API 请求。
- 真实模式调用真实 chat intent、真实 embedding relevance 和真实 judge。
- 输出正式 results / summary / ablation CSV。
- 输出不包含密钥、隐藏推理、完整模型原文或完整 chunk。

### Phase 52O：真实 API smoke / full / ablation

状态：完成

验收：

- 已完成多轮真实 API smoke。
- 已完成 100 条用例的 current/legacy full evaluation。
- current gate=pass，legacy gate=blocked。
- current 相比 legacy 在 prior precision、planner action accuracy、low relevance false reuse 上有明确进步。
- 所有正式结果来自真实 API。

### Phase 52P：收尾文档与回归护栏

状态：完成

验收：

- `python scripts/evaluate_phase52_memory.py` -> `cases=32 pass=32 fail=0 pass_rate=1.0000`
- Phase 52 focused tests -> `67 passed`
- `python -m pytest -q` -> `1162 passed, 1 skipped`
- `python scripts/score_stage30_quality.py` -> `overall=91.52 grade=A release_decision=pass`
- `git diff --check` -> 无 whitespace error，仅 LF/CRLF warning
- 正式 real API CSV 敏感字段扫描 -> 无 `api_key` / `bearer` / `authorization` / `raw_response` / `reasoning_content` 命中

最终仍停在用户人工核验前，未提交。

## 交班注意

开工核对时记录的目标分支是 `codex/phase-52-agent-memory-context`，但最终 `git status -sb` 显示当前分支为 `codex/key-improvements-obsidian-sync`。本轮未执行分支切换命令；该分支状态需要用户或后续 agent 人工确认后再提交。

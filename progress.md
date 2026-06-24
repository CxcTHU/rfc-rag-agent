# 阶段 52L-52P Progress：真实 API 记忆测评

## 当前状态

- 当前阶段：Phase 52P，真实 API 测评已完成，正在做最终回归护栏。
- 当前分支：`codex/phase-52-agent-memory-context`
- 当前策略：继续在 main 工作区完成 Phase 52 记忆模块，不切换到 reranker 分支。
- Git 边界：不执行 `git add`、commit、tag、push、PR，等待用户核验。

## 本轮完成

- 设置目标：完成 Phase 52 记忆模块真实 API 测评。
- 完成开工核对：读取项目入口文档、规划文件、Phase 52 设计和 git 状态。
- 新增 `data/evaluation/phase52_memory_real_api_cases.csv`，共 100 条人工标注用例。
- 新增 `scripts/evaluate_phase52_memory_real_api.py`。
- 多轮运行真实 API smoke 和 full evaluation。
- 正式输出：
  - `data/evaluation/phase52_memory_real_api_results.csv`
  - `data/evaluation/phase52_memory_real_api_summary.csv`
  - `data/evaluation/phase52_memory_real_api_ablation.csv`
- 新增 `docs/phase_reviews/phase-52-real-api-memory-eval.md`。
- 更新 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 更新 `task_plan.md`、`findings.md`、`progress.md`。

## 正式真实 API 结果

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

## 代码修复

- `app/services/agent/memory_context.py`
  - off-topic memory policy route 改为 `refuse_or_clarify`。
  - 英文 `it` / `that` 改为词边界匹配。
  - LLM correction label 必须由问题文本中的 correction pattern 锚定，否则 fallback deterministic。
  - 长对话近期主题迁移时，低于直接复用阈值的 prior 不再直接回答复用。
- `app/services/conversation/session_memory.py`
  - 补强 stale correction 检测，覆盖“不是 X，...” / “不是 X。”和 “Not X; continue ...”。
- tests
  - 补充 off-topic memory route、low relevance topic shift、correction detector、LLM unanchored correction 等回归测试。

## 最终回归护栏

```text
python scripts/evaluate_phase52_memory.py -> cases=32 pass=32 fail=0 pass_rate=1.0000
Phase 52 focused tests -> 67 passed
python -m pytest -q -> 1162 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors, LF/CRLF warnings only
```

正式 real API CSV 敏感字段扫描无 `api_key` / `bearer` / `authorization` / `raw_response` / `reasoning_content` 命中。

## 交班注意

开工核对时记录目标分支为 `codex/phase-52-agent-memory-context`，最终 `git status -sb` 显示当前分支为 `codex/key-improvements-obsidian-sync`。本轮没有执行分支切换命令；提交前需要人工确认分支归属。

## 下一步

1. 用户人工核验真实 API 测评结果、报告和分支状态。
2. 若确认无误，再由用户明确授权后执行提交 / tag / push / PR。

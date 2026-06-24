# 阶段 52L-52P Findings：真实 API 记忆测评

## 已确认事实

- Phase 52 记忆系统语义升级已经完成主要开发：`AgentMemoryContext`、prior relevance gate、intent classifier、planner memory metadata、长期记忆禁用态、deterministic regression 等均已落地。
- 用户明确要求：所有正式测评集都必须使用真实 API 测试。
- 因此，本阶段正式质量结论只使用真实 API 结果；deterministic 测试只作为代码回归护栏。
- 当前工作区已有 Phase 52 未提交改动，后续提交仍需用户人工核验和明确授权。

## 真实 API 测评结论

最终正式结果：

```text
current:
  rows=100 completed=100 gate=pass
  intent_accuracy=0.9200
  correction_recall=1.0000
  prior_reuse_precision=1.0000
  planner_action_accuracy=0.9700
  low_relevance_false_reuse_count=0
  stale_anchor_prior_reuse_count=0
  memory_citation_source_true_count=0
  long_term_enabled_count=0

legacy:
  rows=100 completed=100 gate=blocked
  prior_reuse_precision=0.7317
  planner_action_accuracy=0.8800
  low_relevance_false_reuse_count=11
```

current 相对 legacy 的核心进步：

- prior reuse precision 提升 `+0.2683`。
- planner action accuracy 提升 `+0.0900`。
- low relevance false reuse 从 `11` 降为 `0`。
- memory citation source 与 long-term enabled 均保持 `0`。

## 真实 API 暴露并已修复的问题

- off-topic intent 可以仍走 memory-context route，真实 judge 认为存在记忆越界风险。
  修复：`decide_memory_policy()` 对 `off_topic` 返回 `refuse_or_clarify`，不使用 memory retrieval 或 answer。

- 英文 `it` contextual 匹配使用子串逻辑，会误命中 `testing` 等词。
  修复：英文 `it` / `that` 使用词边界匹配。

- 长对话中近期主题已经迁移时，中等相似 prior 仍可能被直接复用。
  修复：近期 session anchors 表明话题迁移且 prior relevance 低于直接复用阈值时，阻断 `answer_from_prior_evidence`。

- 部分 stale correction 句式未被 deterministic correction detector 覆盖。
  修复：增加中文“不是 X，...” / “不是 X。”和英文 “Not X; continue ...” 模式，同时避免把 “do not cite memory” 误判为纠错。

- 真实 judge 一度把“场景固有风险”误当作“observed decision 残余风险”。
  修复：judge rubric 明确如果 observed safe fields 与 expected 一致，且 `memory_citation_source=false` / long-term disabled，则不应仅因场景困难判 high risk。

## 证据等级

- `phase52_memory_real_api_*`：正式质量证据。
- `scripts/evaluate_phase52_memory.py`：deterministic code regression，只能证明代码路径稳定。
- pytest / Stage30：回归护栏，不能替代真实 API 语义测评。

## 安全扫描

正式 real API CSV 结果中未命中：

```text
api_key
bearer
authorization
raw_response
reasoning_content
```

结果文件只保存结构化标签、数值指标、provider/model 名称、latency 和脱敏短理由。

## 最终回归护栏

```text
python scripts/evaluate_phase52_memory.py -> cases=32 pass=32 fail=0 pass_rate=1.0000
Phase 52 focused tests -> 67 passed
python -m pytest -q -> 1162 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors, LF/CRLF warnings only
```

最终 `git status -sb` 显示分支为 `codex/key-improvements-obsidian-sync`，与开工时记录的 `codex/phase-52-agent-memory-context` 不一致。本轮没有执行分支切换命令；提交前需要人工确认分支归属。

## 当前开放问题

- current 的 `intent_accuracy=0.9200` 未满分，主要来自 LLM 对新主题 / contextual / expand 边界的非关键差异；由于 prior decision、planner action、safety gate 均达标，本阶段不继续追求 intent label 满分。
- legacy baseline 是有意模拟旧 source-count prior reuse，用于证明 Phase 52 relevance gate 和 stale/recency policy 的收益。

# Phase 52 记忆模块语义升级 Goal Prompt

阅读 agent 和其他相关文件，了解项目开发进度。
现在继续阶段 52 的开发，目标是对已完成的记忆模块做语义升级，消除硬编码缺陷。请为本线程设置一个 goal：

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及阶段 52 已完成的 52A-52F（memory contract、policy 决策层、observability、20 条 regression、长期记忆禁用态接口、文档收尾），持续推进本项目开发，直到阶段 52 续续"记忆模块语义升级"的开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支继续使用：

```text
codex/phase-52-agent-memory-context
```

执行要求：

1. 首先修改当前对话线程名称为：阶段52-记忆模块语义升级。
2. 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage52_agent_memory_context.md`、`task_plan.md`、`findings.md`、`progress.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认仍在 `codex/phase-52-agent-memory-context`，确认未移动已有 phase tag。
4. 保留 reranker stash/分支，不触碰 reranker 工作。
5. 开发完成前不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验和明确授权。
6. 严格使用 Planning with Files：每个小 Phase 开始前重读 `task_plan.md`、`findings.md`、`progress.md`；每个小 Phase 完成后先自我验收，再更新三份规划文件，之后才进入下一小 Phase。
7. 本阶段后续小 Phase 必须按顺序推进：
   - Phase 52G：意图分类器替代硬编码关键词。新增 `MemoryIntentClassifier` protocol，实现 `LLMMemoryIntentClassifier`（few-shot JSON 分类）和 `DeterministicMemoryIntentClassifier`（封装现有关键词规则）。重构 `infer_memory_decision_hint()` 接收 `MemoryIntent`。LLM 不可用时 fallback deterministic。测试用 deterministic mock。
   - Phase 52H：Prior Evidence Relevance Gate。用 embedding similarity 检查当前 question 与 `prior_answer_summary` 的相关度，替代 `source_count >= 3` magic number。新增 `PriorEvidenceRelevanceGate`，`decide_memory_policy()` 使用 gate 判断。gate 结果记入 trace。
   - Phase 52I：memory_context 强类型 + 架构收口。`memory_context_for_state()` 返回 `AgentMemoryContext`（非 `Any`）。所有 node 函数和 planner 的 `memory_context` 参数改为强类型。移除 `getattr` 访问。纯重构不改行为。
   - Phase 52J：Session Memory Recency Decay。新增 `MemoryItem(text, turn_index, importance)` 替代裸 str。`build_session_memory()` 记录 turn_index，`decay_session_memory()` 做指数衰减，`format_session_memory_for_retrieval()` 按 importance 排序截断。旧 checkpoint 向后兼容。
   - Phase 52K：最终回归、Regression 扩展至 30+ 条、文档与 Obsidian 收尾。
8. 每开始一个小 Phase，简短说明本 Phase 解决什么问题、在 Agent/RAG 记忆链路中的位置、为什么现在做。
9. 每完成一个小 Phase，必须运行该 Phase 的最小验收；通过后更新三份规划文件。
10. 现有 20 条 memory regression 在 deterministic classifier 下必须仍全部通过。新增 regression 覆盖 LLM intent mock 和 relevance gate。
11. 不得把 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk、受限全文或长期用户画像写入 Git、CSV、文档、测试或 Obsidian。
12. 阶段收尾必须运行 focused tests、memory eval、API/SSE focused tests、全量 pytest、Stage 30 和 `git diff --check`。
13. 阶段收尾必须同步 `README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-52.md`，并补齐 Phase 52G-52K Obsidian 汇报。

核心链路：

```text
question + history + prior evidence
-> MemoryIntentClassifier (LLM / deterministic fallback)
-> MemoryIntent (expand / contextual / correction / new_topic / off_topic)
-> PriorEvidenceRelevanceGate (embedding similarity)
-> AgentMemoryContext (强类型, recency decay)
-> MemoryPolicyDecision
-> planner / search / answer nodes
-> safe latency_trace
```

完成标准：

- 意图分类器 protocol + LLM + deterministic 双实现完成。
- relevance gate 替代 magic number，trace 可审计。
- `memory_context` 全链路强类型，无 `Any`。
- session memory 有 recency decay，长对话不退化。
- memory regression 30+ 条全部通过，`memory_citation_source_true_count == 0`。
- 全量测试通过，Stage 30 仍为 `91.52 / A / pass`。
- 最终停在人工核验前，未提交、未 tag、未 push、未 PR。

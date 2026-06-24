# Phase 52 Memory Completion Goal Prompt

阅读 agent 和其他相关文件，了解项目开发进度。
现在继续阶段 52 的开发，目标是完成整个记忆模块。请为本线程设置一个 goal：

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及阶段 52 已完成的 `AgentMemoryContext`、`MemoryPolicyDecision`、memory trace、8 条 memory regression 和长期记忆禁用态接口，持续推进本项目开发，直到阶段 52 续“记忆模块完备化”的开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支继续使用：

```text
codex/phase-52-agent-memory-context
```

执行要求：

1. 首先确认当前线程名称应保持或改为：阶段52-记忆模块完备化。
2. 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage52_agent_memory_context.md`、`task_plan.md`、`findings.md`、`progress.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认仍在 `codex/phase-52-agent-memory-context`，确认未移动已有 phase tag。
4. 保留 reranker stash/分支，不触碰 reranker 工作。
5. 开发完成前不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验和明确授权。
6. 严格使用 Planning with Files：每个小 Phase 开始前重读 `task_plan.md`、`findings.md`、`progress.md`；每个小 Phase 完成后先自我验收，再更新三份规划文件，之后才进入下一小 Phase。
7. 本阶段后续小 Phase 必须按顺序推进：
   - Phase 52A：Memory Contract 固化。
   - Phase 52B：Memory Policy 决策层完备化。
   - Phase 52C：Memory Observability 与审计增强。
   - Phase 52D：Memory Regression 扩展到 20-30 条。
   - Phase 52E：长期记忆治理接口收口，保持 disabled/read-none/write-none/delete-noop。
   - Phase 52F：最终回归、普通文档和 Obsidian 收尾。
8. 每开始一个小 Phase，简短说明本 Phase 解决什么问题、在 Agent/RAG 记忆链路中的位置、为什么现在做。
9. 每完成一个小 Phase，必须运行该 Phase 的最小验收；失败则修复并记录，不能跳过；通过后更新 `task_plan.md`、`findings.md`、`progress.md`。
10. 后续开发重点：保证 `AgentMemoryContext` 是稳定 JSON-native contract；所有 planner/search/answer 记忆使用都通过 `MemoryPolicyDecision`；memory trace 只含脱敏计数、布尔值和枚举；memory summary 永远不是 citation source。
11. 扩展 `scripts/evaluate_phase52_memory.py` 与 `data/evaluation/phase52_memory_regression_cases.csv`，覆盖中英混合、上下文代词、多轮纠错、prior evidence 数量边界、stale anchor、retrieval-only hint、off-topic/refusal boundary。默认 deterministic/dry-run，不调用真实 provider。
12. 长期记忆只做治理接口与禁用态，不写数据库，不生成长期用户画像。未来启用必须依赖显式授权、可删除、可审计、保留期限和最小化存储。
13. 不得把 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk、受限全文或长期用户画像写入 Git、CSV、文档、测试或 Obsidian。
14. 阶段收尾必须运行 focused tests、memory eval、API/SSE focused tests、全量 pytest、Stage 30 和 `git diff --check`。
15. 阶段收尾必须同步 `README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-52.md`，并补齐 Phase 52 续做相关 Obsidian 汇报。

核心链路：

```text
SessionMemory + prior evidence
-> AgentMemoryContext
-> MemoryPolicyDecision
-> planner/search/answer
-> safe latency_trace
-> deterministic memory regression
-> disabled long-term governance
-> final regression and docs
```

完成标准：

- `memory_citation_source_true_count == 0`。
- memory regression pass_rate=1.0000。
- 长期记忆保持 disabled/read-none/write-none/delete-noop。
- `/agent/query`、`/agent/query/stream`、`/chat`、`/quality-report` 不被破坏。
- 全量测试通过，Stage 30 仍为 `91.52 / A / pass`。
- 最终停在人工核验前，未提交、未 tag、未 push、未 PR。

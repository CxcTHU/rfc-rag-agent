# Phase 58 Goal Prompt

阅读 `AGENT.MD` 和相关项目文件，了解项目开发进度。

现在正式进入阶段 58 的开发。请为本线程设置 goal，并持续推进本项目开发，直到阶段 58「成熟 Agent Runtime 层」的规划、开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支建议为：

```text
codex/phase-58-mature-agent-runtime
```

## 背景

阶段 57 已完成默认 `tool_calling_agent` 背后的多通道 hybrid retrieval kernel。人工核验暴露了一个默认链路 runtime 问题：

```text
Turn 1: 大坝的裂缝成因有哪些？请给我详细列出来
Turn 2: 我需要图片支撑
```

默认链路加载了 conversation history，也让 LLM 看到了 history，但 LLM 调用 `search_figures` 时传入的 query 仍是短追问「我需要图片支撑」。由于 `search_figures` 有 visual intent gate，这个短 query 被判为 `visual_intent=false`，工具返回 0 figure results，最后触发 `evidence_insufficient`。

这不是 Redis cache 问题，也不是 history 没加载，而是默认 `tool_calling_agent` 缺少成熟 Runtime 控制层。

## 阶段 58 总目标

把现有 `ToolCallingAgentService` 从「带规则的 tool-calling service」升级为明确的 Agent Runtime：

```text
ToolCallingAgentService
  -> AgentRuntime
      -> RuntimeContextAssembler
      -> TaskContextualizer
      -> LLM tool selection adapter
      -> ToolArgumentGrounder
      -> ToolExecutionController
      -> EvidenceStateManager
      -> LoopController
      -> GuardrailController
      -> FinalAnswerController
      -> RuntimeDiagnostics
  -> AgentToolbox / Workflow Kernels
```

Query rewrite 只是 runtime 的一部分，不是整个阶段目标。

## LLM 引入边界

必要时可以在语义判断层引入 LLM：

- 判断当前轮是否是追问；
- 推断继承 topic；
- 生成 standalone task；
- 提议 tool-specific query rewrite；
- 提议高层 tool selection；
- 基于 runtime-approved evidence 合成最终引用式回答。

Runtime 必须保留最终控制权：

- guardrails；
- allowed tools；
- tool permission；
- tool argument validation；
- loop control；
- duplicate suppression；
- evidence sufficiency；
- cache identity；
- diagnostics schema；
- final refusal gate。

原则：

```text
LLM proposes semantic intent and candidate actions;
Runtime validates, executes, records, and decides control flow.
```

## 执行要求

1. 首先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
2. 运行 `git status -sb` 和 `git log --oneline -5`，确认 Phase 57 后的当前状态。
3. 创建或切换到 `codex/phase-58-mature-agent-runtime`。
4. 严格使用 Planning with Files：每个小 Phase 开始前重读三份规划文件；每个小 Phase 完成后更新 `task_plan.md`、`findings.md`、`progress.md`。
5. 默认链路保持 `tool_calling_agent`，不切换默认 LangGraph/ReAct。
6. 不新增外部数据源、爬虫、PDF、模型权重、写入型 Agent 工具。
7. 不暴露 `search_graph_knowledge` 作为默认并列工具。
8. 不启用广义答案级 Semantic Cache 作为质量方案。
9. 阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验和明确确认。
10. 不得写入真实 `.env`、`.env.prod`、数据库密码、JWT secret、Redis 密码、API key、Bearer token、provider raw response、`raw_response`、`reasoning_content`、hidden thought、完整 answer、完整 chunk、受限全文、私有日志或长期用户画像。

## Phase 顺序

### Phase 58A：启动校准与 runtime 边界审计

- 审计 `ToolCallingAgentService`、Stage 37 loop controls、`AgentToolbox`、Phase 52 memory context、Phase 56 cache diagnostics、Phase 57 retrieval kernel。
- 明确为什么本阶段不是 query rewrite patch，而是 Agent Runtime control plane。

### Phase 58B：规划文件与 runtime 设计

- 更新 `task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage58_mature_agent_runtime_goal_prompt.md` 和 runtime 设计文档。
- 明确哪些层可以使用 LLM，哪些层必须由 Runtime 决策。

### Phase 58C：Runtime state 与 context assembly

- 新增显式 runtime module，包含 `AgentRuntimeState`、`RuntimeContext`、`StandaloneTask`、`EvidenceState`、diagnostics。
- 结构化装配 current query、history、recent topic、follow-up type、inherited topic、standalone task。

### Phase 58D：Tool argument grounding / validation

- 在真实工具执行前统一修复和校验 tool arguments。
- 修复短追问：
  - 「我需要图片支撑」
  - 「给我表格」
  - 「继续详细说」
  - 「上一个问题里的第二点展开」
- `search_figures`、`search_tables` 必须能安全继承 topic。
- 新 topic / off-topic 不得错误继承旧 topic。

### Phase 58E：Execution / Evidence / Loop / Final answer control

- Runtime 记录每次 evidence attempt、tool result count、evidence type、stop reason、final decision。
- 保留 Stage 37 的 one-search-per-iteration、duplicate suppression、safe skipped tool message、citation repair。
- Evidence insufficient 前必须有可解释的 runtime 尝试记录。

### Phase 58F：测试与评估

- 添加 focused tests：
  - context assembly；
  - visual follow-up grounding；
  - table follow-up grounding；
  - detail follow-up grounding；
  - new-topic non-inheritance；
  - duplicate suppression preservation；
  - safe diagnostics。
- 运行 focused tests，必要时运行 Stage 30。

### Phase 58G：文档、Obsidian 与交班

- 更新 README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、阶段报告和本地 Obsidian。
- 停在用户人工核验前。

## 完成标准

- 默认 `tool_calling_agent` 工具面保持稳定。
- Agent Runtime 明确负责 context、task、tool grounding、execution、evidence、loop、guardrail、diagnostics 和 final answer control。
- LLM 只在必要语义层提供 proposal，Runtime 保留控制权。
- 「大坝裂缝成因」后追问「我需要图片支撑」能通过 runtime grounding 调用带继承 topic 的 `search_figures` query。
- diagnostics 能安全显示 standalone task、inherited topic、follow-up type、rewritten tool query、evidence counts、stop reason、final decision。
- focused tests 通过。
- 不泄露 secret、raw provider response、完整 answer、完整 chunk、受限全文或私有日志。
- 最终汇报说明当前分支、主要改动、测试结果、风险、未提交状态和人工核验重点。

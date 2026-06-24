# Phase 52 Goal Prompt

阅读 agent 和其他相关文件，了解项目开发进度。

现在正式进入阶段 52 的开发。请为本线程设置一个 goal：

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及 Phase 51 “性能评测与架构演进对照”的完成状态，持续推进本项目开发，直到阶段 52 “AgentMemoryContext 与短期会话记忆工程化”的开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支建议为：

```text
codex/phase-52-agent-memory-context
```

执行要求：

1. 首先修改当前对话线程名称为：阶段52-AgentMemoryContext与短期会话记忆工程化。
2. 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
3. 确认 Phase 51 已完成并合并到 `main / origin/main`，确认 `phase-51-complete` tag 存在，不要移动任何已有阶段 tag。
4. 从 Phase 51 合并后的 `main` 状态出发，创建或切换到 `codex/phase-52-agent-memory-context` 分支。
5. 开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验和明确确认后，才允许进入提交、tag 和 GitHub 推送流程。
6. 正式开发前，必须根据 AGENT.MD、Phase 51 完成状态和 Phase 52 目标，使用 Planning with Files 编写或校准 `task_plan.md`、`findings.md`、`progress.md`。
7. `task_plan.md` 必须明确 Phase 52 的 Phase 顺序、目标、任务、验证方式、文档收尾要求和完成标准。建议至少包含：启动校准与设计文档、统一短期记忆接口、整合 SessionMemory 与 LangGraph planner、Memory 可观测性与 metadata、Memory 回归评测集与评测脚本、长期记忆接口设计与禁用态实现、回归验证与文档/Obsidian 收尾。
8. `findings.md` 必须记录对 Phase 43 `SessionMemory`、Phase 51 prior evidence、LangGraph checkpoint、planner、answer node、latency trace、API metadata、数据安全边界的理解和关键决策。
9. `progress.md` 必须记录阶段启动、Git/tag/main 状态、每个 Phase 日志、测试结果、遗留风险和“尚未提交，等待用户人工核验”的状态。
10. 严格按 `task_plan.md` 的 Phase 顺序推进，不跳步。每开始一个 Phase，简短说明本 Phase 解决什么问题、在 RAG/Agent 链路中的位置、为什么现在做。
11. 每完成任意 Phase，必须先更新 `task_plan.md`、`findings.md`、`progress.md`；对话中只给简短进度，不输出完整 10 项 Phase 汇报。
12. 开发过程中暂不写入 Obsidian 小 Phase 汇报；阶段 52 全部开发、测试、普通文档完成后，再统一按 `obsidian-vault/模板/Phase 汇报模板.md` 补齐本地 Obsidian 汇报。
13. 阶段 52 收尾时，必须建立或更新 `obsidian-vault/阶段汇报/阶段 52 - AgentMemoryContext 与短期会话记忆工程化/`、阶段 52 Phase 汇报索引、Phase 0 到最终 Phase 小汇报、`obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段/阶段 52 - AgentMemoryContext 与短期会话记忆工程化.md`。
14. 每篇 Obsidian 小 Phase 汇报必须包含：本 Phase 目标、完成的主要任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达。
15. 遇到问题时自行阅读代码、运行测试、定位并修复；新增重要代码必须补测试，阶段收尾运行全量测试。
16. 遇到新词、关键类名、表名、接口名或架构概念，及时用中文解释：是什么、在本项目哪里出现、有什么作用、面试怎么说。
17. 保留用户已有改动，不重置 Git，不覆盖无关文件；不要触碰 reranker 分支或 reranker stash。
18. 阶段 52 不新增外部数据源，不做写入型 Agent 工具，不做长期用户画像，不改变默认 provider，不让真实 API 成为 CI 或本地全量测试前提。
19. 不得把 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk、受限全文或长期用户画像写入 Git、CSV、文档、测试或 Obsidian。

阶段 52 核心链路：

```text
Phase 43 SessionMemory
-> Phase 51 prior evidence
-> AgentMemoryContext
-> LangGraph planner 决策
-> search / answer node
-> memory trace / metadata
-> deterministic memory regression
-> 停在人工核验待提交状态
```

阶段 52 完成标准：

- 新增 `docs/stage52_agent_memory_context.md`，说明目标、输入、记忆类型、planner 决策、trace 字段、长期记忆禁用态、安全边界和完成标准。
- 新增统一短期记忆接口，将 `SessionMemory` 与 prior evidence 合并为 `AgentMemoryContext`。
- LangGraph planner 能基于记忆判断展开追问、新主题追问、stale anchor、证据不足和拒答边界。
- 最终答案引用仍只来自 retrieved/prior evidence sources，memory summary 不得作为引用来源。
- 新增 memory trace / metadata，字段只包含计数、标签和 decision hint。
- 新增 memory regression eval，默认 deterministic/dry-run，不调用真实 provider。
- 长期记忆接口默认 disabled/read-none/write-none。
- 保证 `/agent/query`、`/agent/query/stream`、`/chat`、`/quality-report` 不被破坏。
- 补充阶段 52 相关测试，全量测试通过，Stage 30 仍为 `91.52 / A / pass`。
- 同步 README、AGENT、docs/progress、docs/architecture、docs/data_sources、phase review 和 Obsidian 本地知识库。
- 最终不要本地提交、不要创建 `phase-52-complete` tag、不要推送 GitHub；最终汇报必须说明当前分支、主要改动、测试结果、未提交状态、建议人工核验重点。

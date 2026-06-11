# Task Plan: 阶段 22 - 前端 Agentic 可视化与可观测增强

## Goal

在阶段 21 `phase-21-complete -> 085bff4` 已完成 LangGraph Agentic RAG 的基础上，完成阶段 22「前端 Agentic 可视化与可观测增强」：让原生 HTML/CSS/JS 前端工作台可以 opt-in 调用 `/agent/query` 的 `mode="agentic"`，并可读展示 `workflow_steps`、`iteration_count`、`invalid_citations` 与拒答原因分类。阶段结束时同步普通文档、Obsidian 本地草稿和 `docs/phase_reviews/phase-22.md` 验收报告；用户已明确确认提交、tag、合并和 GitHub 推送。

核心链路：

```text
阶段 21 LangGraph agentic RAG（/agent/query mode="agentic"）
-> 前端 Agent 面板新增 default / agentic 模式切换
-> submitAgent() 传递 mode 参数
-> 响应暴露 workflow_steps / iteration_count / invalid_citations
-> 迭代时间线展示 retrieve -> grade -> rewrite -> re_retrieve -> generate -> citation_check
-> 引用列表标记 invalid_citations
-> 拒答分类展示 responsibility_gate_triggered / evidence_insufficient / off_topic
-> 回归验证 + 浏览器验证
-> 文档同步 + Obsidian + 阶段验收报告
-> 用户确认后提交、tag、merge、push
```

## Baseline And Branch

- 当前工作分支：`codex/phase-22-frontend-agentic-observability`
- 正确基线：`phase-21-complete` tag，指向 `085bff4 Complete phase 21 LangGraph agentic RAG`
- `main` 状态：阶段 21 已按用户要求推送合并到 GitHub，`origin/main -> 085bff4`
- 处理决策：阶段 22 分支从 `phase-21-complete`/`085bff4` 出发；不移动任何已有阶段 tag
- 提交边界：阶段开发完成前不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR

## Boundaries

- 不做写入型 Agent 工具。
- 不做登录系统。
- 不做部署优化。
- 不新增爬虫或外部资料来源。
- 不引入 Node 构建链或前端框架，继续使用原生 HTML/CSS/JS。
- 不让真实 API 成为 CI 或本地全量测试前提。
- HyDE 仍只做离线实验建议，不进入默认链路。
- 不把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- default 模式行为必须保持不变，agentic 只做显式 opt-in。

## Current Phase

Phase 11: complete. 用户已确认提交阶段 22，进入 commit/tag/merge/push 流程。

## Phases

### Phase 0: 启动校准

- [x] 读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- [x] 读取 `docs/stage21_langgraph_agentic_rag.md`、`docs/phase_reviews/phase-21.md`。
- [x] 读取根目录 `task_plan.md`、`findings.md`、`progress.md`。
- [x] 运行 `git status -sb`、`git log --oneline -5`。
- [x] 确认 `phase-21-complete -> 085bff4`，不移动 tag。
- [x] 核对 `main` 是否包含阶段 21。
- [x] 从 `phase-21-complete` 创建 `codex/phase-22-frontend-agentic-observability`。
- [x] 校准 `task_plan.md`、`findings.md`、`progress.md`。
- 验证方式：Git 命令输出、分支名、planning 文件落盘。
- Status: complete

### Phase 1: 阶段 22 设计文档

- [x] 新增 `docs/stage22_frontend_agentic_observability.md`。
- [x] 说明目标、输入、响应契约、前端交互、时间线字段、拒答分类、引用无效标记、测试方案、安全边界和完成标准。
- [x] 明确 `default` 模式不变，`agentic` 模式 opt-in。
- 验证方式：文档存在，并被测试或人工 grep 覆盖关键字段。
- Status: complete

### Phase 2: Agentic 响应契约校准

- [x] 扩展 `AgentQueryResponse`，为前端暴露 `mode`、`iteration_count`、`invalid_citations`、`workflow_steps`、`refusal_category` 等只读观测字段。
- [x] default 模式返回兼容默认值，不改变既有必填字段语义。
- [x] agentic 模式从 `AgenticResult` 映射 dedicated observability 字段，同时保留原 `tool_calls` 显示兼容。
- [x] 明确拒答分类：`responsibility_gate_triggered`、`evidence_insufficient`、`off_topic`。
- 验证方式：新增/更新 API schema 与 `/agent/query` 测试。
- Status: complete

### Phase 3: Agentic 模式前端接入

- [x] 在 `app/frontend/index.html` 的 Agent 面板加入 default / agentic 模式切换控件。
- [x] `submitAgent()` 读取模式，并在 agentic 模式传递 `mode: "agentic"`。
- [x] default 模式不传或传默认 mode，保持现有 API 行为。
- 验证方式：前端静态测试断言控件存在，JS 中包含 mode 传参逻辑。
- Status: complete

### Phase 4: 迭代过程可视化

- [x] 在 Agent 结果区域展示 `iteration_count`。
- [x] 在工具/步骤侧栏用时间线或步骤列表展示 `workflow_steps`。
- [x] 每步显示节点名、输入摘要、输出摘要、成功/失败与错误摘要。
- [x] 节点顺序覆盖 retrieve、grade、rewrite、re_retrieve、generate、citation_check。
- 验证方式：前端渲染函数测试或静态断言，API 测试确认字段返回。
- Status: complete

### Phase 5: 引用与拒答增强展示

- [x] `invalid_citations` 非空时，在引用 badge 或来源列表中标记无效引用。
- [x] 拒答时展示拒答分类：`responsibility_gate_triggered`、`evidence_insufficient`、`off_topic`。
- [x] 保留现有 `refused` 和 `refusal_reason` 文案，不破坏旧模式。
- 验证方式：新增前端相关断言、API agentic refusal 场景测试。
- Status: complete

### Phase 6: 聚焦测试

- [x] 补充前端静态测试，覆盖模式控件、mode 传参、workflow UI、invalid citation UI、refusal category UI。
- [x] 补充 API 测试，覆盖 agentic 响应字段与 default 兼容。
- [x] 运行聚焦测试：`tests/test_frontend_app.py`、`tests/test_agent_api.py`、`tests/test_agentic_graph.py`、`tests/test_stage21_agentic_eval.py`。
- 验证方式：聚焦测试通过。
- Status: complete

### Phase 7: 回归验证与浏览器验证

- [x] 确认 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 未破坏。
- [x] 运行全量测试，目标 `>= 449 existing + new`。
- [x] 启动本地服务并进行前端浏览器验证，检查 desktop/mobile 视口与控制台错误。
- 验证方式：全量 `pytest -q` 通过，浏览器截图/检查通过。
- Status: complete

### Phase 8: 普通文档同步

- [x] 更新 `README.md`。
- [x] 更新 `docs/progress.md`。
- [x] 更新 `docs/architecture.md`。
- [x] 更新 `docs/data_sources.md`。
- [x] 判断并更新 `AGENT.MD`，记录阶段 22 经验与后续规则。
- 验证方式：文档反映阶段 22 状态、边界、测试和人工核验前状态。
- Status: complete

### Phase 9: Obsidian 收尾

- [x] 建立/更新 `obsidian-vault/阶段汇报/阶段 22 - 前端 Agentic 可视化与可观测增强/`。
- [x] 按 `obsidian-vault/模板/Phase 汇报模板.md` 补齐 Phase 0 到最终 Phase 小汇报。
- [x] 每篇小汇报包含：本 Phase 目标、完成的主要任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达。
- [x] 更新阶段 22 Phase 汇报索引、`obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`、`obsidian-vault/阶段/阶段 22 - 前端 Agentic 可视化与可观测增强.md`。
- 验证方式：本地 Obsidian 文件存在，且不进入 Git 提交范围。
- Status: complete

### Phase 10: 阶段验收报告

- [x] 新增 `docs/phase_reviews/phase-22.md`。
- [x] 写入验收结论、范围核对、测试证据、API 兼容、安全合规、文档同步、提交边界和遗留观察。
- 验证方式：验收报告存在，内容覆盖阶段 22 完成标准。
- Status: complete

### Phase 11: 人工核验待提交状态

- [x] 运行 `git status -sb`。
- [x] 确认未执行 `git add`、未 commit、未 tag、未 push、未 PR。
- [x] 最终汇报当前分支、主要改动、测试结果、未提交状态、人工核验重点和后续提交/tag建议。
- 验证方式：无 staged 变更；最终停在用户人工核验前。
- Status: complete

## Completion Criteria

| Item | Expected |
|---|---|
| Design doc | `docs/stage22_frontend_agentic_observability.md` |
| Branch | `codex/phase-22-frontend-agentic-observability` |
| Baseline | `phase-21-complete -> 085bff4` |
| Main check | `origin/main` contains `phase-21-complete -> 085bff4`; branch starts from phase 21 baseline |
| Frontend mode switch | Agent panel has default / agentic switch |
| API request | `submitAgent()` sends `mode="agentic"` only when selected |
| Workflow display | `workflow_steps` shown as steps/timeline with node, input summary, output summary |
| Iteration display | `iteration_count` visible in Agent result |
| Invalid citations | `invalid_citations` marked in citations/source UI |
| Refusal category | responsibility / evidence insufficient / off-topic visible when refused |
| Default mode | Existing Agent behavior unchanged |
| API compatibility | search/vector/hybrid/chat/agent/query/quality-report preserved |
| Tests | Full suite passes, at least 449 existing + new tests |
| Docs | README, docs/progress, docs/architecture, docs/data_sources, AGENT.MD synced |
| Obsidian | Local stage 22 reports and indexes updated |
| Review report | `docs/phase_reviews/phase-22.md` |
| Final state | no add, no commit, no phase-22 tag, no push, no PR |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| Agentic RAG | 带自我修正循环的 RAG：先检索，再评估证据，不足时改写问题重检索，最后生成并检查引用。 |
| `mode="agentic"` | `/agent/query` 的可选模式参数；只有显式传入时才走阶段 21 LangGraph 图。 |
| `workflow_steps` | Agentic RAG 每个节点的可观测记录，包含节点名、输入摘要、输出摘要、成功状态和错误摘要。 |
| `iteration_count` | agentic 检索-评估-改写循环执行了几轮，用来解释系统是否多次重试。 |
| `invalid_citations` | 答案里出现但未能对应到本次来源列表的引用编号，用来提醒用户该引用不可靠。 |
| 拒答分类 | 把 `refused=true` 的原因分成工程责任边界、证据不足、离题等类型，便于用户理解系统为什么拒答。 |

## Notes

- 本文件由 Planning with Files 维护；每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 开发过程中暂不写 Obsidian 小 Phase 汇报；待开发、测试和普通文档完成后统一补齐。
- 阶段 22 完成后必须停在人工核验前，不提交、不打 tag、不推送。

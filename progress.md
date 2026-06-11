# Progress Log（阶段 22）

## Session: 2026-06-11

### Goal / Thread Setup

- 已将线程标题修改为：阶段22-前端Agentic可视化与可观测增强。
- 已创建线程 goal：持续推进阶段 22，直到开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。
- 目标分支：`codex/phase-22-frontend-agentic-observability`。
- 提交边界：阶段完成前不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。

### Startup Reading

已按入口规则读取/核对：

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage21_langgraph_agentic_rag.md`
- `docs/phase_reviews/phase-21.md`
- `task_plan.md`
- `findings.md`
- `progress.md`

已额外读取阶段 22 开发所需现状：

- `app/frontend/index.html`
- `app/frontend/static/app.js`
- `app/frontend/static/styles.css`
- `app/frontend/quality_report.html`
- `app/schemas/agent.py`
- `app/api/agent.py`
- `app/services/agentic/state.py`
- `tests/test_frontend_app.py`
- `tests/test_agent_api.py`
- `tests/test_agentic_graph.py`
- `tests/test_stage21_agentic_eval.py`

### Git / Tag / Main Status

```text
git status -sb
## claude/phase-21-langgraph-agentic-rag...origin/claude/phase-21-langgraph-agentic-rag

git log --oneline -5
085bff4 Complete phase 21 LangGraph agentic RAG
edfe9ff docs: reference goal prompt template path in AGENT.MD
39c06e3 docs: add phase 20 review report and per-phase acceptance review rule
8333d71 Merge phase 20 default chain and eval upgrade
706047d Complete phase 20 default chain and eval upgrade

git rev-parse --short phase-21-complete
085bff4

git show -s --format='%h %s' phase-21-complete
085bff4 Complete phase 21 LangGraph agentic RAG

git merge-base --is-ancestor phase-21-complete main
phase-21-complete is NOT ancestor of main

git log --oneline -5 main
edfe9ff docs: reference goal prompt template path in AGENT.MD
39c06e3 docs: add phase 20 review report and per-phase acceptance review rule
8333d71 Merge phase 20 default chain and eval upgrade
706047d Complete phase 20 default chain and eval upgrade
12184d7 Merge phase 19 chinese analysis and retrieval tuning
```

初始结论：

- 阶段 21 已完成，`phase-21-complete` 正确指向 `085bff4`。
- `main` 尚未包含阶段 21，仍在阶段 20 合并点之后的文档提交附近。
- 按用户规则，本阶段不移动 `main`，不移动已有 tag，直接从 `phase-21-complete` 出发。

阶段 21 merge 后更新：

```text
git ls-remote origin refs/heads/main refs/tags/phase-21-complete
085bff44898385924f766046fd3c0e5df2e322ca refs/heads/main
085bff44898385924f766046fd3c0e5df2e322ca refs/tags/phase-21-complete
```

- 用户随后要求提交阶段 21 整体开发并上传 merge 至 GitHub。
- 已完成阶段 21 全量测试：`449 passed in 35.03s`。
- 已将 `main` 推送到 GitHub，`origin/main` 当前与 `phase-21-complete` 均指向 `085bff4`。
- 阶段 22 当前仍从相同的阶段 21 基线继续，不移动已有 tag。

Branch creation:

```text
git switch -c codex/phase-22-frontend-agentic-observability phase-21-complete
Switched to a new branch 'codex/phase-22-frontend-agentic-observability'
```

当前分支：

```text
## codex/phase-22-frontend-agentic-observability
```

### Planning With Files

- 已使用 Planning with Files 工作方式重写/校准：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- `task_plan.md` 已明确阶段 22 Phase 顺序、目标、任务、验证方式、文档收尾要求和完成标准。
- `findings.md` 已记录前端现状、Agent 面板、`submitAgent()`、`mode="agentic"`、`AgenticResult` 字段和 `quality_report.html` 理解。
- `progress.md` 已记录阶段启动、Git/tag/main 状态、Phase 日志、错误和待提交边界。

### Errors / Non-Blocking Notes

| Issue | Attempt | Resolution |
|---|---|---|
| Planning catch-up 脚本首次 PowerShell 调用写法不兼容 | `& (Get-Command python).Source ...` | 改用变量方式重跑 |
| 当前 PATH 未找到 `python` | `.codex` catch-up 脚本存在，但命令输出 `python not found` | 非阻断；后续测试优先使用项目虚拟环境或工作区 Python |

## Phase 0: 启动校准

- Status: complete
- 本 Phase 解决什么问题：确认阶段 22 从正确基线出发，避免在 `main` 未合并阶段 21 时从错误代码继续。
- 在 RAG 链路中的位置：这是开发前的工程入口校准，不改变检索、问答或 Agent 逻辑。
- 为什么现在做：阶段 22 依赖阶段 21 的 agentic 字段和 `/agent/query mode="agentic"`，必须先确认代码基线包含这些能力。

完成内容：

- 线程改名与 goal 创建完成。
- 入口文件和阶段 21 文档阅读完成。
- `phase-21-complete -> 085bff4` 已确认。
- `main` 未包含阶段 21已记录。
- 已从 `phase-21-complete` 创建阶段 22 分支。
- 已校准三份 Planning with Files 文件。

验证结果：

- Git/tag/main 命令输出已记录。
- 当前分支为 `codex/phase-22-frontend-agentic-observability`。
- 尚未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

遗留风险：

- `main` 尚未合并阶段 21。本阶段选择从 tag 出发是正确基线处理，但最终人工核验时应特别注意后续合并顺序。
- PATH 暂无 `python`，测试阶段需要定位项目虚拟环境或可用 Python。

下一 Phase：

- Phase 1：新增 `docs/stage22_frontend_agentic_observability.md` 设计文档。

## Phase 1: 阶段 22 设计文档

- Status: complete
- 本 Phase 解决什么问题：先把前端要展示的 agentic 状态、后端要返回的字段、测试边界和安全边界固定下来。
- 在 RAG 链路中的位置：不改变检索或生成，只定义阶段 21 agentic 图的可观测结果如何进入前端。
- 为什么现在做：后续改 API 和前端前，先用文档约束 default 模式不变、agentic opt-in、无真实 API 测试前提。

完成内容：

- 新增 `docs/stage22_frontend_agentic_observability.md`。
- 设计文档覆盖：目标、背景、范围、响应契约、拒答分类、前端交互、节点展示、测试方案、安全边界、完成标准和面试表达。
- 同步修正 planning 文件中关于 `main` 的旧状态：阶段 21 已推送到 `origin/main`。

验证结果：

- 文档已落盘。
- `task_plan.md` 已将 Phase 1 标为 complete。
- 尚未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

下一 Phase：

- Phase 2：Agentic 响应契约校准。

## Phase 2: Agentic 响应契约校准

- Status: complete
- 本 Phase 解决什么问题：把阶段 21 agentic 图的内部结果稳定暴露为 `/agent/query` 响应字段，让前端后续可以直接读取而不是猜测 `tool_calls`。
- 在 RAG 链路中的位置：位于 LangGraph agentic RAG 运行完成之后、前端展示之前，是后端到前端的只读观测契约。
- 为什么现在做：前端模式切换和时间线 UI 依赖这些字段，必须先保证 API 返回结构稳定。

完成内容：

- 扩展 `AgentQueryResponse`，新增 `mode`、`workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category`。
- 增加 `AgentWorkflowStepItem`，用节点名、输入摘要、输出摘要、成功状态和错误摘要表达时间线步骤。
- `AgentQueryRequest.mode` 增加合法值校验，支持 `default`、`agentic` 和空值。
- `AgenticResult` 带出 `responsibility_gate_triggered`，用于稳定计算拒答分类。
- agentic 图步骤记录名对齐 `retrieve`、`grade`、`rewrite`、`re_retrieve`、`generate`、`citation_check`。
- agentic 响应同时保留旧 `tool_calls` 映射，default 模式新增字段使用兼容默认值。
- API 测试覆盖 default 兼容、agentic observability 字段和 responsibility gate 拒答分类。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_agent_api.py tests\test_agentic_graph.py -q
27 passed in 4.32s
```

遗留风险：

- 当前只完成后端契约，前端尚未接入 `mode="agentic"` 或展示 `workflow_steps`。
- `workflow_steps` 的节点显示名已经统一，但还需要浏览器验证前端布局是否适合长摘要。

下一 Phase：

- Phase 3：Agentic 模式前端接入。

## Phase 3: Agentic 模式前端接入

- Status: complete
- 本 Phase 解决什么问题：给用户一个显式入口选择是否启用阶段 21 的 agentic 链路，并把该选择传给 `/agent/query`。
- 在 RAG 链路中的位置：位于用户提交 Agent 任务时，决定后端走 default AgentService 还是 LangGraph Agentic RAG。
- 为什么现在做：Phase 2 已经提供响应契约，前端必须先能触发 `mode="agentic"`，后续 workflow UI 才有真实数据可展示。

完成内容：

- Agent 面板新增 `data-agent-mode` 下拉框，默认 `default`，可选 `agentic`。
- `submitAgent()` 读取模式，只在 agentic 模式写入 `body.mode = "agentic"`。
- Agent 控制区 CSS 扩展为 5 列，并统一 label 样式。
- 前端静态测试覆盖模式控件和 JS opt-in 传参逻辑。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed in 0.74s
```

遗留风险：

- 当前只是接入 agentic 请求入口，结果区还未展示 `workflow_steps`、`iteration_count`、`invalid_citations` 或拒答分类。

下一 Phase：

- Phase 4：迭代过程可视化。

## Phase 4: 迭代过程可视化

- Status: complete
- 本 Phase 解决什么问题：让 agentic RAG 的内部执行步骤以时间线/步骤列表显示出来，避免用户只能看到最终答案。
- 在 RAG 链路中的位置：位于后端生成 `workflow_steps` 之后、前端 Agent 右侧面板展示阶段。
- 为什么现在做：Phase 3 已经能触发 agentic 请求，现在需要把 Phase 2 契约中的 `workflow_steps` 和 `iteration_count` 真正显示给用户。

完成内容：

- 新增 `renderAgentWorkflowSteps()`，展示步骤序号、节点名、输入摘要、输出摘要、成功/失败状态和错误摘要。
- `submitAgent()` 在 `workflow_steps` 非空时优先展示 workflow，否则保留旧的 `tool_calls` 展示。
- `renderAgentAnswer()` 展示 `mode` 与 `iterations` badge。
- 新增 workflow 步骤 CSS，保持原生工作台布局，不引入框架。
- 前端静态测试覆盖 `renderAgentWorkflowSteps`、`workflow_steps` 和 `iteration_count`。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed in 1.01s
```

遗留风险：

- 尚未展示 `invalid_citations` 与 `refusal_category`。
- 长输入/输出摘要的真实浏览器布局仍需在 Phase 7 做桌面与移动视口检查。

下一 Phase：

- Phase 5：引用与拒答增强展示。

## Phase 5: 引用与拒答增强展示

- Status: complete
- 本 Phase 解决什么问题：让用户看到哪些 citation 被 citation_check 判为无效，以及拒答属于责任边界、证据不足还是离题。
- 在 RAG 链路中的位置：位于答案生成和引用检查之后，是最终结果解释层。
- 为什么现在做：Phase 4 已经展示执行步骤，本 Phase 补齐关键异常状态，避免用户只看到“拒答”或一组未解释的引用编号。

完成内容：

- `renderAgentAnswer()` 对 `invalid_citations` 命中的引用 badge 标记“无效”。
- 对不在 `citations` 中但出现在 `invalid_citations` 的编号单独展示无效引用 badge。
- 新增 `formatRefusalCategory()`，把拒答分类映射成中文标签并保留原始枚举值。
- 拒答块展示 `refusal_category`，同时保留原有 `refusal_reason`。
- 新增无效引用和拒答分类样式。
- 前端和 API 测试覆盖新增展示字段与责任边界分类。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_agent_api.py -q
14 passed in 2.20s
```

遗留风险：

- 目前仍是静态和 API 层验证，真实浏览器交互待 Phase 7。

下一 Phase：

- Phase 6：聚焦测试。

## Phase 6: 聚焦测试

- Status: complete
- 本 Phase 解决什么问题：把阶段 22 直接相关的前端、API、agentic 图和阶段 21 兼容测试集中跑一遍，避免局部改动带来直接回归。
- 在 RAG 链路中的位置：这是开发验证环节，覆盖从前端入口到 `/agent/query` 再到 LangGraph agentic RAG 的主要接口。
- 为什么现在做：Phase 3-5 的代码改动已完成，进入全量回归和浏览器验证前，需要先确认核心路径稳定。

完成内容：

- 前端静态测试覆盖模式控件、mode 传参、workflow UI、invalid citation UI、refusal category UI。
- API 测试覆盖 default 兼容字段、agentic observability 字段和责任边界拒答分类。
- agentic 图测试覆盖节点、迭代上限、拒答和引用检查。
- 阶段 21 测试继续通过，说明 `mode` 和 LangGraph 模块结构兼容。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_agent_api.py tests\test_agentic_graph.py tests\test_stage21_agentic_eval.py -q
39 passed in 4.42s
```

遗留风险：

- 尚未运行全量测试。
- 尚未做真实浏览器 desktop/mobile 验证。

下一 Phase：

- Phase 7：回归验证与浏览器验证。

## Phase 7: 回归验证与浏览器验证

- Status: complete
- 本 Phase 解决什么问题：确认阶段 22 改动没有破坏既有 API、质量报告和前端页面，并在真实浏览器视口中检查 UI。
- 在 RAG 链路中的位置：这是全链路回归验证，覆盖从前端静态页面、Agent API 到检索/问答/质量报告入口。
- 为什么现在做：代码开发和聚焦测试已完成，进入文档收尾前必须先确认功能面稳定。

完成内容：

- 运行全量 `pytest -q`。
- 启动本地 FastAPI 服务：`http://127.0.0.1:8000/`，最终核验时端口 8000 仍处于监听状态。
- 用内置浏览器检查桌面页面：Agent 模式控件存在、默认 `default`、可选 `agentic`、Agent 问题框/按钮/步骤面板存在、无水平溢出、console error 为空。
- 用浏览器实际切换下拉框到 `agentic`，选中值正确。
- 用 390x844 移动视口检查：Agent 控制区单列、模式控件和运行按钮可见、无水平溢出、console error 为空。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest -q
451 passed in 44.61s
```

浏览器检查结果：

```text
desktop: mode control=true, default=default, agentic option=true, horizontalOverflow=false, console errors=0
mobile 390x844: agentControlsColumns=321.333px, horizontalOverflow=false, modeVisible=true, buttonVisible=true, console errors=0
```

Errors / Non-Blocking Notes：

- 浏览器插件不支持 `networkidle` 等待状态；已改用 `domcontentloaded` 完成验证。
- 浏览器截图捕获命令超时；DOM、布局、交互和 console error 检查均通过，因此不影响本 Phase 验证结论。

遗留风险：

- 尚未同步普通文档、Obsidian 和阶段验收报告。

下一 Phase：

- Phase 8：普通文档同步。

## Phase 8: 普通文档同步

- Status: complete
- 本 Phase 解决什么问题：把阶段 22 的实现、验证、边界和人工核验前状态同步到项目普通文档，避免代码和说明脱节。
- 在 RAG 链路中的位置：这是工程文档收尾，不改变检索、生成或前端运行逻辑。
- 为什么现在做：全量测试和浏览器验证已经通过，进入 Obsidian 与验收报告前应先让仓库内文档反映真实状态。

完成内容：

- `README.md` 更新当前阶段、阶段 22 要点、阶段 21 合并状态和测试数量。
- `docs/progress.md` 新增阶段 22 最新状态，记录完成内容、验证结果、遗留风险、下一阶段任务和面试表达。
- `docs/architecture.md` 新增阶段 22 Agentic 前端可观测架构和响应契约兼容策略。
- `docs/data_sources.md` 说明阶段 22 不新增资料来源、不写入敏感数据、不改变 source registry 边界。
- `AGENT.MD` 补充分支路线和阶段 22 之后的前端 Agentic 协作规则。
- `docs/stage22_frontend_agentic_observability.md` 补充实现后的节点展示和验证状态。

验证结果：

- 文档已落盘；变更集中在入口和说明文件。
- 尚未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

遗留风险：

- Obsidian 本地知识库和阶段验收报告尚未补齐。

下一 Phase：

- Phase 9：Obsidian 收尾。

## Phase 9: Obsidian 收尾

- Status: complete
- 本 Phase 解决什么问题：把阶段 22 的小 Phase 过程、关键决策、验证结果和面试表达沉淀到本地 Obsidian 知识库。
- 在 RAG 链路中的位置：这是本地知识库收尾，不改变代码或运行链路。
- 为什么现在做：普通文档已同步，进入验收报告前先补齐本地复盘资料，方便用户人工核验和后续面试复习。

完成内容：

- 新增阶段页：`obsidian-vault/阶段/阶段 22 - 前端 Agentic 可视化与可观测增强.md`。
- 新增阶段汇报目录：`obsidian-vault/阶段汇报/阶段 22 - 前端 Agentic 可视化与可观测增强/`。
- 新增阶段 22 Phase 汇报索引。
- 新增 Phase 0-11 共 12 篇小 Phase 汇报，每篇包含固定 10 项。
- 更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`。
- 阶段 21 在 Obsidian 中改为已合并，阶段 22 改为待人工核验。

验证结果：

```text
阶段 22 Obsidian 目录文件数：13
内容：Phase 汇报索引 + Phase 0-11 小汇报
```

遗留风险：

- Phase 10/11 的 Obsidian 汇报目前是草稿，待对应 Phase 完成后复核为最终状态。
- Obsidian 为本地 only，不进入 Git 提交范围。

下一 Phase：

- Phase 10：阶段验收报告。

## Phase 10: 阶段验收报告

- Status: complete
- 本 Phase 解决什么问题：形成阶段 22 的可审计验收证据，说明范围、测试、安全、文档和提交边界均已核对。
- 在 RAG 链路中的位置：这是阶段验收闭环，不改变运行链路。
- 为什么现在做：开发、测试、浏览器验证、普通文档和 Obsidian 已完成，需要在人工核验前给出正式验收报告。

完成内容：

- 新增 `docs/phase_reviews/phase-22.md`。
- 验收报告结论为 PASS（待用户人工核验）。
- 报告覆盖范围核对、关键实现、测试证据、浏览器验证、API 兼容、安全合规、文档与 Obsidian、提交边界、遗留观察和人工核验建议。
- 新增 `obsidian-vault/验收报告/阶段 22 验收报告.md`，更新 `obsidian-vault/验收报告/验收报告索引.md`。
- Phase 10 Obsidian 小汇报已从草稿更新为完成状态。

验证结果：

- `docs/phase_reviews/phase-22.md` 已落盘。
- 尚未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

遗留风险：

- 还需最终运行 `git status -sb` 并更新 Phase 11 待提交状态。

下一 Phase：

- Phase 11：人工核验待提交状态。

## Phase 11: 人工核验待提交状态

- Status: complete
- 本 Phase 解决什么问题：确认阶段 22 结束时停在用户人工核验前，没有提前提交、tag、push 或创建 PR。
- 在 RAG 链路中的位置：这是交付边界核验，不改变代码或运行链路。
- 为什么现在做：所有开发、测试、普通文档、Obsidian 和验收报告已完成，必须按用户要求停在人工核验前。

完成内容：

- 运行 `git status -sb`。
- 运行 `git diff --cached --stat`，确认无 staged 变更。
- 运行 `git tag -l phase-22-complete`，确认未创建阶段 22 tag。
- 运行 `git branch --show-current`，确认仍在目标分支。
- 运行 `git log --oneline -3`，确认最近提交仍是阶段 21 完成提交。
- Phase 11 Obsidian 草稿复核为完成状态。

验证结果：

```text
git branch --show-current
codex/phase-22-frontend-agentic-observability

git diff --cached --stat
# no output

git tag -l phase-22-complete
# no output

git log --oneline -3
085bff4 Complete phase 21 LangGraph agentic RAG
edfe9ff docs: reference goal prompt template path in AGENT.MD
39c06e3 docs: add phase 20 review report and per-phase acceptance review rule
```

`git status -sb` 当前显示阶段 22 的工作区改动和新增文档，均未 staged；Obsidian 文件未进入 Git 状态。

遗留风险：

- 阶段 22 已获用户明确确认进入提交、tag、合并和 GitHub 推送流程；执行过程中仍不得移动已有阶段 tag。

下一步：

- 提交阶段 22、创建 `phase-22-complete` tag、合并到 `main` 并 push。

## Current State

- 当前分支：`codex/phase-22-frontend-agentic-observability`
- 当前 Phase：Phase 11 complete，用户已确认提交阶段 22
- 最新全量测试：`451 passed in 31.12s`
- 下一步：提交阶段 22、创建 `phase-22-complete` tag、合并到 `main` 并推送 GitHub
- PR：不创建

## Submission Authorization: 2026-06-11

- 用户明确要求：阅读 agent，根据要求，提交阶段 22 的整体开发工作，并上传 merge 至 GitHub。
- 已重新阅读 `AGENT.MD` 与关键状态文件。
- 已再次运行全量测试：`451 passed in 31.12s`。
- 本次授权解除阶段 22 之前的“人工核验前不得提交/tag/push”边界，允许进入 `git add`、`git commit`、`git tag`、`git push` 与 `main` 合并流程。

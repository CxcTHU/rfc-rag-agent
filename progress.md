# 阶段 23 进度日志：Agentic 评测闭环与自动模式路由

## 当前状态

- 当前阶段：阶段 23「Agentic 评测闭环与自动模式路由」。
- 当前分支：`codex/phase-23-agentic-eval-and-auto-routing`。
- 当前基线提交：`1a5bf0c Complete phase 22 frontend agentic observability`。
- Git/tag 状态：`phase-22-complete`、`main`、`origin/main` 已确认均指向阶段 22 最终提交 `1a5bf0cde5f8b8e76ff1dafa6225fc7fa9f82cfd`。
- 阶段 23 状态：已完成核心开发、评测、回归验证、普通文档、验收报告和 Obsidian 草稿收尾；用户已确认进入提交、tag、合并和 GitHub 推送流程。
- 提交状态：尚未 `git add`、尚未提交、尚未创建 `phase-23-complete` tag、尚未推送，等待阶段完成后的用户人工核验。

## Phase 0：启动校准与文件计划

**时间**：2026-06-11

**本 Phase 解决什么问题**

确认阶段 22 已完成并合并到 `main`，以阶段 22 最终功能提交作为阶段 23 的正确起点。

**RAG 链路位置**

项目协作和基线确认层，不改检索、问答或 agentic 运行链路。

**为什么现在做**

阶段 23 的自动路由依赖阶段 21 的 LangGraph agentic RAG 和阶段 22 的前端可观测字段，错误起点会导致评测结论和代码行为错位。

**已完成**

- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读 `docs/stage22_frontend_agentic_observability.md`、`docs/phase_reviews/phase-22.md`。
- 阅读 `docs/stage21_langgraph_agentic_rag.md`、`docs/phase_reviews/phase-21.md`。
- 阅读上一阶段遗留的 `task_plan.md`、`findings.md`、`progress.md`。
- 确认 `phase-22-complete` 指向 `1a5bf0c Complete phase 22 frontend agentic observability`。
- 确认 `phase-22-complete` 已并入 `main`，且 `main` 未停留在阶段 21 合并点。
- 从阶段 22 合并后的 `main` 创建阶段 23 分支 `codex/phase-23-agentic-eval-and-auto-routing`。
- 按 Planning with Files 将根目录 `task_plan.md`、`findings.md`、`progress.md` 校准为阶段 23。

**已运行验证**

- `git status -sb`
- `git log --oneline -5`
- `git show -s --format="%H%n%h %D%n%s" phase-22-complete`
- `git show -s --format="%H%n%h %D%n%s" main`
- `git merge-base --is-ancestor phase-22-complete main`

**验证结论**

- 阶段 22 已完成并合并到 `main`。
- `phase-22-complete` tag 不需要也不会移动。
- 当前阶段 23 分支从正确的 `main` 起点创建。

## Phase 1：阶段 23 设计文档

**状态**：已完成

**本 Phase 解决什么问题**

把阶段 23 的评测修复、自动路由、API 行为、前端改造、安全边界和完成标准写成可审查合同。

**RAG 链路位置**

横跨离线评测、`/agent/query` 入口、default AgentService、agentic LangGraph 和前端 Agent 面板。

**为什么现在做**

阶段 23 要改变用户入口默认行为，必须先把“何时自动走 agentic、何时保留 default、如何证明可靠”说清楚。

**已完成**

- 新增 `docs/stage23_agentic_eval_and_auto_routing.md`。
- 固化评测修复/隔离方案、agentic vs default 对照结论标准、自动路由规则、API 行为、前端只读指示器和安全边界。

**验证结论**

- 设计文档覆盖阶段 23 的主要验收项。
- 最终评测结论将在阶段 23 评测和回归完成后回填同步。

## Phase 2：Agentic 评测修复与可靠对照设计

**状态**：已完成

**本 Phase 解决什么问题**

阶段 21 agentic 对照被 SSL/超时污染，阶段 23 需要先把真实 provider 不稳定性隔离掉，得到可复跑的低错误率证据。

**RAG 链路位置**

离线评测层，对比 default `AgentService` 与 agentic LangGraph，不改变运行时入口。

**为什么现在做**

没有稳定对照，就不能放心把 agentic 接到 `/agent/query` 的自动分流。

**已完成**

- 隔离阶段 21 SSL/超时问题。
- 输出 error_rate < 0.10 的可靠阶段 23 对照评测。
- 新增 `scripts/evaluate_stage23_agentic_auto_routing.py`。
- 新增 `tests/test_stage23_agentic_eval.py`。
- 评测默认使用 deterministic provider 和 in-memory SQLite fixture，不依赖真实 API。

**当前结论**

- 阶段 21 的 `inconclusive_high_error_rate` 保留为历史结果。
- 阶段 23 新评测通过 deterministic fixture 隔离真实 provider 的 SSL 问题。
- 当前 fixture 中 agentic 的明确收益集中在复杂“Search and compare”任务：default `detect_intent` 会走 search-only，agentic 会生成 answer-like 响应；其他多证据题暂按 parity 记录。

**已运行验证**

```text
.\.venv\Scripts\python.exe scripts\evaluate_stage23_agentic_auto_routing.py

default: errors=0 error_rate=0.000 answer_like=2
agentic: errors=0 error_rate=0.000 answer_like=3 gains=1
decision: reliable_auto_route_candidate
```

```text
.\.venv\Scripts\python.exe -m pytest tests\test_stage23_agentic_eval.py -q
3 passed in 0.51s
```

## Phase 3：问题复杂度路由规则

**状态**：已完成

**本 Phase 解决什么问题**

建立规则式问题复杂度判断，让 `/agent/query` 能在用户不传 `mode` 时决定走 default 还是 agentic。

**RAG 链路位置**

API 入口前置路由层，位于 default `AgentService` 与 agentic LangGraph 之前。

**为什么现在做**

Phase 2 已经得到稳定对照结果，现在需要把“哪些问题值得 agentic”落成无外部依赖的可测试函数。

**已完成**

- 实现 `classify_query_complexity`。
- 覆盖 simple/complex 和判断依据。
- 新增 `app/services/agent/routing.py`。
- 新增 `tests/test_agent_routing.py`。
- 路由规则覆盖长度、子句、对比、流程、多方面、跨证据/改写、search+analysis 组合。
- 修正普通 “What affects ...?” 概念题误判边界，避免简单题过度进入 agentic。

**已运行验证**

```text
.\.venv\Scripts\python.exe -m pytest tests\test_agent_routing.py -q
6 passed in 0.03s
```

## Phase 4：`/agent/query` 自动分流集成

**状态**：已完成

**本 Phase 解决什么问题**

让 `/agent/query` 在用户不传 `mode` 时自动选择 default 或 agentic，同时保留显式 mode 调试能力。

**RAG 链路位置**

FastAPI `/agent/query` 分支点，向下分别进入 default `AgentService.query()` 或 agentic `run_agentic_rag()`。

**为什么现在做**

复杂度路由函数已经通过测试，下一步就是把它接到真实 API 入口。

**已完成**

- 未传 `mode` 时自动分流。
- 显式 `mode` 继续覆盖自动判断。
- 保持 `detect_intent` 内部逻辑不变。
- 修改 `app/api/agent.py`，新增 `effective_mode`。
- 新增 API 测试覆盖自动 agentic、显式 default 覆盖、显式 agentic 覆盖。

**已运行验证**

```text
.\.venv\Scripts\python.exe -m pytest tests\test_agent_routing.py tests\test_agent_api.py -q
17 passed in 2.51s
```

## Phase 5：前端只读模式指示器

**状态**：已完成

**本 Phase 解决什么问题**

把阶段 22 的用户手动 mode 下拉框改为阶段 23 的系统自动路由只读显示。

**RAG 链路位置**

前端 Agent 面板：请求前不再发送 `mode`，请求后展示 `/agent/query` 响应中的实际 `mode`。

**为什么现在做**

API 已经支持自动分流，前端应降低用户认知负担，把模式选择变成结果观测。

**已完成**

- 移除用户手动选择模式的下拉语义。
- 提交时不发送 `mode`。
- 根据响应 `mode` 展示本次实际链路。
- 保留 `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 只读可观测字段。

**已运行验证**

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_agent_api.py tests\test_agent_routing.py -q
23 passed in 2.73s
```

## Phase 6：回归验证与质量门

**状态**：已完成

**本 Phase 解决什么问题**

确认阶段 23 对评测、API 和前端的改动没有破坏既有检索、问答、Agent 和质量报告入口。

**RAG 链路位置**

全链路回归，包括 offline eval、default AgentService、agentic LangGraph、前端 Agent 面板和核心 API。

**为什么现在做**

功能开发完成后必须先用测试和浏览器验证兜底，再进入普通文档和 Obsidian 收尾。

**已完成**

- 运行新增测试、接口回归和全量测试，目标 >= 451。
- 运行浏览器桌面/移动视口检查。

**已运行验证**

```text
.\.venv\Scripts\python.exe -m pytest tests\test_stage23_agentic_eval.py tests\test_agent_routing.py tests\test_agent_api.py tests\test_frontend_app.py tests\test_agentic_graph.py tests\test_stage21_agentic_eval.py -q
51 passed in 4.32s
```

```text
.\.venv\Scripts\python.exe -m pytest -q
463 passed in 31.21s
```

```text
browser desktop:
hasModeSelect=false
modeStatusText=系统自动
modeStatusTag=OUTPUT
horizontalOverflow=false
console errors=0

browser mobile 390x844:
hasModeSelect=false
modeStatusText=系统自动
horizontalOverflow=false
```

## Phase 7：普通文档同步

**状态**：已完成

**本 Phase 解决什么问题**

把阶段 23 的设计、代码行为、评测结论、验收状态和后续边界同步到项目普通文档，避免维护者从 README 或 docs 入口看到阶段 22 的旧状态。

**RAG 链路位置**

项目知识层和维护入口，不改变运行时检索、问答或 agentic 链路。

**为什么现在做**

核心开发和回归验证已经完成，文档现在可以准确描述最终代码行为。

**已完成**

- 更新 `README.md` 当前阶段、阶段 23 要点、阶段 22 历史基线和验证结果。
- 更新 `docs/progress.md` 最新状态、评测结论、验证结果、遗留风险、下一步和面试表达。
- 更新 `docs/architecture.md`，新增阶段 23 自动模式路由架构。
- 更新 `docs/data_sources.md`，登记阶段 23 评测脚本/CSV 与安全边界。
- 更新 `AGENT.MD`，固化阶段 23 之后的 `/agent/query` 自动路由、显式 mode 覆盖、前端只读指示器和 deterministic 评测结论边界。

**已运行校验**

```text
rg -n '当前阶段：阶段 22|body\.mode = "agentic"|\[data-agent-mode\]|<select data-agent-mode|用户手动选 mode|手动选择模式|mode 下拉框' ...
```

**验证结论**

- 前端运行时代码不再读取旧 `data-agent-mode` 选择器，也不再写入 `body.mode = "agentic"`。
- 命中的旧下拉框相关文本均为历史说明、测试断言或计划记录，不是过期运行行为。
- 普通文档没有新增 secrets、供应商敏感响应或受限全文。

**操作问题与处理**

- 第一次读取 Planning with Files skill 使用了错误路径，已改用 `C:\Users\admin\.codex\skills\planning-with-files\SKILL.md`。
- 第一次 `rg` 的正则在 PowerShell 中被错误拆分，已改用单引号正则重跑。

## Phase 8：Obsidian 本地知识库收尾

**状态**：已完成

**本 Phase 解决什么问题**

把阶段 23 的每个 Phase 写成本地 Obsidian 草稿，方便后续复盘、面试表达和用户人工核验。

**RAG 链路位置**

本地知识库与复盘材料，不影响 API、检索、default AgentService 或 agentic LangGraph。

**为什么现在做**

用户明确要求开发过程中暂不写 Obsidian 小 Phase 汇报，等阶段 23 全部开发、测试和普通文档完成后再统一收尾。

**计划**

- 阅读 `obsidian-vault/模板/Phase 汇报模板.md` 和既有阶段目录样式。
- 建立阶段 23 目录、索引、Phase 0 到最终 Phase 小汇报。
- 更新阶段汇报索引和阶段总览。

**已完成**

- 创建 `obsidian-vault/阶段汇报/阶段 23 - Agentic 评测闭环与自动模式路由/`。
- 新增阶段 23 Phase 汇报索引。
- 新增 Phase 0 到 Phase 9 小汇报草稿。
- 新增 `obsidian-vault/阶段/阶段 23 - Agentic 评测闭环与自动模式路由.md`。
- 更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`。
- 校正阶段 22 Obsidian 状态为已完成并合并。

**已运行校验**

```text
Get-ChildItem -File 'obsidian-vault\阶段汇报\阶段 23 - Agentic 评测闭环与自动模式路由'
```

```text
每篇阶段 23 Phase *.md:
HasSection10=True
HasStageLink=True
HasIndexLink=True
```

**验证结论**

- 阶段 23 Obsidian 草稿完整。
- 每篇小 Phase 汇报均包含模板要求的 10 个小节。
- 阶段页、汇报索引、首页和阶段索引已互相链接。

**操作问题与处理**

- 第一次读取模板路径未加引号，已改用带引号路径成功读取。

## Phase 9：最终待人工核验状态

**状态**：已完成

**本 Phase 解决什么问题**

确认阶段 23 停在用户要求的人工核验前状态：可核验、未提交、未创建 `phase-23-complete` tag、未推送。

**RAG 链路位置**

阶段交付与版本边界，不改变检索、问答、AgentService 或 LangGraph。

**为什么现在做**

开发、测试、普通文档和 Obsidian 草稿都已完成，需要最后一次确认工作树、tag 和测试状态。

**计划**

- 清理浏览器验证生成的临时 `.playwright-mcp` 快照。
- 复跑阶段 23 deterministic 评测和全量测试。
- 最后运行 `git status -sb` 和 `git tag --list phase-23-complete`。
- 回填 Phase 9 Obsidian 汇报和根目录计划文件。

**已完成**

- 已清理 `.playwright-mcp` 临时快照目录。
- 已复跑阶段 23 deterministic 评测。
- 已复跑全量测试。
- 已确认当前分支、HEAD、`phase-22-complete` 和 `phase-23-complete` tag 状态。
- 已回填 Phase 9 Obsidian 汇报和 Planning with Files 文件。

**已运行验证**

```text
.\.venv\Scripts\python.exe scripts\evaluate_stage23_agentic_auto_routing.py

default: errors=0 error_rate=0.000 answer_like=2
agentic: errors=0 error_rate=0.000 answer_like=3 gains=1
decision: reliable_auto_route_candidate
```

```text
.\.venv\Scripts\python.exe -m pytest -q
463 passed in 27.31s
```

```text
pre-submit rerun:
.\.venv\Scripts\python.exe -m pytest -q
463 passed in 33.84s
```

```text
git tag --list phase-23-complete
<no output>
```

```text
git status -sb
## codex/phase-23-agentic-eval-and-auto-routing
阶段 23 修改和新增文件均未 staged
```

```text
final status text check:
no effective in-progress or Phase 9 pending-review markers
```

**验证结论**

- 当前分支保持 `codex/phase-23-agentic-eval-and-auto-routing`。
- `phase-23-complete` tag 尚未创建。
- 未执行 `git add`、未提交、未推送。
- 阶段 23 已按要求停在用户人工核验前状态。
- 最终一次复杂 `rg` 正则在 PowerShell 中被错误拆分，已改用简单单引号模式重跑并确认无残留进行中状态。
- `obsidian-vault/` 被 `.gitignore` 忽略；Obsidian 草稿已本地更新，但不会出现在普通 `git status` 待提交列表中。

## 遗留风险

- 阶段 21 agentic 评测的 SSL 错误可能来自真实供应商/API 环境，阶段 23 需要用 deterministic provider 或 fixture 可靠隔离。
- 若可靠评测显示 agentic 相比 default 没有明显增益，文档必须如实记录，不得把自动路由包装成全面收益。
- 前端移除手动模式选择后，仍需保留 API 层显式 `mode` 调试能力。

## 当前待提交状态

- 用户已确认提交阶段 23 整体开发工作，并上传 merge 至 GitHub。
- 下一步执行阶段 23 提交、创建 `phase-23-complete` tag、推送分支、合并到 `main` 并推送远端。

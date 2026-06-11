# Findings & Decisions（阶段 22）

## Requirements

- 阶段 22：前端 Agentic 可视化与可观测增强。
- 目标分支：`codex/phase-22-frontend-agentic-observability`。
- 必须先确认阶段 21 已完成，且 `phase-21-complete` 指向 `085bff4`。
- 必须核对阶段 21 是否已合并到 `main`。
- 若 `main` 未包含阶段 21，必须从正确基线处理：本阶段选择从 `phase-21-complete` tag 出发，不移动 `main`。
- 阶段开发完成前不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR；2026-06-11 用户已明确确认提交阶段 22 并上传 merge 至 GitHub。
- 不引入 Node 构建链或前端框架，继续使用原生 HTML/CSS/JS。
- 不做写入型 Agent 工具、登录系统、部署优化、新爬虫。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不写入 API key、Bearer token、供应商原始敏感响应或受限全文。

## Git / Tag / Main Findings

| Item | Evidence | Result |
|---|---|---|
| Current starting branch | `git status -sb` | `claude/phase-21-langgraph-agentic-rag...origin/claude/phase-21-langgraph-agentic-rag` |
| Phase 21 tag | `git rev-parse --short phase-21-complete` | `085bff4` |
| Phase 21 commit | `git show -s --format='%h %s' phase-21-complete` | `085bff4 Complete phase 21 LangGraph agentic RAG` |
| Main ancestry (initial) | `git merge-base --is-ancestor phase-21-complete main` | initially not ancestor before user requested phase 21 merge |
| Main latest after phase 21 merge | `git ls-remote origin refs/heads/main refs/tags/phase-21-complete` | both point to `085bff44898385924f766046fd3c0e5df2e322ca` |
| Phase 22 branch | `git switch -c codex/phase-22-frontend-agentic-observability phase-21-complete` | created from phase 21 tag |

Decision: after the user explicitly requested phase 21 submission/merge, `main` was fast-forwarded to `085bff4` and pushed. The phase 22 branch still starts from the same verified phase 21 baseline, so development includes all phase 21 code without moving tags.

## Frontend Current State

### `app/frontend/index.html`

- The page is a native static workbench served by FastAPI.
- It has sections for sources, documents, search, chunks, chat, citations, Agent, and Agent tool calls.
- Agent panel currently includes:
  - `data-agent-question`
  - `data-agent-top-k`
  - `data-agent-max-tool-calls`
  - `data-agent-source-id`
  - `data-agent-submit`
  - `data-agent-answer-box`
  - `data-agent-tools-list`
- There is no default / agentic mode switch yet.
- Existing Agent side panel is titled `工具调用`, which can be reused for default `tool_calls` and agentic `workflow_steps`.

### `app/frontend/static/app.js`

- `apiEndpoints.agent` already points to `/agent/query`.
- `submitAgent()` currently builds:

```js
{
  question,
  top_k: topK,
  max_tool_calls: maxToolCalls
}
```

- It conditionally adds `source_id`, but never adds `mode`.
- `renderAgentAnswer(result)` shows answer, citations, top 5 source badges and `reasoning_summary`.
- `renderAgentToolCalls(toolCalls)` shows `tool_name`, success/failure, input summary, output summary and error.
- `renderCitations()` is currently used for chat citations only; Agent result sources are summarized as badges in `renderAgentAnswer()`.
- All dynamic HTML is escaped through `escapeHtml()`, so new UI should keep that pattern.

Decision: keep existing `renderAgentToolCalls()` compatibility but introduce dedicated observability rendering where needed, using the same escaped HTML pattern.

### `app/frontend/static/styles.css`

- Layout uses simple grids, panels and list items.
- Existing reusable classes: `.data-panel`, `.panel-heading`, `.answer-box`, `.answer-meta`, `.pill`, `.pill.neutral`, `.tool-call-list`, `.tool-call-item`, `.result-snippet`, `.refusal`.
- Responsive behavior collapses major grids below 760px.
- No frontend framework or build pipeline is present.

Decision: add small, scoped CSS classes for mode switch, workflow steps, invalid citations and refusal category. Avoid nested cards and keep the operational workbench style.

### `app/frontend/quality_report.html`

- Static read-only quality report page currently titled stage 20.
- It reads inline JSON and supports section/risk filters plus CSV/JSON export.
- It is not part of the Agent panel path.

Decision: stage 22 should not rework the quality report feature beyond normal documentation/status updates unless tests require compatibility checks.

## Agentic API Current State

### `app/schemas/agent.py`

- `AgentQueryRequest` already has optional `mode: str | None = None`.
- `AgentQueryResponse` currently exposes:
  - `question`
  - `answer`
  - `tool_calls`
  - `search_results`
  - `sources`
  - `citations`
  - `refused`
  - `refusal_reason`
  - `reasoning_summary`
- It does not expose `workflow_steps`, `iteration_count`, `invalid_citations`, `mode`, or `refusal_category` as dedicated fields.

Decision: extend response schema with optional/default observability fields so old default clients continue to work.

### `app/api/agent.py`

- `query_agent()` checks `request.mode == "agentic"` and calls `run_agentic_rag()`.
- `agent_response_from_agentic_result()` maps `result.workflow_steps` into `tool_calls`.
- It sets `reasoning_summary=f"agentic RAG, iterations={result.iteration_count}"`.
- It maps agentic sources to synthetic `source_id=f"chunk:{s.chunk_id}"`.
- It currently drops dedicated `iteration_count` and `invalid_citations` fields because response schema lacks them.

Decision: preserve the existing `tool_calls` compatibility mapping, but also expose `workflow_steps`, `iteration_count`, `invalid_citations` and `mode="agentic"` directly.

### `app/services/agentic/state.py`

- `MAX_ITERATIONS = 3`.
- `AgenticState` includes:
  - `question`
  - `results`
  - `retrieval_queries`
  - `evidence_sufficient`
  - `confidence_score`
  - `iteration_count`
  - `rewritten_query`
  - `answer`
  - `citations`
  - `refused`
  - `refusal_reason`
  - `responsibility_gate_triggered`
  - `invalid_citations`
  - `workflow_steps`
- `AgenticResult` includes:
  - `question`
  - `answer`
  - `citations`
  - `sources`
  - `refused`
  - `refusal_reason`
  - `iteration_count`
  - `invalid_citations`
  - `workflow_steps`

Finding: `responsibility_gate_triggered` is in state but not currently included in `AgenticResult`. Refusal category may need to infer from `refusal_reason` or extend the result if the implementation already has state available at return time.

## Test Current State

### Existing relevant tests

- `tests/test_frontend_app.py`
  - Confirms `/` serves the frontend.
  - Confirms `/static/app.js` includes endpoints and render functions.
  - Confirms `/quality-report` and exports remain read-only.
- `tests/test_agent_api.py`
  - Covers default `/agent/query` answers/search/source detail.
  - Covers optional `history`.
  - Covers existing search/chat/sources compatibility.
  - Does not yet cover `mode="agentic"`.
- `tests/test_agentic_graph.py`
  - Covers graph compile, node behavior, max iteration cap, refusal, citation check and end-to-end deterministic runs.
- `tests/test_stage21_agentic_eval.py`
  - Covers stage 21 design doc, langgraph dependency, module structure and schema `mode`.

Decision: add phase 22 coverage primarily to `test_frontend_app.py` and `test_agent_api.py`, with minimal risk to core graph tests.

## Refusal Category Decision

Initial mapping for frontend display:

| Category | Source |
|---|---|
| `responsibility_gate_triggered` | Dedicated flag if exposed; otherwise `refusal_reason` / answer text matching responsibility boundary answer |
| `evidence_insufficient` | `refused=true` with no responsibility/off-topic signal, or default insufficient evidence answer |
| `off_topic` | `refused=true` when the query lacks domain anchor or answer/reason indicates off-topic |

Implementation preference: compute category in backend response conversion so frontend stays simple and deterministic.

## UI Decisions

- Use a select or segmented radio-like native control for Agent mode.
- Default selected mode must be `default`.
- Show mode and iteration count in `renderAgentAnswer()`.
- Keep Agent source badges; add invalid citation pills when `invalid_citations` is non-empty.
- Reuse the existing right-side Agent tools panel for workflow steps, with clearer status text when agentic mode returns `workflow_steps`.
- Do not create marketing hero content or new landing page; this is an operational workbench.

## Data Safety Decisions

- Stage 22 only changes frontend display and response metadata; it does not introduce new data sources.
- New tests must use deterministic providers and local in-memory SQLite.
- New docs/Obsidian must mention field names and behavior, not credentials or provider raw responses.

## Phase Findings

### Phase 0: 启动校准

- 阶段 21 tag 已确认：`phase-21-complete -> 085bff4`。
- `main` 起初未包含阶段 21；用户随后要求提交阶段 21 整体开发并 merge 至 GitHub，当前 `origin/main` 已指向 `085bff4`。
- Planning with Files catch-up 脚本路径存在于 `.codex`，但当前 PATH 没有 `python` 命令，已记录为非阻断项；项目测试后续可使用项目虚拟环境或工作区 Python。
- 前端现状、API schema、agentic result 字段与质量报告边界已完成初步阅读。

### Phase 1: 设计文档

- 新增 `docs/stage22_frontend_agentic_observability.md`。
- 固定阶段 22 范围：只读可观测、前端 agentic opt-in、响应契约扩展、workflow 步骤展示、无效引用标记、拒答分类展示。
- 设计文档明确 default 模式不变，不引入前端框架、不新增真实 API 测试前提。
- 新词已解释：响应契约、可观测增强、opt-in、workflow_steps、invalid_citations、拒答分类。

### Phase 2: Agentic 响应契约校准

- `AgentQueryRequest.mode` 已增加校验，只允许 `default`、`agentic` 或空值；空值保持阶段 21 之前的默认行为。
- `AgentQueryResponse` 已新增 `mode`、`workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category`，default 模式分别返回 `default`、空数组、`0`、空数组和 `None`。
- `AgentWorkflowStepItem` 用 `name`、`input_summary`、`output_summary`、`succeeded`、`error` 表达前端时间线步骤，避免前端复用 `tool_calls` 时丢失语义。
- `agent_response_from_agentic_result()` 同时填充 `workflow_steps` 和旧的 `tool_calls`，因此旧前端仍可看到工具/步骤列表，新前端可读 dedicated observability 字段。
- `AgenticResult` 已带出 `responsibility_gate_triggered`，后端转换层据此把拒答归类为 `responsibility_gate_triggered`、`off_topic` 或 `evidence_insufficient`。
- agentic 节点记录名已对齐图节点：`retrieve`、`grade`、`rewrite`、`re_retrieve`、`generate`、`citation_check`；`citation_check` 在无引用或无结果时也会记录一次，便于前端展示完整尾部检查。
- 新增 API 测试覆盖 default 新字段默认值、agentic workflow 字段、iteration count、invalid citations、responsibility gate 拒答分类。
- 聚焦验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_agent_api.py tests\\test_agentic_graph.py -q`，结果 `27 passed in 4.32s`。

### Phase 3: Agentic 模式前端接入

- `app/frontend/index.html` 的 Agent 控制区新增 `data-agent-mode` 原生下拉框，默认值为 `default`，可选 `agentic`。
- `submitAgent()` 读取 `data-agent-mode`；只有 `agentMode === "agentic"` 时才向请求体写入 `body.mode = "agentic"`，default 模式请求体保持旧行为。
- `styles.css` 已把 `.agent-controls label` 纳入现有表单标签样式，并把 Agent 控制区扩为 5 列，覆盖模式、召回数、工具步数、source_id 和运行按钮。
- `tests/test_frontend_app.py` 新增静态断言，覆盖 `data-agent-mode`、agentic option 和 JS 中的 `body.mode = "agentic"`。
- 聚焦验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_frontend_app.py -q`，结果 `6 passed in 0.74s`。

### Phase 4: 迭代过程可视化

- `renderAgentWorkflowSteps()` 已新增，读取 `workflow_steps` 并在 Agent 右侧列表展示序号、节点名、成功/失败状态、输入摘要、输出摘要和错误摘要。
- `submitAgent()` 现在优先渲染 `result.workflow_steps`；当该字段为空时继续调用旧的 `renderAgentToolCalls()`，保证 default 模式仍显示工具调用。
- `renderAgentAnswer()` 新增 `mode` 与 `iterations` badge，`iteration_count` 在结果区可见。
- `styles.css` 新增 `.workflow-step-item`、`.workflow-step-heading`、`.workflow-step-index` 和 `.pill.warning`，用于步骤列表布局与失败状态提示。
- 前后端契约已共同覆盖节点顺序：后端返回 `retrieve`、`grade`、`rewrite`、`re_retrieve`、`generate`、`citation_check`，前端逐项展示 `name`。
- 聚焦验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_frontend_app.py -q`，结果 `6 passed in 1.01s`。

### Phase 5: 引用与拒答增强展示

- `renderAgentAnswer()` 现在读取 `invalid_citations`，对命中的 citation badge 增加 `danger` 样式并显示“无效”；若无效引用不在 `citations` 中，也会单独显示无效引用 badge。
- 新增 `formatRefusalCategory()`，将 `responsibility_gate_triggered`、`evidence_insufficient`、`off_topic` 映射为中文展示标签，同时保留原始枚举值，便于调试。
- 拒答块继续显示旧的 `refusal_reason`，并在其上方增加 `refusal_category` 分类行，不改变 default 模式原有拒答文本。
- `styles.css` 新增 `.pill.danger` 与 `.refusal-category`，用于无效引用和拒答分类展示。
- `tests/test_frontend_app.py` 覆盖 `invalid_citations`、`refusal_category`、`formatRefusalCategory` 与 `responsibility_gate_triggered` 静态断言；`tests/test_agent_api.py` 已覆盖责任边界拒答分类。
- 聚焦验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_frontend_app.py tests\\test_agent_api.py -q`，结果 `14 passed in 2.20s`。

### Phase 6: 聚焦测试

- 本阶段直接相关测试文件为 `tests/test_frontend_app.py`、`tests/test_agent_api.py`、`tests/test_agentic_graph.py`、`tests/test_stage21_agentic_eval.py`。
- 聚焦回归覆盖：前端模式控件和静态资源、agentic/default API 响应契约、LangGraph 图节点与迭代上限、阶段 21 schema/design 兼容。
- 聚焦验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_frontend_app.py tests\\test_agent_api.py tests\\test_agentic_graph.py tests\\test_stage21_agentic_eval.py -q`，结果 `39 passed in 4.42s`。

### Phase 7: 回归验证与浏览器验证

- 全量测试命令：`.\\.venv\\Scripts\\python.exe -m pytest -q`，结果 `451 passed in 44.61s`；覆盖阶段 22 新增测试后总量已超过阶段 21 的 449。
- 本地服务启动：`uvicorn app.main:app --host 127.0.0.1 --port 8000`；页面 `http://127.0.0.1:8000/` 可访问，最终核验时端口 8000 仍处于监听状态。
- 浏览器桌面检查：页面标题为 `RFC RAG 工作台`；`data-agent-mode` 存在且默认值为 `default`；`agentic` option 存在；Agent 问题框、运行按钮和工具/步骤面板存在；无水平溢出；console error 为空。
- 浏览器交互检查：原生下拉框可切换到 `agentic`，选中值与显示文本均为 `agentic`。
- 浏览器移动视口检查：390x844 下 `.agent-controls` 为单列，模式控件和运行按钮可见，无水平溢出，console error 为空。
- 非阻断浏览器工具问题：插件不支持 `networkidle` 等待状态，改用 `domcontentloaded`；截图捕获命令超时，但 DOM、布局、交互和控制台检查已通过。

### Phase 8: 普通文档同步

- `README.md` 已将当前阶段更新为阶段 22，并记录阶段 21 已合并到 `origin/main -> 085bff4`、阶段 22 要点、451 个测试和人工核验前提交边界。
- `docs/progress.md` 已新增阶段 22 最新状态、Git/tag/main 起点、完成内容、验证结果、遗留风险、下一阶段任务和面试表达；阶段 21 改为已完成并合并的历史状态。
- `docs/architecture.md` 已加入阶段 22 Agentic 前端可观测架构，说明 default/agentic 分流、只读响应契约和兼容策略。
- `docs/data_sources.md` 已说明阶段 22 不新增外部资料来源、不新增爬虫、不写入真实 API 或受限全文，只新增本地前端展示和观测字段。
- `AGENT.MD` 已补充阶段 20-22 分支路线和阶段 22 之后的前端 Agentic 规则：agentic 继续 opt-in、原生前端、可观测字段只读、浏览器验证覆盖 desktop/mobile。
- `docs/stage22_frontend_agentic_observability.md` 已根据实现状态修正节点展示说明，并补充聚焦测试、全量测试和浏览器验证结果。

### Phase 9: Obsidian 收尾

- 新增 `obsidian-vault/阶段/阶段 22 - 前端 Agentic 可视化与可观测增强.md`。
- 新增 `obsidian-vault/阶段汇报/阶段 22 - 前端 Agentic 可视化与可观测增强/阶段 22 Phase 汇报索引.md`。
- 新增 Phase 0-11 共 12 篇小 Phase 汇报，每篇包含固定 10 项：目标、任务、改动、关键模块、问题与解决、新词、验证、遗留、下一步、面试表达。
- 更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`，阶段 21 改为已合并，阶段 22 改为待人工核验；提交授权后阶段 22 将进入已合并状态。
- Phase 10/11 汇报已先建草稿，待对应 Phase 完成后复核为最终状态；这是为了满足阶段 22 最终 Phase 汇报结构完整，同时不伪造尚未执行的最终检查。
- Obsidian 为本地 only、gitignored 知识库，不进入 Git 提交范围。

### Phase 10: 阶段验收报告

- 新增 `docs/phase_reviews/phase-22.md`，结论为 PASS；用户已确认进入提交/合并流程。
- 验收报告覆盖范围核对、关键实现、聚焦测试、全量测试、浏览器验证、API 兼容、安全合规、普通文档、Obsidian、提交边界和人工核验建议。
- 同步新增 `obsidian-vault/验收报告/阶段 22 验收报告.md`，并更新 `obsidian-vault/验收报告/验收报告索引.md`。
- Phase 10 的 Obsidian 小汇报已从草稿改为完成状态。

### Phase 11: 人工核验待提交状态

- 最终分支：`codex/phase-22-frontend-agentic-observability`。
- `git diff --cached --stat` 曾为空，确认人工核验前没有 staged 变更。
- `git tag -l phase-22-complete` 曾无输出，确认提交前未创建阶段 22 tag。
- 最近提交曾为 `085bff4 Complete phase 21 LangGraph agentic RAG`，确认阶段 22 在用户授权前未提交。
- `git status -sb` 显示阶段 22 工作区改动与新增 `docs/phase_reviews/phase-22.md`、`docs/stage22_frontend_agentic_observability.md`；Obsidian 文件未出现在 Git 状态，符合本地 only 规则。
- 用户已确认后，允许执行 `git add`、`git commit`、`git tag`、`git push` 与 main 合并流程；不创建 PR。

## Term Explanations

| Term | Meaning |
|---|---|
| 响应契约 | 后端 API 返回给前端的字段约定；前端只能可靠使用契约中明确存在的字段。 |
| 可观测增强 | 不改变核心回答逻辑，只把系统内部步骤、迭代次数、引用检查等状态展示出来，便于排查和解释。 |
| opt-in | 默认不启用；用户在界面显式选择 agentic 模式后才走新链路。 |
| 兼容默认值 | 新增响应字段时给 default 模式填空数组、空值或 `default`，避免旧调用因为缺字段或类型变化失败。 |
| dedicated observability 字段 | 专门给前端和排查使用的只读观测字段；它们不替代答案字段，只解释 agentic 链路如何运行。 |
| `refusal_category` | 拒答分类枚举；把 `refused=true` 的原因整理为责任边界、证据不足或离题，便于前端稳定展示。 |
| 模式切换控件 | 前端让用户显式选择 default 或 agentic 的下拉框；它是 opt-in 的 UI 入口。 |
| 时间线/步骤列表 | 按执行顺序展示 agentic RAG 每个节点的可观测记录，帮助用户看到系统是否改写、重检索或拒答。 |
| 责任边界 | 系统不能替代工程规范审查、验收、签字或合规结论；这类问题必须拒答并建议人工审查。 |
| 只读响应契约 | API 只返回解释性字段，不触发写库、外部提交或真实世界副作用。 |
| Obsidian 草稿 | 本机知识库里的复盘笔记，用于人工核验和面试准备，不随 GitHub 分发。 |
| 验收报告 | 阶段收尾证据文件，逐项说明范围、测试、安全、文档和提交边界是否满足要求。 |

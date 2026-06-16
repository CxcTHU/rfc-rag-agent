# 阶段 40 Progress：流式输出体验与输出安全

## Session: 2026-06-16

### Phase 7：语料导入与提交收尾校准

- **Status:** complete
- **Started:** 2026-06-16

Phase purpose:

- 这一 Phase 将阶段 40 从“流式输出安全人工核验前状态”切换到“用户已授权的语料导入与 GitHub 提交收尾”。
- 它位于实际导入前，负责重新读取规则、确认分支和工作区、固定导入计划与安全边界。
- 现在做它，是因为后续会写入本地 SQLite 和 raw 文件，并最终 `git add/commit/push/PR/merge`，必须先确认哪些内容可以进 Git、哪些必须保持本地。

Actions taken:

- 设置新 goal：完成阶段 40 语料库导入、验证、文档更新、提交、推送、PR 与 GitHub 合并。
- 修改线程名称为 `阶段40-流式输出与语料扩展`。
- 重新阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 运行 `git status -sb` 与 `git log --oneline -5`，确认当前分支为 `codex/phase-40-streaming-output-safety`，最近提交为 `c6e7927 Merge phase 39 production deployment`。
- 确认工作区同时包含流式输出安全改动、post-review fix、阶段 40 既有语料扩充改动和 Stage 30 score 文件改动。
- 确认 `G:\Codex\program\papers_0616` 与 `C:\Users\admin\Zotero\storage` 存在。
- 停止本地 8000 服务，避免语料导入写 SQLite 时产生锁冲突。
- 记录导入前 DB 基线：`documents=642`、`chunks=19132`。

Validation:

- `git status -sb` -> branch `codex/phase-40-streaming-output-safety`
- `git log --oneline -5` -> latest `c6e7927 Merge phase 39 production deployment`
- DB baseline query -> `documents=642`、`chunks=19132`

Next:

- Phase 8：中文文献 dry-run 和正式导入。

### Phase 8：导入中文文献

- **Status:** complete
- **Started:** 2026-06-16

Phase purpose:

- 这一 Phase 将用户合法下载的中文文献导入本地语料库。
- 它位于阶段 40 流式体验修复之后、英文 Zotero 筛选导入之前。
- 现在做它，是因为阶段 40 最终收尾需要把新增授权语料写入本地 DB，并确认全文不进入 Git。

Actions taken:

- dry-run 命令：
  - `python scripts/import_papers_corpus.py --dir "G:\Codex\program\papers_0616" --source-type institutional_access_pdf --dry-run --classify`
- dry-run 结果：
  - `scanned=150`
  - `real_pdf=150`
  - `non_pdf_skipped=0`
  - topics: `rfc_core=109`、`dam_engineering=41`
- 第一次正式导入：
  - `imported=13`
  - `duplicate=2`
  - `empty=0`
  - `failed=135`
  - 根因：PDF 文本中存在 lone surrogate codepoint，且批处理异常后未 rollback session。
- 修复：
  - `clean_text()` 删除 surrogate codepoints。
  - `scripts/import_papers_corpus.py` 单篇异常后 `db.rollback()`。
  - 新增 cleaner 回归测试。
- 修复后重跑正式导入：
  - `real PDFs=150`
  - `newly imported=93`
  - `duplicate=55`
  - `empty=2`
  - `failed=0`
  - `chunks=5637`
- 中文导入累计：
  - 新增文档 106 篇
  - 新增 chunks 6183
  - 导入后 DB：`documents=748`、`chunks=25315`

Validation:

- `python -m pytest tests\test_ingestion_cleaner.py tests\test_ingestion_service.py -q` -> `7 passed`
- `python -m pytest tests\test_agent_stream_api.py tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py -q` -> `27 passed`

Notes:

- 用户预估为 155 篇；实际当前目录可扫描真 PDF 为 150 篇。
- 两篇 PDF 无可抽取文本：`大坝应力变形分析.pdf`、`自密实堆石混凝土力学性能的实验研究和数值模拟.pdf`。
- 全文只进入本地 DB 和 `data/raw/`，均由 `.gitignore` 排除。

### Phase 0：启动校准与规划落盘

- **Status:** complete
- **Started:** 2026-06-16

Actions taken:

- 阅读 `AGENT.MD`，确认每个新线程必须先读 Agent、README、progress、architecture、data_sources，并检查 Git 状态。
- 阅读 `README.md`，确认阶段 39 已完成生产部署与端到端体验，默认 Agent 链路来自阶段 38 的 `tool_calling_agent`。
- 阅读 `docs/progress.md`，确认当前权威阶段进度为阶段 39 完成并停在人工核验/合并后的主线状态。
- 阅读 `docs/architecture.md`，确认阶段 39 前端增量已有 loading/error/citation UX；阶段 37/38 已扩展 SSE/tool-calling 事件。
- 阅读 `docs/data_sources.md`，确认上一轮阶段 40 语料扩充已写入数据说明。
- 运行 `git status -sb`，确认当前分支为 `main...origin/main`，且存在上一轮阶段 40 语料扩充未提交改动。
- 运行 `git log --oneline -5`，确认最近主线提交：
  - `c6e7927 Merge phase 39 production deployment`
  - `288bd1d Complete phase 39 production deployment`
  - `33b63e0 Merge phase 38 tool calling generation quality`
  - `ee6830a Complete phase 38 tool calling generation quality`
  - `25344a8 Merge phase 37 tool calling loop migration`
- 创建并切换到阶段 40 目标分支：`codex/phase-40-streaming-output-safety`，保留当前未提交工作区。
- 检查 Planning with Files session catchup：本机 `.claude` 路径没有 `session-catchup.py`，当前三份规划文件已完整读取，继续以根目录规划文件为准。
- 读取 `obsidian-vault/模板/goal prompt.md`，确认阶段 goal prompt 模板与“不超过 4000 字符”的要求。
- 使用 Planning with Files 方式更新根目录三份规划文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- 根据用户反馈修正 `task_plan.md` 中的 Stage 40 Goal Prompt：从压缩版执行 prompt 改为严格贴近 `obsidian-vault/模板/goal prompt.md` 的模板版，包含“阅读 agent”、目标分支、执行要求、核心链路和完成标准。

Files created/modified:

- `task_plan.md`：重写为阶段 40 流式输出体验与输出安全任务计划，并包含阶段 40 goal prompt。
- `task_plan.md`：二次修正 Stage 40 Goal Prompt，使其符合本项目 goal prompt 模板风格。
- `findings.md`：重写为阶段 40 需求、发现、技术决策、术语解释和开放问题。
- `progress.md`：重写为阶段 40 进度日志。

Current working-tree note:

- 当前工作区已有未提交语料库扩充改动，属于用户/前序 Agent 工作，不得回滚。
- 当前阶段 40 的前端流式安全规划需要与这些改动并存。

### Phase 1：设计文档与测试合同

- **Status:** complete

- **Started:** 2026-06-16

Phase purpose:

- 先固定阶段 40 的设计文档与测试合同，避免后续 sanitize、abort 和节流实现偏离边界。
- 这一步位于流式链路实现之前，负责把 `/agent/query/stream -> fetch ReadableStream -> UI 渲染` 的安全与体验约束写清楚。
- 现在做它，是因为后续每个代码 Phase 都需要可回归的测试合同和不做项边界。

Actions taken:

- 新增 `docs/stage40_streaming_output_safety.md`，说明阶段 40 基线、核心链路、四条主线、安全边界、测试合同和完成标准。
- 新增 `tests/test_stage40_streaming_output_safety.py`，先固定设计合同与后续前端静态合同。
- 梳理当前前端渲染路径：`renderAnswerWithCitationLinks()`、`renderInlineMarkdown()`、`citationReferenceHtml()` 生成回答 HTML，最终由多处 `.innerHTML` / `insertAdjacentHTML` 写入 DOM。

Validation:

- `python -m pytest tests\test_stage40_streaming_output_safety.py -k "design" -q` -> `4 passed, 4 deselected`

Planned actions:

- 新增 `docs/stage40_streaming_output_safety.md`。
- 新增/更新 Stage 40 聚焦测试，固定 sanitize、abort、中断保留、token 节流的合同。

### Phase 2：Markdown sanitize 输出安全

- **Status:** complete

- **Started:** 2026-06-16

Phase purpose:

- 这一 Phase 解决模型输出最终进入 DOM 前的 XSS 防护问题。
- 它位于 `/agent/query/stream` 收到 token/metadata 之后、citation/Markdown HTML 写入页面之前。
- 现在做它，是因为 sanitize 是停止生成和节流之前的安全底座；后续任何流式或最终渲染都应该复用同一安全出口。

Actions taken:

- 在 `app/frontend/static/app.js` 新增 `sanitizeRenderedHtml()`。
- sanitizer 使用本地 allowlist，不引入 CDN，不扩大 Markdown 能力。
- 清洗危险标签、事件属性和危险 URL。
- 将 `renderAnswerWithCitationLinks()`、`agentAnswerHtml()`、`finalizeAgentStreamingMessage()` 接入最终渲染清洗。
- 更新 `tests/test_stage40_streaming_output_safety.py` 和 `tests/test_frontend_app.py`，固定 sanitize 合同。

Validation:

- `node --check app\frontend\static\app.js` -> pass
- `python -m pytest tests\test_stage40_streaming_output_safety.py -k "design or sanitizer" -q` -> `5 passed, 3 deselected`
- `python -m pytest tests\test_frontend_app.py::test_frontend_static_assets_are_served -q` -> `1 passed`

Issue:

- 首次 sanitizer 合同测试把 JS API `startsWith` 写成了 `startswith`，已修正并重跑通过。

Planned actions:

- 确认前端 HTML 插入路径。
- 实现 sanitizer。
- 补 XSS 回归测试。

### Phase 3：AbortController 停止生成与中断状态

- **Status:** complete

- **Started:** 2026-06-16

Phase purpose:

- 这一 Phase 解决用户主动停止流式生成的问题。
- 它位于浏览器 `fetch + ReadableStream` 读取 SSE 的控制层，控制 `/agent/query/stream` 请求生命周期。
- 现在做它，是因为已有安全渲染出口后，可以安全保留半截内容并把 UI 状态收敛为“已停止生成”。

Actions taken:

- 在 `app/frontend/index.html` 增加 `data-agent-stop` 停止生成按钮。
- 在 `app/frontend/static/app.js` 增加 active abort controller、停止按钮事件、AbortError 识别和 aborted UI 收尾。
- `streamAgentQuery()` 传入 `signal`，浏览器侧可中断 `fetch + ReadableStream`。
- 中断后保留当前 assistant 气泡中的 token，并显示“已停止生成”。
- 更新 `app/frontend/static/styles.css` 的停止按钮、aborted 气泡和状态文案样式。
- 更新前端静态测试，固定 `aborted/refused/answered` 三态收尾合同。

Validation:

- `node --check app\frontend\static\app.js` -> pass
- `python -m pytest tests\test_stage40_streaming_output_safety.py -k "design or sanitizer or abort" -q` -> `6 passed, 2 deselected`
- `python -m pytest tests\test_frontend_app.py::test_frontend_index_is_served tests\test_frontend_app.py::test_frontend_static_assets_are_served -q` -> `2 passed`

Residual risk:

- 浏览器 abort 可以停止前端读取和 UI 渲染，但当前后端 producer thread/provider 调用未必被立即取消；文档和 Obsidian 收尾必须如实记录。

Issue:

- 既有前端静态测试仍断言阶段 39 的二态状态收尾字符串，已更新为阶段 40 三态合同。

### Phase 4：前端 token 渲染节流

- **Status:** complete

- **Started:** 2026-06-16

Phase purpose:

- 这一 Phase 解决流式 token 高频 DOM 写入的问题。
- 它位于 `consumeSseBuffer()` 解析 token 事件之后、`appendTokenToAgentMessage()` 写入页面之前。
- 现在做它，是因为停止生成已经能保留半截内容，接下来需要让正常生成和停止收尾都通过可控 flush，避免 token 丢失或高频 repaint。

Actions taken:

- 在 `app/frontend/static/app.js` 新增 `createAgentTokenFlushScheduler()`。
- token 事件进入 buffer，通过 `requestAnimationFrame` 或 32ms timeout 合并 flush。
- `metadata`、`done`、`error`、`abort` 均强制 flush 剩余 token。
- `submitAgent()` 不再在每个 token 后等待两帧 paint，降低高频 DOM 更新。
- 更新前端静态测试，固定 scheduler 合同。

Validation:

- `node --check app\frontend\static\app.js` -> pass
- `python -m pytest tests\test_stage40_streaming_output_safety.py -q` -> `8 passed`
- `python -m pytest tests\test_frontend_app.py::test_frontend_index_is_served tests\test_frontend_app.py::test_frontend_static_assets_are_served -q` -> `2 passed`
- `python -m pytest tests\test_agent_stream_api.py -q` -> `8 passed`

### Phase 5：集成验证与浏览器 smoke

- **Status:** complete

- **Started:** 2026-06-16

Phase purpose:

- 这一 Phase 验证阶段 40 改动是否破坏既有入口和浏览器体验。
- 它覆盖完整链路：FastAPI 静态首页、前端 JS、`/agent/query/stream` SSE、桌面与移动视口。
- 现在做它，是因为 sanitize、abort、token scheduler 都已实现，需要从用户实际操作角度验证正常生成、停止生成和安全渲染。

Actions taken:

- 启动本地 FastAPI smoke 服务 `http://127.0.0.1:8011` 并确认 `/health` 可用。
- 桌面浏览器 smoke：页面加载、正常短流式回答、停止生成、停止后状态收敛、无横向溢出。
- 移动端浏览器 smoke：390x844 下 Agent 控件存在、无横向溢出、console errors=0。
- 修复浏览器 smoke 暴露的首 token 前停止残留“正在思考”问题。
- 停止本地 8011 smoke 服务。

Validation:

- `python -m pytest tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py tests\test_agent_stream_api.py -q` -> `26 passed`
- `python -m pytest -q` -> `819 passed`

Browser smoke:

- Desktop normal stream: passed; `agentStatus=answered`，`apiStatus=Agent 已完成`，horizontal overflow=false。
- Desktop abort: passed after fix; `agentStatus=aborted`，`apiStatus=Agent 已停止生成`，`hasAbortStatus=true`，`thinkingResidue=false`，submit restored。
- Mobile 390x844: passed; `horizontalOverflow=false`，console errors=[]。

### Phase 6：文档、Obsidian 草稿与人工核验前收尾

- **Status:** complete; waiting for user human verification

- **Started:** 2026-06-16

Phase purpose:

- 这一 Phase 把阶段 40 的代码、测试和浏览器验证结果沉淀到普通文档与 Obsidian 本地知识库。
- 它位于开发和验证之后、用户人工核验之前。
- 现在做它，是因为阶段 40 功能已经通过聚焦测试、全量 pytest 和浏览器 smoke，需要停在可核验、未提交状态。

Actions taken:

- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，记录阶段 40 流式输出体验与输出安全完成状态、后端取消边界和人工核验前状态。
- 新增 `docs/phase_reviews/phase-40.md`，沉淀目标、主要改动、测试、风险和核验建议。
- 新增 Obsidian 阶段页：`obsidian-vault/阶段/阶段 40 - 流式输出体验与输出安全.md`。
- 新增 Obsidian 阶段汇报目录与 Phase 0 到 Phase 6 小汇报。
- 更新 `obsidian-vault/阶段汇报索引.md`，加入阶段 40 Phase 汇报索引。
- 保留前序 Agent 的阶段 40 语料扩充未提交改动，未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

Validation:

- `python -m pytest tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py tests\test_agent_stream_api.py -q` -> pass
- 阶段 40 收尾前全量验证曾运行：`python -m pytest -q` -> `819 passed`

Residual risks:

- 浏览器 `AbortController` 已能中断前端 fetch/ReadableStream 与 UI 渲染；当前后端 producer thread/provider 调用不承诺被浏览器 abort 立刻取消，文档与 Obsidian 已诚实记录该边界。
- 停止生成后的半截回答目前保留在当前页面 UI 状态中，不作为新的后端会话消息持久化。
- 工作区仍包含阶段 40 语料扩充改动与本轮流式输出安全改动，等待用户人工核验后再决定提交边界。

Post-review fix 1:

- 根据用户在 8000 页面人工查看反馈，修复流式文本不可见、停止按钮交互不符合预期、停止后半截文本不可见三个问题。
- 移除独立 `data-agent-stop` 按钮；运行中的 `data-agent-submit` 主按钮变为红色 `.command-button--stop`，文案为“停止生成”。
- 删除 `.chat-message--thinking .answer-text` 隐藏规则，保证 token 追加后立即可见，中断时半截内容留在 assistant 气泡中。
- `submitAgent()` 在已有请求运行中再次触发时改为调用 `abortAgentStream()`。
- 静态资源版本更新为 `phase40-streaming-output-safety-fix1`，降低浏览器缓存导致旧 UI 继续出现的概率。
- 验证：
  - `node --check app\frontend\static\app.js` -> pass
  - `python -m pytest tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py tests\test_agent_stream_api.py -q` -> `26 passed`
  - 8000 首页检查：存在新资源版本、无独立停止按钮、保留主提交按钮。

Post-review fix 2:

- 修复运行中点击红色主按钮仍触发表单“请填写此字段”的问题。
- `data-agent-submit` 增加 click 截流：运行中点击时 `preventDefault()` 并调用 `abortAgentStream()`。
- 运行中临时关闭问题输入框 `required`，收尾时恢复，避免浏览器原生必填气泡干扰停止生成。
- 修复默认 `tool_calling_agent` 的最终回答 SSE token 生产：流式入口为 tool-calling 链路包装 `QueueStreamingChatModelProvider`，并委托 `generate_with_tools()`，保持工具调用行为不变。
- 静态资源版本更新为 `phase40-streaming-output-safety-fix2`。
- 验证：
  - `node --check app\frontend\static\app.js` -> pass
  - `python -m pytest tests\test_agent_stream_api.py tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py -q` -> `27 passed`
  - 8000 浏览器自动化：运行中 required=false、validation message 为空；二次点击主按钮进入 aborted。
  - 8000 SSE 计时：默认 tool-calling 链路在工具调用后输出真实 `event: token`。

## Test Results

### Phase 9: Zotero RFC English Import

- **Status:** complete
- **Started/Completed:** 2026-06-16

Phase purpose:

- This Phase imports the small English RFC-related supplement from Zotero after the Chinese paper batch.
- It sits in the corpus ingestion chain before DB verification and quality regression.
- It is done now because the stage closeout requires the local corpus to include the authorized Chinese and English expansion before final tests and GitHub submission.

Actions taken:

- Added `scripts/import_stage40_zotero_rfc.py` for reproducible one-level Zotero storage enumeration and filename filtering.
- Dry-run command: `python scripts/import_stage40_zotero_rfc.py --storage-dir "C:\Users\admin\Zotero\storage" --source-type open_access_pdf --dry-run`.
- Formal import command: `python scripts/import_stage40_zotero_rfc.py --storage-dir "C:\Users\admin\Zotero\storage" --source-type open_access_pdf`.
- Imported through `IngestionService.import_document()` with `source_type=open_access_pdf`.

Results:

- Dry-run: `scanned_pdfs=66`, `matched_pdfs=9`.
- Formal import: `scanned_pdfs=67`, `matched_pdfs=9`, `imported=5`, `duplicate=4`, `empty=0`, `failed=0`, `new_chunks=372`.
- Non-RFC PDFs in Zotero storage were not imported.

Residual risk:

- The Zotero filenames displayed mojibake in PowerShell output for Chinese connector words such as author separators, but filtering and import used actual filesystem paths and completed successfully.

### Phase 10: Import Verification And Quality Regression

- **Status:** complete
- **Started/Completed:** 2026-06-16

Phase purpose:

- This Phase verifies that imported documents actually increased the active corpus and did not regress tests or Stage 30 quality.
- It sits after corpus ingestion and before documentation/commit closeout.
- It is done now because GitHub submission should only happen after DB, regression, and release quality gates are proven.

Validation:

- DB counts: `documents=753`, `chunks=25687`.
- Source distribution: `institutional_access_pdf=431`, `web_page=136`, `metadata_record=115`, `wikipedia=25`, `open_access_pdf=20`, `standard_document=16`, `local_file=10`.
- Full regression: `python -m pytest -q` -> `821 passed in 87.68s`.
- Stage 30 quality: `python scripts/score_stage30_quality.py` -> `overall=91.52`, `grade=A`, `release_decision=pass`.

Residual risk:

- The imported full-text corpus remains local runtime state and is intentionally not committed. A fresh clone will need the same import steps to recreate the local DB.

### Phase 11: Documentation Closeout

- **Status:** complete
- **Started/Completed:** 2026-06-16

Phase purpose:

- This Phase synchronizes the final code, corpus import, DB verification, and quality results into reader-facing docs before submission.
- It sits after validation and before Git staging/commit.
- It is done now because the PR should carry a self-contained record of what Phase 40 changed and what remains local-only.

Actions taken:

- Updated `README.md` top Phase 40 status.
- Updated `docs/progress.md` latest Phase 40 status and final verification.
- Updated `docs/data_sources.md` Phase 40 corpus import closeout.
- Updated `docs/architecture.md` with final stop-button behavior, `QueueStreamingChatModelProvider`, and corpus closeout boundary.
- Updated `docs/phase_reviews/phase-40.md` with streaming fixes, corpus import results, DB counts, and submission boundary.
- Updated `task_plan.md`, `findings.md`, and `progress.md` with Phase 9-11 checkpoints.

Residual risk:

- Historical sections still mention earlier human-verification boundaries for previous phases or earlier Phase 40 sub-phases; those are retained as history, while the top/latest Phase 40 sections record the current authorized submission state.

| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Git status | `git status -sb` | 确认分支和未提交改动 | `main...origin/main`，存在阶段 40 语料扩充改动 | pass |
| Git log | `git log --oneline -5` | 确认阶段 39 已合并 | 最近提交为 `c6e7927 Merge phase 39 production deployment` | pass |
| Planning files | 更新三份根目录规划文件 | task_plan/findings/progress 指向阶段 40 | 已完成 | pass |
| Stage 40 focused tests | `python -m pytest tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py tests\test_agent_stream_api.py -q` | sanitize、abort、节流、SSE 兼容与前端入口通过 | 已通过 | pass |
| Post-review fix 1 focused tests | `python -m pytest tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py tests\test_agent_stream_api.py -q` | 主按钮停止态、流式文本可见性和既有 SSE 合同通过 | `26 passed` | pass |
| Post-review fix 2 focused tests | `python -m pytest tests\test_agent_stream_api.py tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py -q` | 停止按钮绕过 required 校验、默认 tool-calling 最终回答真流式、前端合同通过 | `27 passed` | pass |
| Full pytest | `python -m pytest -q` | 全量回归通过 | `819 passed` | pass |
| Browser smoke | 桌面与移动端 in-app browser | 正常流式、停止生成、无横向溢出、无 console error | 已通过 | pass |

## Error Log

| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-06-16 | PowerShell 不支持 `git status -sb && git log --oneline -5` | 1 | 分别运行 `git status -sb` 与 `git log --oneline -5` |
| 2026-06-16 | `goal prompt.md` 路径含空格，普通 `Get-Content` 解析失败 | 1 | 使用 `Get-Content -LiteralPath` |

## 5-Question Reboot Check

| Question | Answer |
|----------|--------|
| Where am I? | 阶段 40 Phase 6 已完成，等待用户人工核验 |
| Where am I going? | 用户核验通过后，才进入提交、tag、push 或 PR 流程 |
| What's the goal? | 完成阶段 40 前四项流式输出体验与输出安全能力，并停在人工核验前 |
| What have I learned? | 见 `findings.md` |
| What have I done? | 已完成阶段 40 开发、测试、普通文档和 Obsidian 草稿，且保持未提交状态 |

---

*后续每完成一个 Phase 或遇到错误，都要更新本文件。*

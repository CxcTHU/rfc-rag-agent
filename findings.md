# 阶段 40 Findings：流式输出体验与输出安全

## Requirements

- 阶段 40 先做 Claude 建议中的前四条：
  - Markdown 最终渲染前 sanitize。
  - AbortController 停止生成。
  - 中断后保留半截内容并标记“已停止生成”。
  - 前端 token 渲染节流。
- 暂缓第 5 条长回答虚拟列表/分段虚拟渲染。
- 按 `AGENT.MD` 和 goal prompt 模板更新三份规划文件。
- 本阶段结束前不提交、不打 tag、不 push、不创建 PR，等待用户人工核验。
- 保留当前已有语料库扩充改动，不得回滚。
- 用户已授权进入阶段 40 最终收尾：导入中文/英文语料、验证导入、更新文档、提交、push、创建 PR 并合并到 GitHub。

## Research Findings

### 项目当前阶段

- 阶段 39 已合并到 `main`：
  - `c6e7927 Merge phase 39 production deployment`
  - `288bd1d Complete phase 39 production deployment`
- 阶段 39 已经完成 FastAPI Docker 部署、结构化日志、前端 loading/error/citation UX。
- 阶段 38 已将默认 Agent 链路切到 `tool_calling_agent`，`/agent/query/stream` 省略 mode 时也走该链路。
- 当前阶段 40 已有一轮语料库扩充未提交改动，包括中文标准题录入库、OpenAlex 严格 license 二筛和相关测试。
- 当前开发分支已创建为 `codex/phase-40-streaming-output-safety`，从 `c6e7927` 所在 `main` 出发，未提交语料扩充改动随工作区保留。
- 2026-06-16 阶段 40 收尾启动时，分支仍为 `codex/phase-40-streaming-output-safety`，最近提交仍为 `c6e7927 Merge phase 39 production deployment`。
- 导入前本地 DB 基线：`documents=642`、`chunks=19132`；source_type 分布为 `institutional_access_pdf=325`、`web_page=136`、`metadata_record=115`、`wikipedia=25`、`standard_document=16`、`open_access_pdf=15`、`local_file=10`。

### 语料导入计划理解

- 中文文献源目录为 `G:\Codex\program\papers_0616`，使用已有 `scripts/import_papers_corpus.py` 导入，`source_type=institutional_access_pdf`，先 dry-run 再正式导入。
- 英文文献源目录为 `C:\Users\admin\Zotero\storage`，目录形态为 `storage/<ID>/<filename>.pdf`；只按文件名筛选 RFC 相关 PDF，不导入非 RFC 论文。
- 英文筛选关键词包括 `rock-filled`、`rock filled`、`rockfill`（dam/concrete 语境）、`SCC`（self-compacting concrete 语境）、`stone-concrete`（dam 语境）和 `堆石`。
- 英文匹配论文使用 `IngestionService.import_document()` 导入，`source_type=open_access_pdf`。
- `data/app.sqlite`、`data/raw/`、`data/fulltext/`、`data/faiss/` 均由 `.gitignore` 排除；全文和 DB 不进入 Git。

### 中文文献导入发现

- `G:\Codex\program\papers_0616` 实际扫描为 150 个 PDF，不是预估 155 个；dry-run 主题分布为 `rfc_core=109`、`dam_engineering=41`。
- 第一次正式导入新增 13 篇后遇到 PDF 抽取文本中的 lone surrogate codepoint（例如 `\ud835`）导致 SQLite UTF-8 写入失败；随后 SQLAlchemy session 未 rollback，造成后续文件被 `PendingRollbackError` 连带失败。
- 修复策略：
  - `app/services/ingestion/cleaner.py` 在 `clean_text()` 开头删除 lone surrogate codepoints。
  - `scripts/import_papers_corpus.py` 在 `EmptyDocumentError` 和泛异常分支调用 `db.rollback()`，保证单篇失败不拖垮批次。
- 修复后重跑中文导入，新增 93 篇，55 篇 duplicate，2 篇 empty，0 failed。
- 中文导入累计新增 106 篇 institutional_access_pdf，新增 6183 chunks；2 篇 empty 为 `大坝应力变形分析.pdf` 与 `自密实堆石混凝土力学性能的实验研究和数值模拟.pdf`。

### 当前流式链路理解

- 后端 SSE 入口位于 `app/api/agent.py` 的 `/agent/query/stream`。
- 事件类型包括 `token`、`metadata`、`done`、`error`，以及阶段 37/38 后的 `agent_step`、`tool_call_start`、`tool_call_result`。
- 前端流式读取主要位于 `app/frontend/static/app.js` 的 `streamAgentQuery`、SSE buffer 解析、token 回调和 Agent UI 渲染路径。
- 阶段 25 曾说明：由于需要 POST body 和 Header，项目采用 `fetch + ReadableStream` 手动解析 SSE，而不是原生 `EventSource`。
- `renderAnswerWithCitationLinks()` 当前先用 `renderInlineMarkdown()` 转义普通文本，只把 `[N]` 转成 citation button；最终由 `renderAnswer()`、`appendAgentAssistantMessage()`、`finalizeAgentStreamingMessage()` 等路径写入 `.innerHTML`。
- 因为 citation button 是本项目自己生成的可信 HTML，而 answer 文本来自模型，sanitize 的最小安全点应放在“回答 HTML 片段写入 DOM 之前”，避免后续 Markdown 能力扩展时绕过安全出口。

### Claude 建议的阶段 40 前四项判断

- AbortController：前端 `controller.abort()` 能立即中断浏览器侧 fetch/ReadableStream；但后端 provider 是否立刻停止取决于 FastAPI generator 和 producer 线程是否检测到断开，应在实现中验证并诚实记录。
- Token 渲染节流：每 token 写 DOM 容易造成高频 reflow/repaint；使用 `requestAnimationFrame` 或 16-50ms buffer flush 可以显著降低 DOM 写入次数，同时保留流式观感。
- 中断保留：停止生成后保留已收到 token 是用户体验必需，否则会出现“点停止后内容消失/状态不一致”。
- Markdown sanitize：如果模型输出最终以 HTML 插入 DOM，必须剥离危险标签和属性，防止 prompt injection 引发 XSS。

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| 阶段 40 聚焦“流式输出体验与输出安全”，不继续语料扩充 | 语料扩充和前端安全属于不同关注点，混在一起会让验收边界模糊 |
| sanitize 放在高优先级 | 输出安全是底线，且面试中能体现安全意识 |
| 停止生成与半截保留同阶段完成 | 单独做 abort 会留下 UI 状态问题 |
| token 节流只改前端调度，不改变 SSE 协议 | 降低后端回归风险，保持 API 兼容 |
| 长回答虚拟列表暂缓 | 当前领域问答通常不足以触发必须虚拟化的 DOM 规模 |
| 不改变检索/prompt/provider/评分 | 阶段 40 的交付面是前端和流式运行体验，不影响阶段 38/39 的质量链路 |
| 不使用 CDN 运行时依赖 | 项目部署应可离线/可控，避免安全和网络不确定性 |
| sanitizer 先做项目可控的最小 allowlist | 当前只需要保留 citation button、popover、strong 和状态 badge，不需要引入完整 Markdown HTML 白名单 |
| sanitize 输出点命名为 `sanitizeRenderedHtml()` | 语义明确：它只处理最终渲染 HTML，不处理检索文本、source metadata 或后端响应 |
| abort 先保证浏览器侧受控停止与半截保留 | 当前后端 `stream_non_chitchat_agent_response()` 使用 producer thread + queue，浏览器 abort 不保证立刻取消底层 provider 调用 |
| token scheduler 使用 rAF + 32ms timeout 双保险 | rAF 贴近浏览器绘制，32ms timeout 避免后台或低帧率场景中 buffer 长时间不 flush |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| PowerShell 不支持 Bash 风格 `&&` 串联命令 | 改为分别运行 `git status -sb` 与 `git log --oneline -5` |
| `obsidian-vault/模板/goal prompt.md` 路径包含空格 | 使用 `Get-Content -LiteralPath` 读取 |
| 当前工作区已有阶段 40 语料扩充改动 | 在规划文件中明确列出，后续不得回滚 |
| Planning with Files 的 `session-catchup.py` 在本机 `.claude` 路径不存在 | 已完整读取当前 `task_plan.md`、`findings.md`、`progress.md`，继续以根目录三份文件为准 |
| Stage 40 sanitizer 静态测试首次失败，原因是测试断言写成 Python 风格 `startswith` | 修正为 JS `startsWith` 后重跑通过 |
| 前端静态测试仍锁定阶段 39 二态状态文案 | 更新为阶段 40 三态 `aborted/refused/answered` 断言 |

## Resources

- `AGENT.MD`：项目唯一规则真相源，包含双 Agent 协作、规划文件、人工核验前不提交等规则。
- `obsidian-vault/模板/goal prompt.md`：阶段 goal prompt 模板，要求 goal prompt 不超过 4000 字符。
- `app/api/agent.py`：Agent 同步与流式 API 入口。
- `app/frontend/static/app.js`：前端 Agent UI、SSE 读取、token 渲染、citation 渲染主文件。
- `app/frontend/static/styles.css`：停止生成按钮、状态标记、citation、loading 等样式位置。
- `tests/test_agent_stream_api.py`：流式 API 相关回归测试候选。
- `tests/test_frontend_app.py`：前端静态合同测试候选。

## Visual/Browser Findings

- 用户前序截图来自抖音视频，主题是“大模型流式输出前端怎么接”，核心提醒包括：
  - `EventSource` 原生只支持 GET；项目因为要 POST body，已使用 `fetch + ReadableStream`。
  - 流式 token 不能每 chunk 直接高频更新 DOM，应做节流。
  - LLM 输出 Markdown/HTML 有 XSS 风险，应 sanitize。
  - 中断不应只停前端渲染，还应尽量取消后端请求。
  - 中断后应保留已有内容并显示状态。

## 术语解释

- `AbortController`：浏览器原生取消控制器，可把 `signal` 传给 `fetch`，调用 `abort()` 后中断请求。本项目用于“停止生成”按钮。
- `SSE`：Server-Sent Events，服务端持续向前端推送事件；本项目用它逐 token 输出 Agent 回答。
- `ReadableStream`：浏览器 fetch 响应体的流式读取接口；本项目用 `response.body.getReader()` 手动解析 SSE。
- `requestAnimationFrame`：浏览器在下一帧绘制前执行回调的 API，适合把多次 token 更新合并成一帧 DOM 写入。
- `sanitize`：清洗不可信 HTML，剥离脚本、事件属性、危险 URL 等，避免 XSS。
- `XSS`：跨站脚本攻击，攻击者诱导页面执行恶意脚本；LLM 输出若未经清洗直接插入 DOM，可能成为入口。

## Phase 9 Finding: Zotero RFC English Import

- `C:\Users\admin\Zotero\storage` follows `storage/<ID>/<filename>.pdf`; PowerShell enumeration found 66 PDFs during manual listing, while the formal script saw 67 PDFs at import time.
- Filename filtering intentionally stayed narrow: `rock-filled`, `rock filled`, `rock-fill/rockfill` with dam/concrete context, `SCC` with concrete/rock/aggregate context, `stone-concrete` with dam/rockfill context, and `堆石`.
- The final matched set contained 9 RFC-related PDFs. Non-RFC rock support, mining, tunnel, foundation, and generic concrete papers were left out to avoid corpus noise.
- `scripts/import_stage40_zotero_rfc.py` uses the same `IngestionService.import_document()` path as existing imports, with `source_type=open_access_pdf`.
- Import result: 5 newly imported documents, 4 duplicates by content hash, 0 empty, 0 failed, 372 new chunks.
- New term: `content hash dedupe` means the importer hashes stored raw file content and skips documents already present in the corpus. In this project it appears in `IngestionService.import_document()` through `DocumentRepository.get_by_content_hash()`. Interview phrasing: this keeps batch imports idempotent, so rerunning the importer does not create duplicate documents.

## Phase 10 Finding: Import Verification And Regression

- The local DB now contains `documents=753` and `chunks=25687`, proving both Chinese and English imports were chunked into the active corpus.
- `institutional_access_pdf=431` reflects the Chinese paper import; `open_access_pdf=20` reflects the 5 newly imported Zotero RFC PDFs on top of the previous 15 open-access PDFs.
- Full regression passed with `821 passed`, including the Phase 40 streaming output safety tests and ingestion cleaner rollback/surrogate fixes.
- Stage 30 scoring stayed at `overall=91.52`, `grade=A`, `release_decision=pass`, so the corpus import and streaming fixes did not regress the established release quality gate.
- Boundary: `data/app.sqlite`, `data/raw/`, `data/fulltext/`, and `data/faiss/` remain local/gitignored runtime data; only scripts, metadata, tests, CSV summaries, and docs should be staged.

## Phase 11 Finding: Documentation Closeout

- The top-level reader path is now consistent: `README.md`, `docs/progress.md`, `docs/data_sources.md`, `docs/architecture.md`, and `docs/phase_reviews/phase-40.md` all record the final streaming fixes, corpus import, DB counts, `821 passed`, and Stage 30 `91.52/A/pass`.
- The documentation now distinguishes two boundaries: runtime corpus state is local/gitignored, while committed files are scripts, tests, metadata/evaluation summaries, and docs; phase tags are not created unless separately requested.
- The architecture note explicitly corrects the UI contract after user review: there is no extra stop button; the main submit button changes into the red stop-generation control while running.
- The data-source note records the actual Chinese directory count (`150`, not estimated `155`) and the actual Zotero match count (`9`, not approximately `10`), keeping the corpus record honest.

## Open Questions

1. 当前前端是否引入 Markdown 库，还是主要使用自写 citation HTML 渲染？实现前需确认实际插入 HTML 的路径。
2. 后端 `StreamingResponse` 在客户端断开时是否能取消 generator；producer thread 是否还会继续调用模型？
3. 停止后的半截消息是否只保留在当前页面状态，还是需要写入后端 conversation messages？
4. DOMPurify 是否已有依赖或需要 vendored 文件？如果新增依赖，是否要更新构建/部署文档？

## Phase 1 Result

- 新增 `docs/stage40_streaming_output_safety.md`，固定目标、输入、四条主线、安全边界、测试合同和完成标准。
- 新增 `tests/test_stage40_streaming_output_safety.py`，其中设计合同已通过；前端 sanitize/abort/节流合同将在 Phase 2-4 实现后通过。
- 设计合同验证：`python -m pytest tests\test_stage40_streaming_output_safety.py -k "design" -q` -> `4 passed, 4 deselected`。

## Phase 2 Result

- `app/frontend/static/app.js` 新增 `sanitizeRenderedHtml()`，使用本地 allowlist 清洗最终回答 HTML。
- sanitizer 删除危险标签：`script`、`iframe`、`object`、`embed`、`style`、`link`、`meta`、`form`。
- sanitizer 删除事件属性：所有 `on*` 属性，例如 `onclick`、`onerror`、`onload`。
- sanitizer 删除危险 URL：`javascript:` 和 `data:text/html`。
- `renderAnswerWithCitationLinks()`、`agentAnswerHtml()`、`finalizeAgentStreamingMessage()` 等回答渲染路径已接入 sanitizer。
- 验证：
  - `node --check app\frontend\static\app.js` -> pass
  - `python -m pytest tests\test_stage40_streaming_output_safety.py -k "design or sanitizer" -q` -> `5 passed, 3 deselected`
  - `python -m pytest tests\test_frontend_app.py::test_frontend_static_assets_are_served -q` -> `1 passed`

## Phase 3 Result

- `app/frontend/index.html` 新增运行期“停止生成”按钮：`data-agent-stop`。
- `app/frontend/static/app.js` 新增 `state.activeAgentAbortController`、`abortAgentStream()`、`isAgentAbortError()` 和 `markAgentStreamingAborted()`。
- `streamAgentQuery()` 现在把 `AbortController.signal` 传给 `fetch`。
- 用户停止生成后，当前 assistant 气泡保留已收到 token，标记 `chat-message--aborted`，并显示“已停止生成”。
- 停止后 `setAgentBusy(false)` 仍会在 finally 中执行，允许继续发送新问题。
- 后端边界：当前后端 producer thread 和 provider 调用不保证被浏览器 abort 立刻终止；阶段 40 文档必须诚实记录为“前端可控停止，后端尽力收敛”。
- 验证：
  - `node --check app\frontend\static\app.js` -> pass
  - `python -m pytest tests\test_stage40_streaming_output_safety.py -k "design or sanitizer or abort" -q` -> `6 passed, 2 deselected`
  - `python -m pytest tests\test_frontend_app.py::test_frontend_index_is_served tests\test_frontend_app.py::test_frontend_static_assets_are_served -q` -> `2 passed`

## Phase 4 Result

- 新增 `createAgentTokenFlushScheduler()`，token 先进入 `tokenBuffer`，再通过 `requestAnimationFrame` 或 32ms timeout 合并写入 DOM。
- `submitAgent()` 中的 `onToken` 改为 `tokenScheduler.push(token)`，不再每 token 立即写 DOM。
- `metadata`、`done`、`error`、`abort` 均会调用 `tokenScheduler.flushNow()`，保证剩余 token 不丢。
- SSE 事件协议未改变，后端 `/agent/query/stream` 的 `token`、`metadata`、`done`、`error`、`agent_step`、`tool_call_start`、`tool_call_result` 均保持兼容。
- 验证：
  - `node --check app\frontend\static\app.js` -> pass
  - `python -m pytest tests\test_stage40_streaming_output_safety.py -q` -> `8 passed`
  - `python -m pytest tests\test_frontend_app.py::test_frontend_index_is_served tests\test_frontend_app.py::test_frontend_static_assets_are_served -q` -> `2 passed`
  - `python -m pytest tests\test_agent_stream_api.py -q` -> `8 passed`

## Phase 5 Result

- 本地 FastAPI smoke 服务：`http://127.0.0.1:8011`，`GET /health` -> 200。
- 桌面浏览器 smoke：
  - 首页加载成功，Agent form 和停止按钮存在。
  - 正常短流式回答“谢谢”完成，状态 `answered`，无横向溢出。
  - 长问题点击“停止生成”后状态 `aborted`，气泡保留并显示“已停止生成”，提交按钮恢复。
  - 修复了首 token 前停止时残留“正在思考”的 UI 问题。
- 移动端浏览器 smoke：390x844，首页和 Agent 控件存在，水平溢出为 false，console errors=0。
- 验证：
  - `python -m pytest tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py tests\test_agent_stream_api.py -q` -> `26 passed`
  - `python -m pytest -q` -> `819 passed`
- smoke 后已停止 8011 uvicorn 服务。

## Phase 6 Result

- 普通文档已同步阶段 40：`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 新增阶段复盘文档：`docs/phase_reviews/phase-40.md`。
- Obsidian 本地知识库已补齐阶段 40：
  - `obsidian-vault/阶段/阶段 40 - 流式输出体验与输出安全.md`
  - `obsidian-vault/阶段汇报/阶段 40 - 流式输出体验与输出安全/阶段 40 Phase 汇报索引.md`
  - Phase 0 到 Phase 6 小汇报
  - `obsidian-vault/阶段汇报索引.md`
- 最终阶段聚焦测试已重跑：`python -m pytest tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py tests\test_agent_stream_api.py -q`。
- 当前状态：阶段 40 开发、测试、普通文档和 Obsidian 草稿完成；未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR；等待用户人工核验。

## Post-Review Fix 1

- 用户人工查看 8000 页面后发现三点：流式文本不可见、停止生成不应使用额外按钮、停止后半截文本不可见。
- 根因：阶段 40 初版保留了独立 `data-agent-stop` 按钮，且 CSS 中 `.chat-message--thinking .answer-text { display: none; }` 会隐藏 token 追加目标；当 metadata 尚未到达或用户中途停止时，半截文本容易被 thinking 态遮住。
- 修复：
  - 移除独立停止按钮，运行中的 `data-agent-submit` 主按钮直接变为“停止生成”。
  - 新增 `.command-button--stop` 红色危险态，让主按钮从蓝色运行态切换到红色停止态。
  - `submitAgent()` 在 `state.agentRequestInFlight` 为 true 时直接调用 `abortAgentStream()`。
  - 删除 thinking 态隐藏 `.answer-text` 的样式，使 token 一到达就可见，停止后也继续保留在当前 assistant 气泡中。
  - 静态资源版本 bump 到 `phase40-streaming-output-safety-fix1`，避免浏览器缓存旧 JS/CSS。
- 验证：
  - `node --check app\frontend\static\app.js` -> pass
  - `python -m pytest tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py tests\test_agent_stream_api.py -q` -> `26 passed`
  - 8000 页面合同检查：引用 `phase40-streaming-output-safety-fix1`，无 `data-agent-stop`，存在 `data-agent-submit`。

## Post-Review Fix 2

- 用户再次人工查看发现：运行中点击红色主按钮仍触发表单“请填写此字段”，且回答流式感仍不明显。
- 前端根因：主按钮仍是 submit 类型，运行开始后 textarea 被清空；第二次点击时浏览器原生 required 校验可能先于 submit handler 抢占交互。
- 前端修复：
  - 为 `data-agent-submit` 增加 click handler；运行中点击会 `preventDefault()` 并直接调用 `abortAgentStream()`。
  - `setAgentBusy(true)` 时临时关闭 `data-agent-question.required`，收尾时恢复，避免运行中出现原生必填气泡。
  - 静态资源版本 bump 到 `phase40-streaming-output-safety-fix2`。
- 后端根因：`stream_non_chitchat_agent_response()` 初版没有给默认 `tool_calling_agent` 包 `QueueStreamingChatModelProvider`；如果服务内部最终回答使用普通 `generate()`，前端只能等结果完成后 fallback 拆 token。
- 后端修复：
  - 除 `react_agent` 外，流式入口统一使用 `QueueStreamingChatModelProvider` 包装 chat provider。
  - `QueueStreamingChatModelProvider.generate_with_tools()` 委托到底层 provider，保持工具调用决策不变；普通 `generate()` 负责把最终回答 token 推入 SSE queue。
- 验证：
  - `node --check app\frontend\static\app.js` -> pass
  - `python -m pytest tests\test_agent_stream_api.py tests\test_stage40_streaming_output_safety.py tests\test_frontend_app.py -q` -> `27 passed`
  - 浏览器自动化：运行中 `required=false`、无 validation message；第二次点击主按钮后 `agentStatus=aborted`、`hasAbortStatus=true`。
  - SSE 计时：默认 `tool_calling_agent` 在工具步骤后输出 `event: token`，最终回答阶段不再只依赖完成后的 fallback token 拆分。

---

*本文件是阶段 40 的外部记忆。后续每发现关键事实或完成重要决策，都应更新这里。*

# 阶段 40：流式输出体验与输出安全

## 目标

阶段 40 从 `main / origin/main -> c6e7927 Merge phase 39 production deployment` 出发。阶段 39 已完成 FastAPI 生产部署、结构化日志、前端 loading/error/citation 体验；阶段 38 已把默认 Agent 链路稳定为 `tool_calling_agent`，Stage 30 保持 `91.52 / A / pass`。

本阶段目标是把既有流式问答链路补齐为更安全、更可控的前端体验：

```text
/agent/query/stream
-> fetch + ReadableStream 手动解析 SSE
-> token buffer + requestAnimationFrame/定时 flush
-> 安全渲染文本/Markdown/citation
-> AbortController 停止生成
-> 保留已收到 token 并标记“已停止生成”
-> done/error/abort 时 flush 剩余 token 并收敛 UI 状态
```

## 输入与现状

- 后端流式入口：`app/api/agent.py` 的 `POST /agent/query/stream`。
- 前端流式入口：`app/frontend/static/app.js` 的 `streamAgentQuery()`。
- 当前 SSE 事件包括 `token`、`metadata`、`done`、`error`、`agent_step`、`tool_call_start`、`tool_call_result`。
- 当前前端因 POST body 和自定义 header 需要使用 `fetch + response.body.getReader()` 手动解析 SSE，而不是原生 `EventSource`。
- 当前 citation 渲染通过 `renderAnswerWithCitationLinks()` 和 `citationReferenceHtml()` 把 `[N]` 转成来源按钮。
- 当前 Markdown 能力很小，只支持 `**bold**` 的 inline 渲染；阶段 40 不引入运行时 CDN Markdown/Sanitize 依赖。

## 四条主线

### 1. Markdown sanitize

最终写入 DOM 的回答 HTML 必须经过本地 sanitizer。安全目标：

- 剥离 `<script>`、`<iframe>`、`<object>`、`<embed>`、`<style>` 等危险标签。
- 剥离 `onclick`、`onerror`、`onload` 等事件属性。
- 剥离或禁用 `javascript:`、`data:text/html` 等危险 URL。
- 保留本项目需要的安全展示能力：纯文本、换行、`<strong>`、citation button、citation popover、基础状态 badge。
- 不依赖运行时 CDN；若使用第三方 sanitizer，必须 vendored 或作为本地依赖可控引入。

新词解释：

- sanitize：对不可信 HTML 做清洗，删除脚本、事件属性和危险链接。本项目用于模型输出进入 `.innerHTML` 前的最后一道防线。
- XSS：跨站脚本攻击。LLM 输出可能被提示词诱导写出危险 HTML，如果页面直接执行，就会变成 XSS 入口。

面试表达：

```text
我不会把模型输出直接塞进 innerHTML。即使当前 Markdown 能力很小，也把“渲染前 sanitize”固定成统一出口，避免后续扩展 Markdown 时埋下 XSS 风险。
```

### 2. AbortController 停止生成

`streamAgentQuery()` 必须创建或接收 `AbortController`，并把 `signal` 传给 `fetch`。运行中 UI 展示“停止生成”按钮，点击后调用 `abort()` 中断浏览器侧 SSE 读取。

前端合同：

- 请求进行中才能显示或启用停止按钮。
- 停止后必须把状态收敛为可继续提问。
- 停止后不走同步 `/agent/query` fallback，因为用户明确选择停止。
- 停止不应删除 user 消息，也不应删除已收到的 assistant token。

后端边界：

- FastAPI `StreamingResponse` 在客户端断开后通常会停止继续向 socket 写入。
- 当前 `stream_non_chitchat_agent_response()` 使用 producer thread 和 queue。浏览器 abort 能中断前端读取，但如果 provider 调用已经在后台线程中执行，未必能立刻取消底层 provider 请求。
- 阶段 40 尽量检测客户端断开；如果当前 provider/producer 无法被浏览器 abort 立即终止，必须在文档和汇报中诚实记录，不伪造成完全后端取消。

新词解释：

- AbortController：浏览器原生取消控制器，`controller.signal` 传给 `fetch` 后，调用 `controller.abort()` 可以中断请求。

面试表达：

```text
停止生成分两层：浏览器侧 abort 立即停止读取和渲染；后端侧是否能取消真实模型调用取决于 provider 是否支持取消。我会把两者分开说明，不把前端停止伪造成模型已完全停止计费或执行。
```

### 3. 中断后半截内容保留

用户点击停止生成后，已经收到的 token 必须保留在当前 assistant 气泡里，并追加状态标记，例如“已停止生成”。这条主线解决的是用户体验一致性：停止是“停在这里”，不是“抹掉刚才生成的内容”。

前端合同：

- half answer 继续作为 assistant 消息存在于页面内。
- 气泡状态从 thinking/running 收敛为 aborted。
- 状态文案可见，例如“已停止生成”。
- 停止后 `state.agentRequestInFlight` 必须回到 `false`，允许继续发送新问题。

是否写入数据库：

- 当前后端只在完整 `metadata` 后持久化 conversation messages。
- 浏览器主动 abort 时通常不会收到 metadata，因此阶段 40 优先保证当前页面状态保留；是否把半截回答写入后端会话，需要后续单独设计 API，不在本阶段强行扩展。

### 4. Token 渲染节流

当前 `onToken` 每收到一个 token 就更新 DOM，并等待两帧 paint。阶段 40 改成 token buffer：

- `token` 事件先进入内存 buffer。
- 使用 `requestAnimationFrame` 或 16-50ms 定时 flush 合并 DOM 更新。
- `metadata`、`done`、`error`、`abort` 到达时必须 flush 剩余 token。
- 保持最终 citation 渲染不丢失：metadata 到达后仍以完整 answer + sources/citations 做最终渲染。

新词解释：

- requestAnimationFrame：浏览器在下一帧绘制前执行回调的 API，适合把多次 DOM 写入合并到一帧。
- token buffer：把流式 token 先暂存在数组或字符串里，再按帧批量写入页面，减少 reflow/repaint。

面试表达：

```text
流式输出不是 token 来一个就写一次 DOM。高频 DOM 写入会拖慢页面，所以我用 buffer 和 requestAnimationFrame 合并更新，同时在 done/error/abort 时强制 flush，保证内容不丢。
```

## 安全边界

阶段 40 严格不做：

- 不做长回答虚拟列表或分段虚拟渲染。
- 不改变检索策略、prompt 策略、Stage 30 评分规则。
- 不改变 embedding/rerank/chat provider 拓扑。
- 不新增外部数据源或语料库。
- 不做登录系统。
- 不做部署优化。
- 不把 deterministic `citation_validator` 或 Judge 接入生产链路。

所有新增代码、CSV、文档、测试和 Obsidian 草稿都不得写入：

- API key
- Bearer token
- Authorization header
- raw provider response
- `reasoning_content`
- hidden thought
- 完整 chunk 全文
- 受限全文

## 测试合同

阶段 40 至少覆盖：

- sanitize：危险标签、事件属性、`javascript:` URL 不进入最终回答 DOM；合法 citation button 和 `<strong>` 保留。
- 停止生成 UI：运行中存在“停止生成”按钮或等价控制；停止后按钮状态收敛。
- 中断保留：abort 后已收到 token 保留，并出现“已停止生成”状态。
- token 节流：token 不直接逐个写 DOM，而是经过 buffer scheduler；metadata/done/error/abort 强制 flush。
- SSE 兼容：既有 `token`、`metadata`、`done`、`error`、`agent_step`、`tool_call_start`、`tool_call_result` 事件继续兼容。
- 入口回归：`POST /agent/query/stream`、`POST /agent/query`、`POST /chat`、`GET /` 不被破坏。

阶段收尾验证：

```text
node --check app/frontend/static/app.js
python -m pytest tests/test_stage40_streaming_output_safety.py tests/test_frontend_app.py tests/test_agent_stream_api.py -q
python -m pytest -q
browser smoke desktop + 390x844 mobile
```

真实 provider 和生产 smoke 只允许在显式人工验证命令中运行，不作为 CI 或本地全量 pytest 前提。

## 完成标准

- `docs/stage40_streaming_output_safety.md` 已新增并说明目标、输入、四条主线、安全边界、验证方式和完成标准。
- 前端最终渲染前具备 sanitize 防护，能剥离危险标签、事件属性和危险 URL。
- `streamAgentQuery` 使用 `AbortController.signal`；运行中有“停止生成”按钮；点击后前端中断 SSE 读取。
- 用户停止生成后，已收到 token 保留在 assistant 消息中，并显示“已停止生成”状态；停止后可以继续发送新问题。
- 前端 token 渲染采用 buffer + `requestAnimationFrame` 或 16-50ms flush 节流；metadata/done/error/abort 时 flush 剩余 token。
- 后端取消能力边界已在文档和汇报中诚实记录。
- 既有入口不被破坏。
- 阶段 40 聚焦测试、前端语法检查、浏览器 smoke 和必要全量测试完成。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-40.md` 与 Obsidian 草稿完成。
- 最终不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，停在用户人工核验前状态。

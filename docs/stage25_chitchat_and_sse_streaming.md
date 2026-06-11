# 阶段 25：闲聊短路 + SSE 流式输出

## 目标

阶段 24 已把 Agent 面板升级为服务端持久化多轮会话。阶段 25 在此基础上做两件体验层增强：

```text
用户输入
-> /agent/query 或 /agent/query/stream
-> 路由层闲聊短路
-> 非闲聊问题继续走 default / agentic RAG
-> 生成阶段支持流式 token
-> 前端逐 token 追加到助手气泡
-> 流结束回填 metadata 并持久化会话消息
```

本阶段的重点不是改变 RAG 检索质量，而是让“明显不需要检索的问题”更快返回，让“需要生成的回答”更早出现在前端。

## 范围

本阶段做：

- 新增 `app/services/agent/chitchat.py`，在 API 路由层统一识别 `greeting`、`thanks`、`goodbye`、`acknowledgment`、`help` 五类社交意图。
- 在 `/agent/query` 中把闲聊短路放在 `classify_query_complexity()` 之前，命中后不调用 LLM、不检索。
- 从 `AgentService.detect_intent()` 移除已提升的 `greeting` 分支，让 default Agent 继续只负责 answer/search/list_sources/get_source_detail。
- `ChatModelProvider` Protocol 新增 `stream_generate(messages) -> Iterator[str]`。
- `OpenAICompatibleChatModelProvider` 使用 `stream=true` 调用兼容 `/chat/completions` 接口，解析 SSE `delta.content`。
- `DeterministicChatModelProvider` 按段 yield 完整回答，保证自动测试不依赖真实 API。
- 新增 `POST /agent/query/stream`，返回 `StreamingResponse(media_type="text/event-stream")`。
- 前端 `submitAgent()` 使用 `fetch()` + `ReadableStream` 消费 SSE，实现打字机效果。
- 流完成后复用阶段 24 的会话持久化和摘要压缩。
- 同步测试、README、进度、架构、数据来源和 Obsidian 草稿。

本阶段不做：

- 不做 WebSocket 双向通道。
- 不做用户认证/登录。
- 不引入 React/Vue 或 Node 构建链。
- 不新增写入型 Agent 工具。
- 不做跨会话长期记忆。
- 不改变 `/chat` 的单次引用式问答边界。
- 不让真实 API 成为 CI 或本地全量测试前提。

## 闲聊短路设计

阶段 24 的问候识别位于 `AgentService.detect_intent()` 内部，只覆盖 default Agent 路径。阶段 25 将它提升到 `app/api/agent.py` 路由入口：

```text
POST /agent/query
-> load conversation history if conversation_id exists
-> detect_chitchat(question)
   hit  -> AgentQueryResponse(answer=预设友好回复, mode="default")
   miss -> classify_query_complexity(question)
           -> default AgentService 或 agentic RAG
```

识别结果使用冻结 dataclass：

```python
ChitchatResult(
    intent="greeting" | "thanks" | "goodbye" | "acknowledgment" | "help",
    answer="预设中文友好回复",
    reasoning_summary="识别为闲聊短路 ..."
)
```

匹配策略：

- 对用户输入做 `strip()`、`casefold()` 和标点/空白压缩。
- greeting：`你好`、`您好`、`嗨`、`hi`、`hello`、`hey`、`早上好`、`下午好`、`晚上好`。
- thanks：`谢谢`、`感谢`、`thanks`、`thank you`。
- goodbye：`再见`、`拜拜`、`bye`、`goodbye`。
- acknowledgment：`好的`、`好`、`明白了`、`知道了`、`ok`、`okay`。
- help：`帮帮我`、`怎么用`、`help`、`你能做什么`、`使用帮助`。

命中闲聊时：

- 不调用 `classify_query_complexity()`。
- 不实例化 default `AgentService` 执行工具。
- 不调用 `run_agentic_rag()`。
- 不调用 ChatModelProvider。
- 不检索 `documents/chunks/chunk_embeddings`。
- 如果请求带 `conversation_id`，仍保存 user/assistant 两条消息，方便前端刷新后看到完整会话。
- 闲聊消息不触发摘要压缩，避免一串“你好/谢谢”污染 summary。

## ChatModelProvider 流式协议

现有接口：

```python
def generate(messages: Sequence[ChatMessage]) -> ChatModelResult
```

阶段 25 新增：

```python
def stream_generate(messages: Sequence[ChatMessage]) -> Iterator[str]
```

约束：

- `stream_generate()` 只 yield 文本增量，不 yield provider 原始响应。
- 调用方负责把所有片段拼接成最终 `answer`。
- provider 和 model 名称仍从 `provider_name` / `model_name` 属性读取。
- 真实 provider 失败时抛出 `RuntimeError`，API 层转换为 SSE `error` 或同步 503。

`OpenAICompatibleChatModelProvider.stream_generate()`：

```text
payload = {
  "model": model_name,
  "messages": [...],
  "temperature": temperature,
  "stream": true
}
```

响应解析：

- 逐行读取响应体。
- 忽略空行和非 `data:` 行。
- `data: [DONE]` 表示模型端流结束。
- JSON 行读取 `choices[0].delta.content`。
- content 是非空字符串时 yield。
- 不保存 `raw_response`，不向前端暴露供应商原始响应。

`DeterministicChatModelProvider.stream_generate()`：

- `generate()` 用于同步 JSON 端点，仍返回完整答案。
- `stream_generate()` 用于 SSE 端点，按空白和中英文标点切成稳定片段。
- yield 片段时保留原始顺序，拼接后必须等于 `generate().answer`。

## `/agent/query/stream` SSE 端点

新增端点与同步端点并行存在：

```text
POST /agent/query         -> application/json
POST /agent/query/stream  -> text/event-stream
```

这样可以完全保留阶段 24 的同步 JSON 契约，避免旧前端、测试或脚本因 content type 改变而破坏。

SSE 事件格式：

```text
event: token
data: {"text":"堆石混凝土"}

event: metadata
data: {"question":"...","answer":"...","citations":[],"mode":"default",...}

event: done
data: {}

event: error
data: {"detail":"chat model provider is unavailable or timed out"}
```

事件含义：

- `token`：增量正文，前端追加到当前助手气泡。
- `metadata`：完整 `AgentQueryResponse` JSON，用于回填 citations、sources、mode、workflow_steps、invalid_citations、refusal_category。
- `done`：流正常结束，前端解锁输入并刷新会话列表。
- `error`：流过程中出错，前端显示错误气泡；出错时不持久化不完整助手消息。

流式端点处理顺序：

```text
1. 校验 conversation_id 并加载 history。
2. detect_chitchat(question)。
3. 闲聊命中：发送 token -> metadata -> done，保存完整消息，跳过摘要。
4. 非闲聊：按 mode / classify_query_complexity 选择 default 或 agentic。
5. 检索、grade、rewrite 等非生成步骤同步执行。
6. generate 阶段通过 `QueueStreamingChatModelProvider` 调用 `stream_generate()`，每个 token 进入队列后立即由 SSE generator 发送。
7. token 拼接完成后构造 AgentQueryResponse。
8. 发送 metadata 和 done。
9. 如果 conversation_id 存在，保存 user/assistant 消息并触发摘要压缩。
```

错误策略：

- 请求参数错误在进入 generator 前仍可返回普通 HTTP 400。
- generator 内部错误发送 `event: error`，并停止后续 token/metadata/done。
- 不把 API key、Bearer token、Authorization header、供应商原始响应写进 error data。

## default 路径流式策略

default Agent 当前通过 `AgentService.query()` 调用 `AgentToolbox.answer_with_citations()`，最终由 Brain workflow 调用 `chat_model_provider.generate()`。

阶段 25 的实现避免复制完整 Agent 工具逻辑。最终实现让流式端点在 default answer 场景中：

```text
后台生产者线程执行现有 AgentService / Brain 前置步骤
-> Brain workflow 仍调用 chat_model_provider.generate()
-> QueueStreamingChatModelProvider.generate() 内部消费 base_provider.stream_generate()
-> 每个 token 放入队列，SSE generator 立即 yield token event
-> 拼接 answer
-> extract citations / refusal metadata
-> AgentQueryResponse
```

这样现有同步业务代码不用大改，但用户不再等完整 `AgentQueryResponse` 构造完才看到第一段文本。

对于 source detail、list sources、search-only 等不需要模型生成的 default 意图，可以直接将完整 answer 作为一个或少量 `token` 事件发送，然后回填 metadata。这样保持产品上的“流式接口可用”，同时不为非生成工具制造伪 token 复杂度。

## agentic 路径流式策略

agentic 图当前节点为：

```text
retrieve -> grade -> rewrite/re_retrieve -> generate -> citation_check
```

阶段 25 不把整个 LangGraph 执行变成异步流。原因：

- retrieve/grade/rewrite 的输出是内部状态，不适合作为用户正文。
- citation_check 需要完整 answer 后才能判断无效引用。
- 直接改 LangGraph 节点为 iterator 会显著扩大风险。

阶段 25 最终实现：

```text
后台生产者线程调用 run_agentic_rag(...)
-> 复用 retrieve_node / grade_node / rewrite_node / re_retrieve_node 的同步逻辑
-> 到 generate 节点时，QueueStreamingChatModelProvider.generate() 消费 stream_generate()
-> 每个 token 放入队列，SSE generator 立即 yield token event
-> 完整 answer 后执行 citation_check 逻辑
-> 返回 AgenticResult
```

自动测试应覆盖 agentic stream 至少在 deterministic provider 下能产生 `token -> metadata -> done`，且 metadata 中 `workflow_steps`、`iteration_count`、`citations`、`invalid_citations` 与同步结果语义一致。

## 会话持久化与摘要

阶段 24 的持久化函数：

```python
persist_agent_conversation_messages(...)
```

阶段 25 可以新增参数控制摘要：

```python
persist_agent_conversation_messages(..., summarize: bool = True)
```

规则：

- 同步 `/agent/query`：非闲聊仍保持原摘要行为；闲聊命中时保存消息但 `summarize=False`。
- 流式 `/agent/query/stream`：只有正常完成并已构造完整 `AgentQueryResponse` 后才持久化。
- 流中断或 error：不保存 assistant 半成品；如果用户消息已经乐观渲染在前端，也只作为前端临时状态，不进入数据库。
- metadata 继续复用 `assistant_metadata_from_response()`，不保存供应商原始敏感响应。

## 前端消费设计

`EventSource` 只支持 GET，不适合本项目的 POST 请求体。因此前端使用：

```text
fetch("/agent/query/stream", { method: "POST", body: JSON.stringify(body) })
-> response.body.getReader()
-> TextDecoder
-> 手动解析 event/data 行
```

解析要求：

- 支持一个 SSE event 被拆到多个 network chunk。
- `data:` 可能为空对象 `{}`。
- JSON parse 失败时抛出可理解错误，并 fallback 到同步 `/agent/query`。
- token 追加使用 `textContent` 或文本节点，不用 `innerHTML`。
- metadata 到达后复用 `agentAnswerHtml()` 或拆出 metadata 渲染 helper，更新同一个助手气泡底部。

交互要求：

- 用户提交后立即追加 user 气泡。
- 助手气泡先显示“正在思考...”。
- 第一个 token 到达时清空提示并替换为正文。
- token 持续追加时自动滚动到底部。
- `metadata` 到达后展示 mode、iterations、citations、sources、refusal_category。
- `done` 到达后解锁输入、刷新会话列表。
- `error` 到达或网络失败时展示错误气泡并复位 mode 状态。

## 测试方案

新增或更新测试：

```text
tests/test_agent_chitchat.py
tests/test_chat_model_streaming.py
tests/test_agent_stream_api.py
tests/test_agent_api.py
tests/test_frontend_app.py
tests/test_agentic_graph.py
```

重点断言：

- 五类闲聊意图均在 `/agent/query` 路由层短路。
- 闲聊不调用检索、不调用 ChatModelProvider、不触发 complexity routing。
- `AgentService.detect_intent()` 不再返回 `greeting`。
- deterministic `stream_generate()` 拼接结果等于 `generate().answer`。
- OpenAI-compatible SSE delta 解析能处理 `data: [DONE]`、空 delta、content delta。
- `/agent/query/stream` 事件顺序稳定：`token... -> metadata -> done`。
- error 事件不泄露 API key 或供应商原始响应。
- 有 `conversation_id` 的流式完成后会保存 user/assistant 消息。
- 前端包含 `ReadableStream` / `getReader()` SSE 消费逻辑，不再对 Agent 主路径只等完整 JSON。
- 旧 `/agent/query`、`/search`、`/search/vector`、`/search/hybrid`、`/chat`、`/quality-report` 仍通过回归。

全量验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

目标不少于阶段 24 基线：

```text
483 passed
```

浏览器验证：

- 桌面视口：闲聊问题立即返回，console error 为 0。
- 桌面视口：普通 RAG 问题逐 token 输出，metadata 回填引用与 mode。
- 移动视口：聊天气泡和会话栏不横向溢出，流式输出不遮挡输入区。

## 安全边界

- 闲聊回复为预设文本，不调用模型。
- SSE `token` 只包含面向用户的回答文本。
- SSE `metadata` 复用脱敏后的 `AgentQueryResponse`。
- 不暴露 `raw_response`。
- 不保存 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文。
- 真实 API 只允许运行时调用，不作为 CI 或本地全量测试前提。
- 前端动态内容继续使用 `escapeHtml()` 或文本节点。

## 完成标准

- 本设计文档就位。
- `app/services/agent/chitchat.py` 就位，路由层短路五类社交意图。
- `ChatModelProvider` 支持 `stream_generate()`，deterministic 可测试。
- `/agent/query/stream` 可用，事件格式稳定。
- 前端实现打字机效果，流结束后元数据正确展示。
- `/agent/query` 同步 JSON 契约完全保留。
- `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`GET /quality-report` 不被破坏。
- 全量测试通过，数量不低于阶段 24 基线。
- 浏览器桌面/移动验证通过。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、必要的 `AGENT.MD` 和 Obsidian 已同步。
- 不提交、不创建 `phase-25-complete` tag、不推送、不创建 PR，停在用户人工核验前。

## 新词解释与面试表达

- **闲聊短路**：系统识别到“你好”“谢谢”“再见”这类不需要资料库的问题时，直接返回预设回复。在本项目里放在 `/agent/query` 路由层，避免浪费检索和模型调用。
- **SSE**：Server-Sent Events，服务端向浏览器单向推送文本事件。本项目用它让 Agent 回答逐段出现，但不做 WebSocket 那种双向实时通道。
- **token**：这里指模型输出的一小段文本，不一定是严格的模型 tokenizer 单位。前端收到一个 token 就追加一点回答。
- **metadata**：流结束后补充的结构化信息，例如引用、来源、mode、workflow steps 和拒答分类。它不包含供应商原始响应或凭据。
- **ReadableStream**：浏览器 fetch 返回体的流式读取接口。本项目用它读取 POST SSE，因为 `EventSource` 只能发 GET。

面试表达：

```text
阶段 25 我没有把所有请求都直接扔进 RAG，而是在 /agent/query 路由层先做闲聊短路，覆盖问候、感谢、告别、确认和帮助意图。命中后不走复杂度分类、不检索、不调用模型，只返回友好引导，既省成本也避免 agentic 路径误处理寒暄。

流式输出上，我保留原 /agent/query 的 JSON 契约，新开 /agent/query/stream 返回 text/event-stream。Provider 层新增 stream_generate，真实 OpenAI-compatible provider 解析 delta.content，deterministic provider 用分段 yield 保证测试稳定。前端不用 EventSource，而是 fetch + ReadableStream 手动解析 POST SSE；token 事件更新正文，metadata 事件回填引用、mode 和 workflow，done 事件结束。这样既改善用户等待体验，又不破坏旧 API 和阶段 24 的会话持久化。
```

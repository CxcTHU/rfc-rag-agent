# 阶段 24：多轮对话 UI 与会话持久化

## 目标

阶段 23 已经让 `/agent/query` 在未传 `mode` 时自动选择 default 或 agentic 链路，并让前端只读展示本次实际模式。阶段 24 在此基础上补齐真正的多轮对话能力：

```text
Conversation + Message 持久化
-> /conversations 会话管理 API
-> /agent/query 接收 conversation_id
-> 自动加载历史并持久化用户/助手消息
-> 长对话摘要压缩
-> 前端聊天气泡 UI
-> 会话列表、新建、切换、删除、刷新恢复
```

本阶段的核心不是做一个新的问答模型，而是把已经稳定的 RAG Agent 入口变成可持续使用的对话工作台。

## 当前局限

`AgentQueryRequest.history` 已经存在，但它只是一次请求里的可选数组：

- 由客户端传入，服务端不保存。
- 前端阶段 23 还没有维护该字段。
- 刷新页面后历史丢失。
- `run_agentic_rag()` 目前不接收 history。
- 没有会话分组，`qa_logs` 只是扁平问答日志，不能还原一组对话。

阶段 24 保留该字段的向后兼容能力，但新增服务端会话持久化作为默认前端体验。

## 范围

本阶段做：

- 新增 `Conversation` 和 `Message` 数据模型。
- 新增 `/conversations` 会话 CRUD API。
- `/agent/query` 新增可选 `conversation_id`。
- 传入 `conversation_id` 时，自动加载历史、调用 default/agentic 链路、追加 user/assistant 消息。
- agentic 路径扩展 `history` 参数，在 generate 节点利用历史。
- 长对话超过阈值后自动生成 summary 消息，历史装配使用“最新摘要 + 近期消息”。
- 前端 Agent 面板改为聊天气泡列表，消息追加渲染。
- 前端支持新建、切换、删除会话，页面刷新后恢复最近会话。
- 补充测试、普通文档和 Obsidian 草稿。

本阶段不做：

- 不做 WebSocket/SSE 流式输出。
- 不做用户认证或登录系统。
- 不做跨会话长期记忆。
- 不做 RAG over 历史对话。
- 不引入 LangGraph Checkpointer。
- 不引入 React/Vue 或 Node 构建链。
- 不新增爬虫或外部资料来源。
- 不让真实 API 成为 CI 或本地全量测试前提。

## 数据模型

### Conversation

`Conversation` 表表示一组对话。

```text
id          Integer primary key
title       String(200)
created_at  DateTime
updated_at  DateTime
```

设计约束：

- `title` 默认使用第一条用户消息的前若干字符。
- 每次追加消息时更新 `updated_at`，列表按 `updated_at desc` 排序。
- 阶段 24 不引入用户表，所有会话先属于本地应用实例。

### Message

`Message` 表表示会话中的一条消息。

```text
id               Integer primary key
conversation_id  ForeignKey(conversations.id, ondelete="CASCADE")
role             String(20): user / assistant / summary
content          Text
mode             String(20), nullable: default / agentic
metadata_json    Text, nullable
created_at       DateTime
```

`metadata_json` 用于保存助手消息的可观测展示数据，例如：

```json
{
  "citations": ["[1]"],
  "sources": [],
  "workflow_steps": [],
  "iteration_count": 0,
  "invalid_citations": [],
  "refusal_category": null,
  "refused": false,
  "refusal_reason": null
}
```

不把这些字段拆成单独列，是因为 workflow steps 和 citations 都是变长结构；前端需要原样还原展示，JSON 更适合作为展示元数据。

## 会话 API

新增 `app/api/conversations.py`，路由前缀为 `/conversations`。

```text
POST /conversations
  创建新会话，返回 id、title、created_at、updated_at。

GET /conversations
  列出最近会话，默认按 updated_at desc。

GET /conversations/{conversation_id}/messages
  返回指定会话和全部消息。

DELETE /conversations/{conversation_id}
  删除会话，并级联删除消息。
```

异常策略：

- 会话不存在返回 404。
- 删除已不存在的会话返回 404。
- 创建时 title 为空则使用默认标题。
- 列表接口不返回敏感 metadata 之外的数据；阶段 24 没有用户权限模型。

## `/agent/query` 集成

`AgentQueryRequest` 新增：

```python
conversation_id: int | None = None
```

处理逻辑：

```text
if conversation_id is None:
    保持阶段 23 行为不变
else:
    读取 conversation
    组装 history = latest_summary + recent_messages
    结合 request.history 中的显式历史（如果有）时，服务端会话历史优先
    根据阶段 23 mode/auto-routing 选择 default 或 agentic
    调用对应链路
    追加 user Message
    追加 assistant Message
    更新 conversation.updated_at 和必要 title
    检查是否需要摘要压缩
```

向后兼容要求：

- 不传 `conversation_id` 时不写入 `Conversation` / `Message`。
- 显式 `mode=default` / `mode=agentic` 继续尊重。
- 未传 `mode` 时继续使用阶段 23 的 `classify_query_complexity()`。
- `POST /chat` 不在本阶段接入持久化，避免扩大变更面。

## agentic history 策略

阶段 24 不改变 LangGraph 节点结构，不引入 Checkpointer。只扩展：

```python
run_agentic_rag(..., history: list[str] | None = None)
```

`AgenticState` 增加 `history` 字段，generate 节点在调用 `BrainService` 或生成 prompt 时传入历史。retrieve / grade / rewrite 仍以当前问题为主，避免把历史对话变成跨会话长期记忆或历史 RAG。

## 上下文摘要压缩

触发规则：

- 非 summary 消息数超过 16 条时触发。
- 保留最近 6 条非 summary 消息。
- 被压缩范围包括更早的 user/assistant 消息，以及已有最新 summary。

摘要存储：

```text
role = "summary"
content = 摘要文本
mode = null
metadata_json = {"summary_of_message_ids": [...]} 或最小可测试元数据
```

历史装配：

```text
latest summary message
-> messages created after latest summary
-> 转为 history list[str]
```

摘要实现要求：

- 摘要函数接受 `chat_model_provider`，测试可使用 deterministic provider。
- 摘要文本只保留任务、约束、用户偏好和已给出的关键结论。
- 不写入 API key、Bearer token、供应商原始响应或受限全文。
- 被摘要的旧消息保留在数据库中，但默认不再进入 prompt。

## 前端聊天 UI

Agent 面板从“单次结果覆盖”改为“消息列表追加”：

```text
会话工具栏：新建 / 刷新 / 删除 / 当前模式状态
会话列表：最近会话
聊天区：user 气泡 + assistant 气泡
输入区：textarea + 提交按钮
诊断区：当前助手消息的 workflow steps / tool calls
```

渲染规则：

- 用户提交后立即追加 user 气泡。
- 响应成功后追加 assistant 气泡。
- 响应失败时追加错误状态或恢复输入状态，并修复阶段 23 “判断中”不复位的小问题。
- 自动滚动到最新消息。
- 切换会话时清空当前消息列表并按 API 返回重建。
- 刷新页面时自动加载最近会话；没有会话则创建新会话。

助手气泡保留阶段 22/23 的可观测信息：

- `mode`
- `iteration_count`
- `workflow_steps`
- `citations`
- `invalid_citations`
- `refusal_category`
- `refused` / `refusal_reason`

所有动态 HTML 必须继续通过 `escapeHtml()`。

## 安全边界

- `Message.metadata_json` 不保存 credentials、Bearer token、Authorization header、供应商原始敏感响应或受限全文。
- 会话删除使用级联删除消息，避免孤儿消息。
- 前端只展示 API 返回的脱敏字段。
- 摘要内容只来自用户和助手消息，不读取外部未授权资料。
- 阶段 24 不改变 source registry、documents、chunks、chunk_embeddings 的资料边界。
- 自动摘要不作为质量评测数据写入 CSV。

## 测试方案

新增测试建议：

```text
tests/test_conversation_repository.py
tests/test_conversations_api.py
tests/test_agent_conversation_api.py
tests/test_conversation_summary.py
tests/test_agentic_history.py
tests/test_frontend_app.py
```

重点覆盖：

- Conversation / Message 创建、追加、查询、删除和级联删除。
- `/conversations` 四个端点正常和异常路径。
- `/agent/query` 有 `conversation_id` 时持久化 user/assistant 消息。
- `/agent/query` 无 `conversation_id` 时行为不变。
- default 和 agentic 路径都能接收 history。
- 超过 16 条消息后生成 summary，历史装配只包含最新 summary 和近期消息。
- 前端不覆盖旧消息，使用聊天气泡追加。
- 前端会话新建、切换、删除、刷新恢复相关静态行为。
- `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 回归不破坏。

全量验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

目标：全量测试通过，数量不低于阶段 23 基线 463。

## 完成标准

- `docs/stage24_multi_turn_conversation.md` 就位。
- 新增 `Conversation` 和 `Message` 模型，支持会话级消息分组、持久化和级联删除。
- 新增 `/conversations` 四个端点，测试覆盖正常和异常路径。
- `/agent/query` 支持可选 `conversation_id`，不传时行为不变。
- agentic 路径支持 `history` 参数，并在 generate 节点利用历史。
- 上下文摘要压缩在长对话时自动触发，summary 消息和历史装配正确。
- 前端 Agent 面板改为聊天气泡列表，保留 mode/workflow/citations/refusal 展示。
- 前端支持会话列表、新建、切换、删除和刷新恢复。
- 动态 HTML 使用 `escapeHtml()`。
- 全量测试通过，且不依赖真实 API。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、必要的 `AGENT.MD` 和 Obsidian 本地知识库同步。
- 最终不提交、不创建 `phase-24-complete` tag、不推送、不建 PR，停在用户人工核验前。

## 新词解释与面试表达

- **Conversation**：会话，一组连续问答的容器。在本项目里对应 `conversations` 表；面试时可以说，它解决了多轮对话的分组、列表和刷新恢复问题。
- **Message**：消息，会话里的一条用户、助手或摘要记录。在本项目里对应 `messages` 表；面试时可以说，它让前端能按顺序还原聊天历史。
- **级联删除**：删除会话时自动删除该会话下所有消息。在本项目里用外键关系保护数据一致性；面试时可以说，它避免产生没有归属的孤儿消息。
- **上下文摘要压缩**：把较旧的多轮历史压缩成一条 summary 消息，只把摘要和近期消息送进 LLM。在本项目里用于控制 prompt 长度；面试时可以说，这是轻量版 ConversationSummaryBufferMemory，但没有引入额外框架依赖。
- **向后兼容**：新字段可选，旧调用不传也能按原行为运行。在本项目里 `/agent/query` 不传 `conversation_id` 时保持阶段 23 行为；面试时可以说，新能力不会破坏已有 API 客户端。

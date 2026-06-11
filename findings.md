# 阶段 24 发现与关键决策

## 启动校准发现

- 当前阶段目标：阶段 24「多轮对话 UI 与会话持久化」。
- 目标分支：`codex/phase-24-multi-turn-conversation`。
- 阶段 23 最终功能提交：`dd7d953 Complete phase 23 agentic eval and auto routing`。
- 阶段 23 合并提交：`8fc1cfa Merge phase 23 agentic eval and auto routing`。
- `phase-23-complete` tag 指向 `dd7d953`，已确认未移动。
- `main` 与 `origin/main` 均指向 `8fc1cfa`，且 `phase-23-complete` 是两者祖先；阶段 24 可以从正确基线启动。
- 阶段 23 验收结论：PASS（2026-06-11 Claude 独立验收，463 passed，evaluation decision=reliable_auto_route_candidate）。

## 当前 history 字段现状

位置：`app/schemas/agent.py`

- `AgentQueryRequest.history` 是 `list[str]`，由前端传入，最大 50 条。
- 经过 `history_items_must_not_be_blank` 验证器清洗空白条目。
- 流向：`/agent/query` → `AgentService.query(history=...)` → `answer_with_citations(history=...)` → `CitationAnswerService.answer(history=...)`。
- **局限**：
  - 前端目前没有维护 history——`submitAgent()` 不传 history 字段。
  - 服务端不持久化历史，刷新页面全部丢失。
  - agentic 路径（`run_agentic_rag()`）不接受 history 参数。
  - 没有会话分组，所有问答都是独立的。

## 当前数据库模型

位置：`app/db/models.py`

- 已有表：`documents`、`sources`、`chunks`、`chunk_embeddings`、`qa_logs`。
- `QuestionAnswerLog` 是扁平问答日志，没有 conversation_id 或 session 分组。
- 没有 `Conversation` 或 `Message` 表。
- SQLAlchemy 使用 `DeclarativeBase`，`Base.metadata.create_all` 自动建表。

## 当前前端 Agent 面板

位置：`app/frontend/index.html`、`app/frontend/static/app.js`

- 单次问答模式：用户提交 → 覆盖 `data-agent-answer-box` → 覆盖 `data-agent-tools-list`。
- 无聊天历史列表、无气泡布局、无会话切换。
- `renderAgentAnswer(result)` 每次替换整个 answer box 的 innerHTML。
- `renderAgentWorkflowSteps()` 和 `renderAgentToolCalls()` 每次替换整个 tools list。
- 阶段 22/23 的可观测字段（mode badge、iteration badge、citation 无效标记、refusal_category）都在 `renderAgentAnswer()` 中渲染，需要在聊天气泡中保留。

## 当前 agentic 路径与 history

位置：`app/services/agentic/graph.py`、`app/services/agentic/state.py`

- `run_agentic_rag(question, db, embedding_provider, chat_model_provider)` 不接受 history 参数。
- `AgenticState` 中没有 history 字段。
- 阶段 24 需要决定：是否让 agentic 路径也利用对话历史？
- **决策**：agentic 路径的 generate 节点在调用 LLM 时可以把历史拼入 system/user prompt，但不改变图的结构（retrieve/grade/rewrite 仍基于当前问题）。实现方式：`run_agentic_rag()` 新增可选 `history` 参数，传入 generate_node 用于生成上下文。

## LangChain Checkpoint vs 自建方案决策

- **LangGraph Checkpointer** 的核心能力是持久化图的中间状态，支持断点续跑和时间旅行回放。
- 本项目当前 agentic 图（6 个节点、MAX_ITERATIONS=3）几秒内跑完，断点续跑价值不大。
- **ConversationSummaryBufferMemory** 的策略（保留最近 N 轮 + 旧轮摘要）是正确方向，但自建实现不到 50 行，不需要引入 LangChain memory 依赖。
- **决策**：自建轻量会话持久化 + 摘要压缩，不引入 LangGraph Checkpointer 或 LangChain Memory 类。

## 会话模型设计决策

### Conversation 表
- `id`: Integer PK
- `title`: String(200)，默认用第一条用户消息的前 40 字符
- `created_at`: DateTime UTC
- `updated_at`: DateTime UTC（每次追加消息时更新）

### Message 表
- `id`: Integer PK
- `conversation_id`: FK → conversations.id, CASCADE 删除
- `role`: String(20)，枚举值 `user` / `assistant` / `summary`
- `content`: Text，消息正文
- `mode`: String(20) nullable，`default` / `agentic` / null（user 消息和 summary 为 null）
- `metadata_json`: Text nullable，JSON 格式存储 assistant 消息的结构化信息（workflow_steps、citations、invalid_citations、refusal_category、iteration_count、refused、refusal_reason）
- `created_at`: DateTime UTC

### 为什么用 metadata_json 而不是单独列
- workflow_steps 是变长结构化数据，不适合关系列。
- 前端需要完整还原每条助手消息的展示状态（mode、citations、workflow steps），JSON 存储最灵活。
- 读取时 JSON parse，写入时 JSON dump。
- 不在 metadata_json 中存储 API key、token 或供应商原始响应。

## 上下文摘要压缩策略

- **阈值**：当会话的非摘要消息数超过 16 条（约 8 轮对话）时触发摘要。
- **摘要范围**：从第 1 条消息到倒数第 6 条消息（保留最近 3 轮不被摘要）。
- **摘要方式**：用 LLM 将被摘要消息压缩为一段中文文本（200-400 字），存为 `role="summary"` 的 Message。
- **历史装配**：最新的 summary 消息 + summary 之后的所有消息 → 组装为 history 传入 LLM。
- **渐进摘要**：如果后续对话又超过阈值，在上次摘要基础上再摘要（摘要包含上次摘要内容 + 新的旧消息）。
- **确定性测试**：摘要函数接受 `chat_model_provider` 参数，测试时使用 DeterministicChatModelProvider。

## 前端聊天 UI 设计决策

- Agent 面板的 `answer-box` 区域改为 `chat-messages` 滚动容器。
- 每条消息是一个 `<article class="chat-message chat-message--user/assistant">` 元素。
- 用户气泡：显示问题文本，右对齐。
- 助手气泡：显示回答文本 + mode badge + iteration badge + citations + refusal 信息，左对齐。
- 工具调用/workflow 步骤面板保持独立侧边区域，点击某条助手消息时更新。
- 输入区域保持底部固定。
- 新消息追加到底部，自动滚动。
- 阶段 24 的会话管理放在 Agent 面板顶部或左侧：会话列表 + 新建按钮。

## 向后兼容策略

- `AgentQueryRequest.conversation_id` 是可选的，默认 None。
- 不传 conversation_id 时：行为与阶段 23 完全一致，不持久化，不加载历史。
- 前端默认创建会话并传 conversation_id，但 API 层不强制。
- `POST /chat` 端点不在阶段 24 改动范围内——多轮对话只影响 Agent 面板。

## 数据安全边界

- `Message.metadata_json` 不存储 API key、Bearer token、供应商原始敏感响应或受限全文。
- 会话删除时级联删除所有消息。
- 摘要内容不暴露供应商内部格式或敏感信息。
- 前端所有动态 HTML 继续使用 `escapeHtml()`。

## Phase 1 设计文档发现

- `docs/stage24_multi_turn_conversation.md` 已作为阶段 24 的普通设计文档落地，后续代码实现以它作为验收锚点。
- 阶段 24 只把多轮会话接入 `/agent/query`，不改 `POST /chat`，避免把变更面扩大到已有引用式问答 API。
- `request.history` 继续保留为兼容字段，但当前前端默认使用服务端 `conversation_id` 历史；当两者同时存在时，服务端会话历史优先，减少客户端伪造或重复历史带来的混乱。
- agentic history 只进入 generate 节点，不改变 retrieve/grade/rewrite 的主问题驱动结构，避免把阶段 24 误扩展成跨会话长期记忆。

## Phase 2 模型层发现

- 现有项目没有 Alembic 迁移链路，测试和本地启动依赖 `Base.metadata.create_all` 自动建表；阶段 24 继续沿用这个模式新增 `conversations` 和 `messages`。
- `Conversation.messages` 使用 ORM 级 `cascade="all, delete-orphan"`，repository 删除会话时会删除同会话消息；这比只依赖 SQLite 外键开关更贴合当前测试环境。
- `Message.metadata_json` 使用 `ensure_ascii=False`，可以保存中文拒答原因或摘要元数据，同时保持 JSON 结构紧凑。
- `ConversationRepository.add_message()` 在第一条 user 消息追加时自动把默认标题更新为用户问题前 40 字符，满足阶段 24 默认标题策略。

## Phase 3 API 层发现

- `/conversations` 使用空路径注册 `POST ""` / `GET ""`，最终暴露为 `POST /conversations` 和 `GET /conversations`，符合 FastAPI 当前路由风格。
- API 响应不把数据库内部字段 `metadata_json` 直接暴露给前端，而是转换为 `metadata` 对象，前端可以直接渲染 citations/workflow/refusal 等结构。
- `GET /conversations` 的 `limit` 在路由内夹紧到 1-100，避免前端误传过大分页参数导致一次性读取过多会话。
- 目前会话 API 没有认证/用户隔离，这是阶段 24 明确边界；后续如果加登录系统，需要给 `Conversation` 增加 owner/user 维度并更新列表过滤。

## Phase 4 `/agent/query` 会话集成发现

- default AgentService 已经支持 `history`，阶段 24 只需要在 API 层把会话消息装配成 `list[str]` 传入，避免重复改 Brain 链路。
- agentic 链路原先不支持 history；阶段 24 采用最小改动：`run_agentic_rag(..., history=None)` -> `AgenticState.history` -> generate 节点用 `rewrite_contextual_question()` 补全上下文追问。
- 传入 `conversation_id` 时，API 成功响应后才追加 user/assistant 消息；如果会话不存在或请求校验失败，不留下半条消息。
- 助手消息 metadata 当前保存响应里的可观测字段，包括 tool_calls、search_results、sources、citations、workflow_steps、refusal_category 等，供前端刷新恢复。
- 历史装配已经预留 summary 规则：如果存在 summary，使用最新 summary 及其后的消息；Phase 5 会补自动摘要生成。

## Phase 5 摘要压缩发现

- 摘要触发不能只看全会话非 summary 总数，否则创建第一条 summary 后下一轮会继续重复摘要旧消息；当前实现只统计“最新 summary 之后”的非 summary 消息数。
- 当前策略是超过 16 条非 summary 消息后摘要较旧消息，并保留最近 6 条；这对应大约保留最近 3 轮对话。
- summary 消息追加在会话末尾，下一轮 `history_from_messages()` 会选中最新 summary 及其后的消息；旧消息保留在 DB，但不再进入默认 history。
- 摘要 provider 使用同一个 `ChatModelProvider` 接口；deterministic provider 可以跑通测试，真实 provider 只在实际运行时被调用，不进入 CI 前提。

## Phase 6 前端聊天 UI 发现

- 为了减少破坏面，前端保留 `data-agent-answer-box` 作为 JS 和测试锚点，但语义从单个 answer 容器变为 `chat-messages` 列表。
- `renderAgentAnswer()` 现在追加助手气泡，而不是替换 `innerHTML`；用户气泡由 `appendAgentUserMessage()` 在请求发出前立即追加。
- 阶段 23 验收提到的“请求失败后 mode 指示器停在判断中”已在 Agent submit catch 中修复为 `updateAgentModeStatus("auto")`。
- Phase 6 暂不传 `conversation_id`，因为 Phase 7 会统一接入会话创建、切换和刷新恢复，避免先写一半前端状态管理。

## Phase 7 前端会话管理发现

- 前端初始化顺序现在是 health -> workspace data -> agent conversations；这样资料工作台和会话工作台都能在同一次页面加载完成。
- 页面无会话时自动创建 `新对话`，因此用户第一次打开 Agent 面板即可直接提交问题。
- 发送 Agent 请求前如果 `state.currentConversationId` 为空，会先创建会话，再把 `conversation_id` 写入 `/agent/query` 请求体。
- 切换会话时前端用服务端返回的 message metadata 重建助手气泡；summary 消息以居中摘要气泡显示。
- Phase 7 仍未引入登录系统，会话列表是本地应用实例级别；这是阶段 24 明确边界。

## Phase 8 回归验证发现

- 全量测试结果为 479 passed，高于阶段 23 的 463 passed 基线，说明阶段 24 新增会话、摘要和前端测试后没有破坏既有质量门。
- 浏览器桌面视口验证显示：会话管理栏、聊天消息区、新建/删除会话按钮均存在；旧的用户可编辑 mode 下拉不再出现，阶段 23 自动路由只读指示器语义保留。
- 浏览器提交使用“查看来源详情 + 缺失 source_id”路径触发 `/agent/query`，该路径不需要真实模型调用；页面追加用户气泡和 Agent 气泡，并展示 `refusal_category`，可证明聊天 UI 的基本追加渲染和元数据展示可用。
- 浏览器移动视口 `390x844` 下，`.conversation-bar` 和聊天列表宽度都收敛在页面宽度内，没有横向溢出。
- 阶段 24 的质量门继续保持“真实 API 不是 CI 或本地全量测试前提”；浏览器验收也优先使用确定性/非模型路径。

## Phase 9 文档与 Obsidian 收尾发现

- `README.md` 顶部已从阶段 23 更新为阶段 24 待人工核验状态，并记录全量测试 479 passed、未提交/未打 tag/未推送边界。
- `docs/progress.md` 作为权威进度记录，已新增阶段 24 最新状态；阶段 23 改为历史状态。
- `docs/architecture.md` 已新增 Conversation 层和阶段 24 多轮会话架构，明确 `/chat` 不受影响，`/agent/query conversation_id` 是多轮开关。
- `docs/data_sources.md` 已说明阶段 24 不新增外部资料来源，新增的是本地会话运行数据；`Message.metadata_json` 不允许保存密钥、供应商原始响应或受限全文。
- `AGENT.MD` 已补阶段 24 之后的多轮会话规则，并把当前推荐第一步改为人工核验阶段 24。
- Obsidian 已新增阶段页、阶段 24 Phase 汇报索引、Phase 0-9 小汇报和 4 篇关键知识点笔记；小 Phase 汇报依据 `progress.md`、`task_plan.md`、`findings.md` 和测试结果回填。
- 阶段 24 仍停在人工核验前状态；后续 agent 不得提交、打 tag 或 push，除非用户明确确认。

## 人工测试反馈修复发现

- “水化热的影响因素”在本地真实 `mimo-v2.5-pro` 配置下约 27.6 秒返回；用户感知的“一直不回”主要来自真实 provider 等待时间长，加上前端没有 busy 锁和明确超时提示。
- 前端应把“运行中”和“超时失败”作为一等状态，否则用户容易重复点击并堆积临时 user 气泡。
- 阶段 24 的 summary 压缩是优化路径，不应影响主回答返回；provider 超时时应跳过本轮 summary，而不是把成功回答变成失败。
- 后端返回 provider 失败时不能透传供应商原始响应或敏感 body；当前统一返回 `503 chat model provider is unavailable or timed out`。
- 用户等待模型生成时，反馈最好放在聊天流里，而不只是按钮或顶部状态栏。阶段 24 追加 `正在思考...` 临时 Agent 气泡后，用户能在对话上下文里确认系统仍在生成。
- 输入 `堆石` 实测可以正常返回答案；用户看到 `error` 且无输出的核心问题是前端失败态没有把错误原因放进聊天流，并且本地可能同时运行旧 8000/8001 uvicorn 进程导致访问到旧静态资源。
- `你好` 这类寒暄不应进入 RAG 检索和拒答判断；它属于产品引导意图。AgentService 增加 greeting 分支后，可避免把正常社交开场误判成资料不足。
- 前端产品入口应收敛到 Agent 对话框。`/chat` 仍保留为后端单轮 RAG baseline 和回归测试接口，但普通用户首页不再展示独立“问答”面板，避免用户困惑“问答”和“Agent”两个入口的差异。
- 首页的“检索 + 片段”面板同样更像工程调试入口：它直接暴露 keyword/vector/hybrid 召回和 chunk 查看，不生成最终回答。普通用户主界面隐藏该面板，避免把底层召回能力和 Agent 产品入口并列；`/search`、`/search/vector`、`/search/hybrid` 后端 API 仍保留为 Agent 底层能力、回归测试和检索质量调试入口。

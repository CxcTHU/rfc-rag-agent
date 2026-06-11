# 阶段 24 提交合并记录

时间：2026-06-11

用户已完成阶段 24 人工核验，并明确要求提交阶段 24 整体开发工作、创建 `phase-24-complete` tag、上传并 merge 至 GitHub。

提交前复核：
- 当前分支：`codex/phase-24-multi-turn-conversation`
- 阶段 24 起点：`8fc1cfa Merge phase 23 agentic eval and auto routing`
- `phase-23-complete` 仍指向 `dd7d953 Complete phase 23 agentic eval and auto routing`
- 提交前不存在 `phase-24-complete`
- 未移动任何已有阶段 tag

最终提交前测试：
```text
.\.venv\Scripts\python.exe -m pytest -q
483 passed in 46.23s
```

本次准备发布范围：
- Conversation / Message 模型与会话级持久化。
- `/conversations` CRUD API。
- `/agent/query conversation_id` 历史加载、消息持久化和向后兼容。
- agentic generate 节点 history 支持。
- 长对话 summary 压缩。
- Agent 聊天气泡 UI、会话管理、正在思考提示、错误气泡、greeting 引导。
- 首页隐藏普通用户不需要的“问答”和“检索”调试面板，后端 `/chat` 和 `/search*` API 保留。
- 阶段 24 普通文档、验收报告与 Obsidian 草稿收尾。

# 阶段 24 进度日志：多轮对话 UI 与会话持久化

## 当前状态

- 当前阶段：阶段 24「多轮对话 UI 与会话持久化」。
- 当前分支：`codex/phase-24-multi-turn-conversation`。
- 当前基线提交：`8fc1cfa Merge phase 23 agentic eval and auto routing`。
- Git/tag 状态：`phase-23-complete -> dd7d953 Complete phase 23 agentic eval and auto routing`；`main` 与 `origin/main` 均指向 `8fc1cfa`，阶段 23 已合并到 main。
- 阶段 24 状态：Phase 9 文档同步与 Obsidian 收尾完成，等待用户人工核验。
- 提交状态：尚未 `git add`、尚未提交、尚未创建 `phase-24-complete` tag、尚未推送。

## 阶段 24 目标概述

从阶段 23 完成后的 main 出发，实现多轮对话 UI 与会话持久化：

1. **后端会话模型**：新增 Conversation 和 Message 表，支持会话级消息分组和持久化。
2. **会话 API**：新增 CRUD 端点管理会话和消息。
3. **`/agent/query` 集成**：支持可选 conversation_id，自动加载历史、持久化新消息。
4. **上下文摘要压缩**：长对话自动生成摘要，控制 LLM prompt 长度。
5. **前端聊天 UI**：Agent 面板从单次覆盖改为聊天气泡列表，消息追加渲染。
6. **前端会话管理**：会话列表、新建/切换/删除，刷新页面恢复。

## 阶段 23 验收基线

- 阶段 23 验收结论：PASS（2026-06-11 Claude 独立验收）。
- 测试基线：463 passed。
- 评测基线：error_rate=0.000，decision=reliable_auto_route_candidate。
- 关键交付：自动模式路由（classify_query_complexity）、前端只读模式指示器、确定性评测闭环。

## 遗留风险

- 阶段 23 验收中指出的模式指示器在请求失败时卡在"判断中"的小 UI 问题，阶段 24 前端改造时可一并修复。
- agentic 路径目前不接受 history 参数，阶段 24 需要扩展 `run_agentic_rag()` 和 `AgenticState`。
- 上下文摘要依赖 LLM 调用，需要确保 deterministic provider 下可测试。
- 前端从单次问答到聊天 UI 是较大的 DOM 结构变更，需要注意不破坏现有可观测字段（mode/workflow/citations/refusal）的展示。

## Phase 0 日志：启动校准与文件计划

时间：2026-06-11

本 Phase 解决的问题：确认阶段 23 的 tag、main 合并点和阶段 24 起点，防止从阶段 22 或错误基线继续开发。

RAG 链路位置：这是阶段开发入口校准，不改运行时 RAG 链路，但决定后续 Conversation、Message、Agent 历史装配都建立在阶段 23 自动路由之后。

为什么现在做：阶段 24 依赖 `/agent/query` 的自动 default/agentic 路由和前端只读模式指示器，必须先确认阶段 23 已完成并合并。

已完成：

- 已创建本线程 goal，并将线程标题改为「阶段24-多轮对话UI与会话持久化」。
- 已读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage23_agentic_eval_and_auto_routing.md`、`docs/phase_reviews/phase-23.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 已运行 `git status -sb`、`git log --oneline -5`、`git fetch --tags origin`。
- 已确认 `phase-23-complete` 指向 `dd7d953`，未移动任何已有阶段 tag。
- 已确认 `main` 与 `origin/main` 均指向 `8fc1cfa`，且 `phase-23-complete` 已并入两者。
- 已从阶段 23 合并后的 `main` 创建并切换到 `codex/phase-24-multi-turn-conversation`。

验证结果：

```text
git status -sb
## main...origin/main
 M findings.md
 M progress.md
 M task_plan.md

git rev-parse main origin/main phase-23-complete
main/origin/main = 8fc1cfa452a0ca749e494b402d5e14262801e33f
phase-23-complete = dd7d953e6dba7023294353a636438dd90c4f2b68

git merge-base --is-ancestor phase-23-complete main
phase-23-complete is ancestor of main

git merge-base --is-ancestor phase-23-complete origin/main
phase-23-complete is ancestor of origin/main
```

新词解释：

- `tag`：Git 里给某个提交打的固定标签。在本项目里，`phase-23-complete` 用来标记阶段 23 的最终功能提交，后续阶段不能移动它；面试时可以说，阶段 tag 是可追溯交付边界。
- `merge commit`：把阶段分支合入 `main` 时产生的合并提交。阶段 23 的合并提交是 `8fc1cfa`；面试时可以说，功能 tag 指向功能提交，main 则停在包含该功能的合并提交。
- `merge-base --is-ancestor`：Git 用来判断一个提交是否已经包含在另一个分支历史里的命令。本项目用它确认阶段 23 tag 已合入 main。

遗留问题：

- 无阻塞问题。继续 Phase 1：阶段 24 设计文档。

## Phase 1 日志：阶段 24 设计文档

时间：2026-06-11

本 Phase 解决的问题：把阶段 24 的会话持久化、API、历史装配、摘要压缩和前端聊天 UI 先写成可审查合同，避免后续实现各自漂移。

RAG 链路位置：横跨数据库模型、`/conversations` API、`/agent/query`、default AgentService、agentic LangGraph generate 节点和前端 Agent 面板。

为什么现在做：阶段 24 涉及后端、前端和上下文管理，先固化设计能让 Phase 2-9 按同一标准实现和验收。

已完成：

- 新增 `docs/stage24_multi_turn_conversation.md`。
- 记录当前 `history` 字段局限：客户端传入、不持久化、刷新丢失、agentic 路径不接收。
- 固化 `Conversation` / `Message` 模型字段和 `metadata_json` 用途。
- 固化 `/conversations` 四个 API 端点。
- 固化 `/agent/query` 的 `conversation_id` 向后兼容策略。
- 固化 agentic history 只进入 generate 节点的边界。
- 固化长对话摘要压缩阈值、存储方式和历史装配方式。
- 固化前端聊天气泡 UI、会话管理、动态 HTML 安全边界。

验证结果：

- 文档已存在，并覆盖阶段 24 验收项。
- 本 Phase 未运行代码测试，因为只新增普通设计文档。

新词解释：

- `Conversation`：会话，一组连续问答的容器。本项目会用 `conversations` 表保存；面试时可以说它负责分组、列表和刷新恢复。
- `Message`：消息，会话里的单条 user/assistant/summary 记录。本项目会用 `messages` 表保存；面试时可以说它让前端能按顺序还原聊天历史。
- `metadata_json`：消息的结构化展示元数据。本项目用它保存 citations、workflow_steps、refusal_category 等可观测字段；面试时可以说它避免为变长展示数据设计一堆不稳定列。
- `上下文摘要压缩`：把旧对话压缩成 summary，只把摘要和近期消息传给 LLM。本项目用它控制长对话 prompt 长度；面试时可以说这是轻量自建方案，不引入 LangGraph Checkpointer。

遗留问题：

- 进入 Phase 2，实现数据库模型和 repository 测试。

## Phase 2 日志：Conversation 与 Message 模型

时间：2026-06-11

本 Phase 解决的问题：后端只有扁平 `qa_logs`，没有能还原多轮对话的会话和消息结构。

RAG 链路位置：数据库模型层，为后续 `/conversations` API、`/agent/query` 历史装配、摘要压缩和前端刷新恢复提供持久化基础。

为什么现在做：API 和前端都依赖模型层先就绪；如果没有 Conversation/Message，后续只能继续靠前端临时 history，刷新即丢。

已完成：

- 在 `app/db/models.py` 新增 `Conversation` 模型。
- 在 `app/db/models.py` 新增 `Message` 模型。
- 在 `app/db/repositories.py` 新增 `ConversationCreate`、`MessageCreate`、`ConversationRepository`。
- 支持创建会话、按更新时间倒序列出会话、查询会话消息、追加消息、删除会话、统计消息数。
- 支持 `metadata_json` 序列化/反序列化。
- 追加第一条 user 消息时，默认会话标题自动变成问题前 40 字符。
- 补充模型和 repository 测试。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_db_models.py tests\test_repositories.py -q
8 passed in 1.94s
```

新词解释：

- `ORM cascade`：通过 SQLAlchemy 对象关系自动处理关联删除。本项目里删除 `Conversation` 会连同其 `Message` 删除；面试时可以说，这是保护数据一致性、避免孤儿消息的方式。
- `metadata_json`：保存在消息表里的 JSON 字符串。本项目用它记录助手消息的 citations、workflow_steps、refusal_category 等展示信息；面试时可以说，它适合存变长、半结构化的可观测字段。
- `updated_at`：更新时间。本项目用它给会话列表排序，用户最近聊过的会话排在前面；面试时可以说，它支撑“最近会话”体验。

遗留问题：

- 进入 Phase 3，新增 `/conversations` API 和 schema。

## Phase 3 日志：会话 API 端点

时间：2026-06-11

本 Phase 解决的问题：前端需要通过 HTTP 管理会话和读取消息历史，模型层可用后还缺少 API 入口。

RAG 链路位置：FastAPI 路由层，位于前端 Agent 面板和数据库会话模型之间。

为什么现在做：没有 `/conversations` API，前端无法创建、切换、删除或刷新恢复会话；Phase 4 的 `/agent/query` 也需要可查询的会话存在性。

已完成：

- 新增 `app/schemas/conversation.py`。
- 新增 `app/api/conversations.py`。
- 注册 `POST /conversations`、`GET /conversations`、`GET /conversations/{conversation_id}/messages`、`DELETE /conversations/{conversation_id}`。
- 响应中把 `metadata_json` 转换为 `metadata` 对象。
- `GET /conversations` 支持 `limit` 并夹紧到 1-100。
- 新增 API 测试，覆盖正常路径和 404 异常路径。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_conversations_api.py -q
6 passed in 5.47s

.\.venv\Scripts\python.exe -m pytest tests\test_db_models.py tests\test_repositories.py tests\test_conversations_api.py -q
14 passed in 4.07s
```

新词解释：

- `schema`：API 请求和响应的数据结构定义。本项目用 Pydantic schema 约束 `/conversations` 的输入输出；面试时可以说，schema 是后端和前端之间的合同。
- `404`：HTTP 的“资源不存在”状态码。本项目在会话不存在时返回 404；面试时可以说，这比返回空数组更清楚地告诉调用方 ID 不存在。
- `limit`：列表接口一次最多返回多少条。本项目把它限制在 1-100；面试时可以说，这是防止误传参数导致一次性读取过多数据的保护。

遗留问题：

- 进入 Phase 4，把 `/agent/query` 接入 `conversation_id`，自动加载历史并持久化新消息。

## Phase 4 日志：`/agent/query` 会话集成与历史装配

时间：2026-06-11

本 Phase 解决的问题：`/agent/query` 每次调用都是独立请求，不能自动加载历史，也不会保存用户和助手消息。

RAG 链路位置：FastAPI `/agent/query` 入口和 default AgentService / agentic LangGraph 之间，是会话历史进入 RAG 链路的位置。

为什么现在做：会话模型和 API 已经就绪，核心查询端点必须接入 `conversation_id` 后，前端多轮聊天才有后端依据。

已完成：

- `AgentQueryRequest` 新增 `conversation_id: int | None`。
- `/agent/query` 传入 `conversation_id` 时，先校验会话存在。
- 会话历史通过 `history_from_messages()` 装配为 `list[str]`。
- default 链路复用现有 `AgentService.query(history=...)`。
- agentic 链路新增 `run_agentic_rag(..., history=...)`，`AgenticState` 新增 `history`，generate 节点使用 `rewrite_contextual_question()`。
- 请求成功后追加 user 和 assistant 两条 `Message`。
- assistant 消息 metadata 保存 citations、workflow_steps、mode、refusal_category 等可观测字段。
- 不传 `conversation_id` 时不写会话，保持阶段 23 向后兼容。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_agent_api.py tests\test_conversations_api.py tests\test_agentic_graph.py -q
39 passed in 8.63s

.\.venv\Scripts\python.exe -m pytest tests\test_db_models.py tests\test_repositories.py tests\test_conversations_api.py tests\test_agent_api.py tests\test_agentic_graph.py -q
47 passed in 11.69s
```

新词解释：

- `conversation_id`：会话编号。本项目中前端传它给 `/agent/query`，后端据此加载历史并保存新消息；面试时可以说，它是多轮对话和单次问答的分界开关。
- `history_from_messages()`：把数据库消息转换成 LLM 可读历史文本的函数。本项目会把 user/assistant/summary 转成带角色前缀的字符串；面试时可以说，这是数据存储格式到 prompt 输入格式的适配层。
- `generate 节点`：agentic LangGraph 中真正生成答案的节点。本项目只在这里利用 history，不改变检索节点；面试时可以说，这避免把短期会话上下文误当作长期知识库。

遗留问题：

- 进入 Phase 5，补充长对话自动摘要压缩，避免历史无限增长。

## Phase 5 日志：上下文摘要压缩

时间：2026-06-11

本 Phase 解决的问题：会话消息会持续增长，如果每轮都把全部历史传给 LLM，会拉长 prompt、增加成本，也可能干扰检索改写。

RAG 链路位置：会话历史装配层，位于 `/agent/query` 消息持久化之后、下一轮 history 进入 default/agentic 链路之前。

为什么现在做：Phase 4 已经能保存多轮消息，必须马上补上长对话压缩，否则前端一旦支持长期会话就会积累无上限历史。

已完成：

- 新增 `app/services/conversation/history.py`。
- 抽出 `history_from_messages()` 和 `format_message_for_history()`。
- 新增 `summarize_conversation_if_needed()`。
- 非 summary 消息超过 16 条时触发摘要。
- 每次摘要保留最近 6 条非 summary 消息。
- summary 写成 `role="summary"` 的 `Message`，metadata 记录被摘要消息 ID 和保留近期消息数。
- `/agent/query` 在成功写入 assistant 消息后触发摘要检查。
- 补充摘要 service 测试和 agent API 长会话摘要测试。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_conversation_summary.py tests\test_agent_api.py -q
17 passed in 4.95s

.\.venv\Scripts\python.exe -m pytest tests\test_db_models.py tests\test_repositories.py tests\test_conversations_api.py tests\test_conversation_summary.py tests\test_agent_api.py tests\test_agentic_graph.py -q
51 passed in 11.65s
```

新词解释：

- `summary message`：摘要消息。本项目中 `role="summary"`，用于代表更早的多轮对话；面试时可以说，它让历史可控增长，同时保留上下文主线。
- `trigger threshold`：触发阈值。本项目是最新 summary 后非摘要消息超过 16 条；面试时可以说，阈值避免每轮都调用摘要模型。
- `recent window`：近期窗口。本项目保留最近 6 条非摘要消息；面试时可以说，近期原文比摘要更适合处理用户刚刚追问的细节。

遗留问题：

- 进入 Phase 6，把前端 Agent 面板改为聊天气泡列表，并保留可观测字段展示。

## Phase 6 日志：前端聊天 UI

时间：2026-06-11

本 Phase 解决的问题：Agent 面板之前每次查询都会覆盖上一次结果，用户看不到多轮对话上下文。

RAG 链路位置：前端 Agent 面板，是用户看到 `/agent/query` 结果、mode、workflow、citations 和 refusal 信息的位置。

为什么现在做：后端已经能持久化会话和摘要，前端需要先具备消息追加展示能力，下一步才能接入会话管理。

已完成：

- 将 Agent 结果区改为 `chat-messages` 滚动列表。
- 新增 `appendAgentUserMessage()`，请求发出前追加用户气泡。
- 新增 `appendAgentAssistantMessage()`，响应成功后追加助手气泡。
- 抽出 `agentAnswerHtml()`，复用阶段 22/23 的 mode、iteration、citation、refusal 展示。
- 保留 workflow/tool 调用侧栏，继续跟随最新助手响应更新。
- 请求失败时 `updateAgentModeStatus("auto")`，修复阶段 23 验收中的“判断中”残留问题。
- 补充前端静态测试断言。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed in 0.79s

.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_conversations_api.py tests\test_agent_api.py -q
26 passed in 5.35s
```

新词解释：

- `聊天气泡`：把 user 和 assistant 消息按角色分开展示的 UI 元素。本项目用左右对齐气泡让多轮对话可读；面试时可以说，它从单次问答升级为可追踪会话。
- `append render`：追加渲染。本项目不再覆盖 Agent 结果区，而是用 `insertAdjacentHTML("beforeend", ...)` 追加消息；面试时可以说，这保留了历史上下文。
- `aria-live`：网页无障碍属性，提示辅助技术某区域会动态更新。本项目用于聊天消息列表；面试时可以说，这是动态界面的基本可访问性考虑。

遗留问题：

- 进入 Phase 7，接入 `/conversations` API，实现会话列表、新建、切换、删除和刷新恢复。

## Phase 7 日志：前端会话管理

时间：2026-06-11

本 Phase 解决的问题：前端虽然能追加消息，但还不能创建、切换、删除会话，刷新页面也无法恢复历史。

RAG 链路位置：前端会话管理层，连接浏览器 UI、`/conversations` API 和 `/agent/query conversation_id`。

为什么现在做：Phase 6 已经有聊天气泡列表，只有接入会话 API 后，多轮对话才从“页面临时状态”变成“服务端持久化会话”。

已完成：

- Agent 面板新增会话管理栏。
- 新增 `state.conversations` 和 `state.currentConversationId`。
- 新增 `refreshConversationList()`、`createAgentConversation()`、`loadConversationMessages()`、`loadAgentConversations()`、`deleteCurrentConversation()`。
- 页面初始化后自动加载最近会话；没有会话则创建新会话。
- 切换会话会重建聊天气泡列表。
- summary 消息渲染为居中摘要气泡。
- `submitAgent()` 会确保存在当前会话，并在请求体中写入 `conversation_id`。
- 删除当前会话后自动切换到下一条或创建新会话。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed in 0.76s

.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_conversations_api.py tests\test_agent_api.py tests\test_conversation_summary.py -q
29 passed in 6.67s
```

新词解释：

- `currentConversationId`：前端当前选中的会话 ID。本项目用它给 `/agent/query` 请求带上会话上下文；面试时可以说，它是前端状态和服务端持久化的连接点。
- `刷新恢复`：页面重载后重新从服务端加载会话列表和消息。本项目通过 `GET /conversations` 和 `GET /conversations/{id}/messages` 实现；面试时可以说，历史不再依赖浏览器内存。
- `summary 气泡`：前端展示 `role="summary"` 消息的中性气泡。本项目用它提醒用户旧历史已被压缩；面试时可以说，这是长对话上下文管理的可见反馈。

遗留问题：

- 进入 Phase 8，运行全量测试并做浏览器桌面/移动验证。

## Phase 8 日志：回归验证与质量门

时间：2026-06-11

本 Phase 解决的问题：阶段 24 涉及数据库模型、API、Agent 历史装配、摘要压缩和前端 Agent 面板，必须确认新增功能与既有接口没有回归。

RAG 链路位置：全链路回归，覆盖数据库层、FastAPI 路由层、default/agentic RAG 入口、前端 Agent 工作台和质量门。

为什么现在做：功能开发完成后，只有先通过全量测试和浏览器基本验收，文档收尾才有准确依据。

已完成：

- 已运行阶段 24 全量测试。
- 已确认全量测试结果高于阶段 23 的 463 passed 基线。
- 已用内置浏览器打开 `http://127.0.0.1:8001` 做桌面视口检查。
- 已通过“查看来源详情 + 缺失 source_id”路径触发 `/agent/query` 非模型分支，验证聊天气泡追加和拒答分类展示。
- 已用移动视口 `390x844` 检查会话栏和聊天区布局。
- 已确认桌面和移动视口均无横向溢出，控制台无 error。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest -q
479 passed in 48.60s

Browser desktop 1280x720:
conversation list = true
chat list = true
legacy data-agent-mode select count = 0
horizontal overflow = false
console errors = []

Browser agent submit:
messages = 2
chat-message--user = 1
chat-message--assistant = 1
refusal_category metadata visible = true
console errors = []

Browser mobile 390x844:
conversation bar visible = true
chat list visible = true
horizontal overflow = false
console errors = []
```

新词解释：

- `质量门`：进入下一阶段前必须通过的测试和验收条件。本项目 Phase 8 的质量门是全量测试通过、浏览器基本可用、且真实 API 不是测试前提；面试时可以说，质量门让功能开发和交付边界可追溯。
- `视口`：浏览器可见区域大小。本项目用桌面 `1280x720` 和移动 `390x844` 检查前端布局；面试时可以说，这是验证响应式 UI 是否溢出的基本方法。
- `非模型路径`：不调用真实 LLM 的后端分支。本项目用来源详情查询缺失 source 的方式验证 `/agent/query` 和聊天 UI；面试时可以说，这能降低验收成本并避免把外部 API 变成测试依赖。

遗留问题：

- 进入 Phase 9，同步普通文档和 Obsidian 本地知识库。

## Phase 9 日志：文档同步、Obsidian 收尾与人工核验待提交状态

时间：2026-06-11

本 Phase 解决的问题：把阶段 24 的最终设计、实现、测试和安全边界同步到普通文档与本地 Obsidian 知识库，并明确停在人工核验前。

RAG 链路位置：项目知识层和阶段交付边界，不改变运行时 RAG 链路。

为什么现在做：阶段 24 已通过全量测试和浏览器验证，文档现在可以准确描述最终行为；同时项目规则要求提交前完成普通文档和 Obsidian 收尾。

已完成：

- 已更新 `README.md`，将当前阶段改为阶段 24 待人工核验状态，补会话持久化、会话 API、摘要压缩和前端会话管理说明。
- 已更新 `docs/progress.md`，新增阶段 24 最新状态，并将阶段 23 标记为历史状态。
- 已更新 `docs/architecture.md`，新增 Conversation 层和阶段 24 多轮会话架构。
- 已更新 `docs/data_sources.md`，说明阶段 24 不新增外部资料来源，只新增本地会话运行数据。
- 已更新 `AGENT.MD`，补阶段 24 之后多轮会话规则和当前人工核验优先事项。
- 已新增 `obsidian-vault/阶段/阶段 24 - 多轮对话 UI 与会话持久化.md`。
- 已新增 `obsidian-vault/阶段汇报/阶段 24 - 多轮对话 UI 与会话持久化/阶段 24 Phase 汇报索引.md`。
- 已新增 Phase 0 到 Phase 9 小汇报，每篇包含目标、完成任务、修改内容、关键模块、问题与解决、新词解释、验证结果、遗留问题、下一 Phase 和面试表达。
- 已更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`。
- 已新增 4 篇阶段 24 知识点：Conversation 与 Message 会话模型、会话 API 设计、上下文摘要压缩、前端聊天气泡与会话管理。

验证结果：

```text
阶段 24 功能质量门：
.\.venv\Scripts\python.exe -m pytest -q
479 passed in 48.60s

阶段 24 浏览器验证：
desktop 1280x720: 无横向溢出，console errors=0
mobile 390x844: 无横向溢出，console errors=0
agent submit 非模型路径: 1 user bubble + 1 assistant bubble，refusal_category 可见
```

新词解释：

- `人工核验前状态`：代码、测试和文档已经完成，但还没有提交、打 tag 或推送，等待用户手动审查确认；面试时可以说，这是把开发完成和版本发布分开的交付控制。
- `Obsidian 阶段页`：记录大阶段整体目标、完成内容、验证和面试表达的本地知识库页面；本项目用它帮助复盘和面试准备。
- `Phase 汇报索引`：一个阶段内所有小 Phase 汇报的导航页；本项目用它把开发过程拆成可追溯的小块。

遗留问题：

- 阶段 24 尚未提交、尚未创建 `phase-24-complete` tag、尚未推送 GitHub。
- 等待用户人工核验；用户明确确认前，不得执行 `git add`、`git commit`、`git tag`、`git push` 或创建 PR。

人工核验重点：

- Conversation / Message 模型和级联删除。
- `/conversations` 四个端点正常和异常路径。
- `/agent/query` 不传 `conversation_id` 的向后兼容。
- `/agent/query` 传 `conversation_id` 后的历史加载、消息持久化和摘要触发。
- agentic generate 节点 history 使用边界。
- 前端聊天气泡、会话列表、新建、切换、删除、刷新恢复。
- 动态 HTML 的 `escapeHtml()` 安全边界。
- 全量测试 479 passed 和浏览器验证结果。

## 人工测试反馈修复：Agent 请求长时间等待的前端与后端兜底

时间：2026-06-11

用户人工测试反馈：前端发送“水化热的影响因素”后一直没有看到 Agent 回复，且重复点击会出现多条用户气泡。

定位结果：

- 本地 `.env` 使用真实 `openai-compatible` chat provider：`mimo-v2.5-pro`，chat timeout 为 30 秒。
- 直打 `/agent/query` 时，同一问题约 27.6 秒才返回 200，说明真实模型响应慢会让页面长时间处于等待状态。
- 前端提交期间没有锁定运行按钮，重复点击会重复追加临时用户气泡。
- 如果真实 provider 超时或报错，后端原先可能把 provider RuntimeError 作为未处理异常暴露给前端；如果摘要压缩阶段失败，也可能影响已生成回答返回。

修复内容：

- `app/frontend/static/app.js`
  - `fetchJson()` 支持 `timeoutMs` 和 `AbortController`。
  - Agent 请求设置 45 秒前端超时，超时时显示“请求超时：后端或模型服务暂时没有返回，请稍后重试或检查模型配置”。
  - 新增 `agentRequestInFlight`、`setAgentBusy()`、`setAgentPanelStatus()`。
  - Agent 请求进行中禁用“运行”按钮并显示“运行中”。
  - 先确保当前会话存在，再追加用户气泡。
  - 请求失败时移除临时用户气泡，避免重复点击堆积。
- `app/api/agent.py`
  - default 和 agentic 链路捕获 `RuntimeError`，返回 `503 chat model provider is unavailable or timed out`，不透传供应商原始响应。
  - summary 压缩失败降级为 best-effort，不再吞掉已成功生成的回答。
- `tests/test_frontend_app.py`
  - 补充前端超时、busy 状态和临时气泡撤销的静态断言。
- `tests/test_agent_api.py`
  - 补充 provider 超时返回 503 的测试。
  - 补充回答成功但 summary provider 超时仍返回 200 的测试。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed

.\.venv\Scripts\python.exe -m pytest tests\test_agent_api.py tests\test_conversations_api.py -q
20 passed

.\.venv\Scripts\python.exe -m pytest tests\test_agent_api.py tests\test_frontend_app.py -q
22 passed

.\.venv\Scripts\python.exe -m pytest tests\test_conversation_summary.py tests\test_conversations_api.py -q
9 passed

.\.venv\Scripts\python.exe -m pytest -q
481 passed in 50.10s
```

当前状态：

- 8001 服务已重启并加载修复后的代码。
- 阶段 24 仍未提交、未创建 `phase-24-complete` tag、未推送，继续等待用户人工核验。

## 人工测试反馈增强：Agent 正在思考提示

时间：2026-06-11

用户继续反馈：即使按钮显示运行中，聊天区没有“正在思考”的提示，用户仍不知道系统是否在正常生成。

修复内容：

- `app/frontend/static/app.js`
  - 新增 `appendAgentThinkingMessage()`。
  - Agent 请求发出后，在聊天流中追加临时 Agent 气泡：`正在思考...`。
  - 成功返回后先移除 thinking 气泡，再追加正式 Agent 回答。
  - 失败或超时时移除 thinking 气泡，并保留错误提示逻辑。
- `app/frontend/static/styles.css`
  - 新增 `.chat-message--thinking` 和 `.thinking-text` 样式，让提示气泡与普通回答区分。
- `tests/test_frontend_app.py`
  - 补充 thinking 气泡函数、提示文案和样式断言。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed

.\.venv\Scripts\python.exe -m pytest tests\test_agent_api.py tests\test_conversations_api.py -q
22 passed

.\.venv\Scripts\python.exe -m pytest -q
481 passed in 46.90s
```

当前状态：

- 8001 服务已重启并加载“正在思考”提示。
- 阶段 24 仍未提交、未创建 `phase-24-complete` tag、未推送，继续等待用户人工核验。

## 人工测试反馈修复：错误原因必须进入聊天流

时间：2026-06-11

用户继续反馈：输入“堆石”后页面只显示 `error`，聊天区没有任何输出。用户追问的关键点是：为什么会失败，而不是只需要显示错误状态。

定位结果：

- 使用 UTF-8 JSON 直打 `/agent/query`，问题 `堆石` + `conversation_id=1` 可以正常返回 200，并给出带引用答案，耗时约 30 秒。
- 因此 `堆石` 本身不是无结果问题，`/search/hybrid` 与 `/agent/query` 都能处理。
- 截图中的“无输出”来自前端旧失败处理：失败时移除临时 thinking 气泡，且此前还会移除临时 user 气泡，只剩顶部 `error`。
- 本机同时存在 8000 和 8001 的旧 uvicorn 进程，用户可能访问到未加载最新前端资源的端口。

修复内容：

- `app/frontend/static/app.js`
  - 新增 `appendAgentErrorMessage()`。
  - 失败或超时时保留用户问题，移除 thinking 气泡后追加 Agent 错误气泡。
  - 错误气泡显示“生成失败”和具体错误原因。
  - 会话列表加载失败时显示“加载失败”，不再一直停留在“加载中”。
- `app/frontend/static/styles.css`
  - 新增 `.chat-message--error` 样式。
- `tests/test_frontend_app.py`
  - 补充错误气泡、会话加载失败占位和样式断言。
- 已重启 8000 与 8001 两个 uvicorn 进程，确认两端静态 JS 都包含 `生成失败`、`正在思考`、`appendAgentErrorMessage`。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed

.\.venv\Scripts\python.exe -m pytest tests\test_agent_api.py tests\test_conversations_api.py -q
22 passed

.\.venv\Scripts\python.exe -m pytest -q
481 passed in 49.78s

manual API:
POST /agent/query {"question":"堆石","conversation_id":1}
200 OK，返回带引用答案
```

当前状态：

- 8000 和 8001 均已重启并加载最新前端。
- 阶段 24 仍未提交、未创建 `phase-24-complete` tag、未推送，继续等待用户人工核验。

## 人工测试反馈修复：寒暄问候不应被拒答

时间：2026-06-11

用户反馈：如果输入“你好”这类寒暄，系统也会被 RAG 拒答。该行为不符合产品预期。

定位结论：

- “你好”不是资料不足，也不是需要 off-topic 拒答的知识问题。
- 它应该被识别为寒暄/引导，直接返回友好提示，不调用检索、不调用真实模型、不计为 RAG 失败。

修复内容：

- `app/services/agent/service.py`
  - `AgentIntent` 新增 `greeting`。
  - `detect_intent()` 增加 `is_greeting()` 判断。
  - `AgentService.query()` 对 greeting 直接返回使用引导：
    “你好，我是堆石混凝土资料库 Agent。你可以问我堆石混凝土的概念、施工工艺、水化热、充填性能、工程案例，或让我检索相关资料。”
  - greeting 不调用工具、不检索、不调用模型，`refused=False`。
- `tests/test_agent_service.py`
  - 补充 greeting 意图和服务层返回测试。
- `tests/test_agent_api.py`
  - 补充 `/agent/query` 输入 `你好` 返回 200、无 tool_calls、非拒答的测试。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_agent_service.py tests\test_agent_api.py -q
25 passed

.\.venv\Scripts\python.exe -m pytest -q
483 passed in 48.80s

manual API:
POST /agent/query {"question":"你好","top_k":2}
8000: 200，返回友好引导
8001: 200，返回友好引导
```

当前状态：

- 8000 和 8001 均已重启并加载 greeting 修复。
- 阶段 24 仍未提交、未创建 `phase-24-complete` tag、未推送，继续等待用户人工核验。

## 人工测试反馈调整：前端主入口收敛到 Agent

时间：2026-06-11

用户反馈：前端同时存在“问答”“检索”和“Agent”多个入口，容易让普通用户困惑。阶段 24 已经让 Agent 承接多轮会话、会话持久化、自动路由、workflow/citation/refusal 展示，因此普通界面应只保留 Agent 对话框。

处理决策：
- 前端首页隐藏独立“问答 + 引用”面板，只保留 Agent 对话框作为用户主入口。
- 前端首页隐藏独立“检索 + 片段”面板；该区域直接暴露 keyword/vector/hybrid 召回和 chunk 查看，更适合开发调试，不作为普通用户入口。
- 后端 `POST /chat` 不删除、不改契约，继续作为单轮引用式 RAG baseline、回归测试接口和 Agent 工具底层能力的一部分。
- 后端 `POST /search`、`POST /search/vector`、`POST /search/hybrid` 不删除、不改契约，继续作为检索质量调试、自动评测和 Agent 底层能力。
- `app/frontend/static/app.js` 中的 `/chat` 和 `/search` 调用代码暂不删除；因为对应表单所在面板已隐藏，普通用户不会触发，同时保留调试和后续回滚余地。

修改内容：
- `app/frontend/index.html`：给 `operations-grid` 增加 `hidden style="display: none"`，浏览器不再展示“检索”和“片段”调试区。
- `app/frontend/index.html`：给 `answer-grid` 增加原生 `hidden` 属性，浏览器不再展示“问答”和独立引用侧栏。
- `app/frontend/static/styles.css`：增加 `[hidden] { display: none !important; }`，并在 `answer-grid` 上增加 `style="display: none"` 作为缓存和样式覆盖兜底。
- `tests/test_frontend_app.py`：补充断言，确认 `operations-grid` 和 `answer-grid` 处于隐藏状态，同时 Agent 表单、会话列表和工具调用区域仍存在。

验证结果：
```text
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed in 0.80s

.\.venv\Scripts\python.exe -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py tests\test_frontend_app.py -q
35 passed in 9.66s

.\.venv\Scripts\python.exe -m pytest -q
483 passed in 42.80s

browser:
http://127.0.0.1:8000/?v=phase24-agent-only-search-hidden
operationsGridHiddenAttr=true
operationsGridInlineStyle="display: none"
operationsGridDisplay="none"
searchTitleVisible=false
answerGridHiddenAttr=true
answerGridInlineStyle="display: none"
answerGridDisplay="none"
chatTitleVisible=false
agentGridVisible=true
horizontalOverflow=false
```

当前状态：
- 8000 和 8001 实际监听端口均已加载最新后端；如浏览器仍显示旧问答区，使用 Ctrl+F5 或带查询参数刷新以避开浏览器缓存。
- 阶段 24 仍未提交、未创建 `phase-24-complete` tag、未推送，继续等待用户人工核验。

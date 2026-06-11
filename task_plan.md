# 阶段 24 任务计划：多轮对话 UI 与会话持久化

## 目标

在阶段 23「Agentic 评测闭环与自动模式路由」已完成并合并到 `main` 的基础上，完成阶段 24「多轮对话 UI 与会话持久化」：新增后端会话模型与 API，把前端 Agent 面板从单次问答改为聊天气泡式多轮对话，接入服务端会话持久化和上下文摘要压缩，使用户刷新页面后仍可看到历史对话，且长对话不超出 LLM 上下文窗口。阶段完成后停在用户人工核验前，不提交、不打 tag、不推送。

## 硬约束

- 阶段 24 开发完成前后均不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
- 不移动任何已有阶段 tag，尤其是 `phase-23-complete`。
- 保留用户或其他 session 的已有改动，不重置 Git，不覆盖无关文件。
- 不做 WebSocket/SSE 流式输出（留给后续阶段）。
- 不做用户认证/登录系统（会话按浏览器 session 隔离即可）。
- 不做跨会话长期记忆或 RAG over 历史对话。
- 不引入 LangGraph Checkpointer（当前图复杂度不需要断点续跑）。
- 不引入前端框架（React/Vue）或 Node 构建链。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 不被破坏。
- 人工核验反馈后，前端普通用户主入口收敛到 Agent；`POST /chat`、`POST /search`、`POST /search/vector`、`POST /search/hybrid` 后端 API 继续保留为单轮 RAG baseline、检索调试和回归测试接口。

## Phase 顺序

### Phase 0：启动校准与文件计划

**状态：已完成**

**解决的问题**：确认阶段 23 的最终状态、tag、main 起点和阶段 24 分支，避免在错误基线上继续开发。

**RAG 链路位置**：阶段起点校准，不改运行链路。

**为什么现在做**：阶段 24 依赖阶段 23 的自动路由和前端只读模式指示器，必须先确认已进入 `main`。

**任务**
- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读阶段 23 设计文档、phase review，以及根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 核对 `phase-23-complete` tag、`main`、`origin/main` 是否指向同一阶段 23 最终提交。
- 从阶段 23 合并后的 `main` 创建或切换到 `codex/phase-24-multi-turn-conversation`。
- 将根目录三份 Planning with Files 文件校准为阶段 24。

**验证方式**
- `git status -sb`
- `git log --oneline -5`
- `git merge-base --is-ancestor phase-23-complete main`

**完成标准**
- 当前分支为 `codex/phase-24-multi-turn-conversation`。
- `phase-23-complete` 不移动，且已并入 `main`。
- `task_plan.md`、`findings.md`、`progress.md` 已切换为阶段 24。

**完成记录（2026-06-11，Codex）**
- 已读取入口规则、阶段 23 设计与验收报告、阶段 24 Planning 文件。
- `main` / `origin/main` 均指向阶段 23 合并提交 `8fc1cfa`。
- `phase-23-complete` 指向阶段 23 最终功能提交 `dd7d953`，未移动。
- 已确认 `phase-23-complete` 是 `main` 和 `origin/main` 的祖先。
- 已从阶段 23 合并后的 `main` 创建并切换到 `codex/phase-24-multi-turn-conversation`。

### Phase 1：阶段 24 设计文档

**状态：已完成**

**解决的问题**：把会话模型、API、前端对话 UI、上下文摘要策略和安全边界先固化成可审查设计。

**RAG 链路位置**：横跨数据库模型、API 层、default AgentService、agentic LangGraph、前端 Agent 面板。

**为什么现在做**：先明确完成标准和边界，后续代码实现、测试和文档可以对齐同一个设计。

**任务**
- 新增 `docs/stage24_multi_turn_conversation.md`。
- 说明当前 `history` 字段的局限性（前端传递、不持久化、刷新即丢）。
- 说明 `Conversation`、`Message` 模型设计和字段含义。
- 说明会话 API 端点设计（创建、列表、详情、删除）。
- 说明 `/agent/query` 的 `conversation_id` 集成方式和向后兼容（不传 conversation_id 时行为不变）。
- 说明上下文摘要压缩策略（阈值、摘要方式、存储方式）。
- 说明前端聊天 UI 设计（气泡布局、消息追加、滚动、模式/工具步骤/引用的保留展示）。
- 说明前端会话管理设计（会话列表/侧边栏、新建/切换/删除）。
- 说明安全边界和完成标准。

**验证方式**
- 人工阅读文档结构是否覆盖阶段 24 验收项。

**完成标准**
- 设计文档存在且覆盖模型、API、前端、摘要、测试、安全与收尾标准。

**完成记录（2026-06-11，Codex）**
- 已新增 `docs/stage24_multi_turn_conversation.md`。
- 文档已覆盖当前 `history` 局限、`Conversation` / `Message` 模型、`/conversations` API、`/agent/query` 集成、agentic history、摘要压缩、前端聊天 UI、测试方案、安全边界和完成标准。

### Phase 2：Conversation 与 Message 模型

**状态：已完成**

**解决的问题**：后端目前没有会话持久化能力；`QuestionAnswerLog` 是扁平日志，无法支撑多轮对话的分组、加载和展示。

**RAG 链路位置**：数据库模型层，为 API 和前端提供持久化基础。

**为什么现在做**：API 和前端都依赖模型层先就绪。

**任务**
- 在 `app/db/models.py` 新增 `Conversation` 模型（id、title、created_at、updated_at）。
- 在 `app/db/models.py` 新增 `Message` 模型（id、conversation_id FK、role [user/assistant/summary]、content、mode [default/agentic/null]、metadata_json [可选，存 workflow_steps/citations/refusal 等结构化信息]、created_at）。
- 在 `app/db/repositories.py` 或新建 `app/db/conversation_repository.py` 新增 CRUD 操作：创建会话、获取会话列表、获取单个会话的消息、追加消息、删除会话。
- 补充模型和 repository 的单元测试。

**验证方式**
- 运行新增模型/repository 测试。
- 确认 SQLAlchemy `Base.metadata.create_all` 可以自动建表。

**完成标准**
- Conversation 和 Message 表可正确创建和 CRUD。
- 测试覆盖创建、查询、追加消息、删除会话。

**完成记录（2026-06-11，Codex）**
- 已在 `app/db/models.py` 新增 `Conversation` 和 `Message` 模型，`Conversation.messages` 使用 `cascade="all, delete-orphan"`。
- 已在 `app/db/repositories.py` 新增 `ConversationCreate`、`MessageCreate`、`ConversationRepository` 和 metadata 序列化/反序列化 helper。
- 已补充 `tests/test_db_models.py` 与 `tests/test_repositories.py`，覆盖建表、消息追加、metadata_json、会话列表、标题更新和删除级联。
- 验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_db_models.py tests\\test_repositories.py -q`，8 passed。

### Phase 3：会话 API 端点

**状态：已完成**

**解决的问题**：前端需要通过 HTTP API 管理会话（创建、列表、查看历史、删除），目前没有这些端点。

**RAG 链路位置**：FastAPI 路由层，`/conversations` 前缀。

**为什么现在做**：模型层完成后，API 层是前端和集成测试的前提。

**任务**
- 新增 `app/api/conversations.py`（或在现有路由文件中扩展）。
- `POST /conversations`：创建新会话，返回 conversation_id 和 title。
- `GET /conversations`：列出所有会话（按 updated_at 降序，带分页或 limit）。
- `GET /conversations/{conversation_id}/messages`：获取指定会话的所有消息。
- `DELETE /conversations/{conversation_id}`：删除会话及其所有消息。
- 在 `app/schemas/` 新增请求/响应 schema。
- 在 `app/main.py` 注册新路由。
- 补充 API 测试。

**验证方式**
- 运行新增 API 测试。
- 确认端点的 CRUD 行为正确。

**完成标准**
- 四个端点可用，测试覆盖正常和异常路径。

**完成记录（2026-06-11，Codex）**
- 已新增 `app/schemas/conversation.py`。
- 已新增 `app/api/conversations.py`，包含 `POST /conversations`、`GET /conversations`、`GET /conversations/{conversation_id}/messages`、`DELETE /conversations/{conversation_id}`。
- 已在 `app/main.py` 注册会话路由。
- 已新增 `tests/test_conversations_api.py`，覆盖创建、默认标题、列表、消息 metadata 返回、删除、404 和 limit。
- 验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_db_models.py tests\\test_repositories.py tests\\test_conversations_api.py -q`，14 passed。

### Phase 4：`/agent/query` 会话集成与历史装配

**状态：已完成**

**解决的问题**：`/agent/query` 目前每次请求独立，不记录也不加载对话历史；用户无法进行追问式交互。

**RAG 链路位置**：FastAPI `/agent/query` → 历史装配 → default AgentService / agentic LangGraph。

**为什么现在做**：会话 API 就绪后，核心查询端点才能接入会话上下文。

**任务**
- `AgentQueryRequest` 新增可选字段 `conversation_id: str | None = None`。
- 当传入 `conversation_id` 时：
  - 加载该会话的历史消息。
  - 将历史组装为 `history` 传入 AgentService 或 agentic LangGraph。
  - 请求完成后，将用户问题和助手回答各作为一条 Message 追加到会话。
- 当不传 `conversation_id` 时：行为完全不变（向后兼容）。
- 历史装配需要考虑摘要（Phase 5）——如果会话有摘要消息，用摘要替代被摘要覆盖的旧消息。
- 补充测试：有 conversation_id 时消息正确持久化、历史正确装配、无 conversation_id 时行为不变。

**验证方式**
- 运行集成测试。
- 确认多轮追问场景中历史正确传递。

**完成标准**
- `/agent/query` 支持 conversation_id，消息自动持久化，历史正确装配。
- 不传 conversation_id 时行为不变。

**完成记录（2026-06-11，Codex）**
- `AgentQueryRequest` 已新增可选 `conversation_id`。
- `/agent/query` 传入 `conversation_id` 时会校验会话存在、加载历史、调用 default/agentic 链路，并持久化 user/assistant 两条消息。
- `/agent/query` 不传 `conversation_id` 时保持阶段 23 行为，不写入会话消息。
- agentic 路径 `run_agentic_rag()` 已新增可选 `history` 参数，`AgenticState` 已新增 `history` 字段，generate 节点会用历史补全上下文追问。
- 已新增测试覆盖会话持久化、缺失会话 404、agentic history 参数。
- 验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_db_models.py tests\\test_repositories.py tests\\test_conversations_api.py tests\\test_agent_api.py tests\\test_agentic_graph.py -q`，47 passed。

### Phase 5：上下文摘要压缩

**状态：已完成**

**解决的问题**：长对话的消息历史可能超出 LLM 上下文窗口或导致检索质量下降，需要在适当时机压缩旧消息为摘要。

**RAG 链路位置**：会话历史装配层，在 `/agent/query` 的历史加载和 LLM 调用之间。

**为什么现在做**：会话集成（Phase 4）完成后，需要处理历史增长带来的上下文管理问题。

**任务**
- 实现摘要函数：当会话消息数超过阈值（建议 8 轮 = 16 条消息）时，用 LLM 将旧消息压缩为一段摘要。
- 摘要作为 `role="summary"` 的 Message 存入会话，被摘要覆盖的旧消息保留但不再进入 prompt。
- 历史装配逻辑：最新摘要 + 摘要之后的近期消息 → 作为 history 传入。
- 摘要触发时机：在 `/agent/query` 请求处理的末尾，追加新消息后检查是否需要摘要。
- 确保 deterministic provider 下摘要可测试（摘要函数可接受 chat_model_provider 参数）。
- 补充测试。

**验证方式**
- 运行摘要相关测试。
- 模拟超过阈值的对话，确认摘要生成和历史装配行为正确。

**完成标准**
- 长对话自动触发摘要压缩。
- 摘要后的历史装配正确、不丢失关键上下文信号。
- deterministic provider 下可测试。

**完成记录（2026-06-11，Codex）**
- 已新增 `app/services/conversation/history.py`，集中管理 history 装配、summary 触发和摘要生成。
- 非 summary 消息超过 16 条时触发摘要，保留最近 6 条非 summary 消息。
- summary 作为 `role="summary"` 消息写入会话，metadata 记录 `summary_of_message_ids` 和保留近期消息数。
- `/agent/query` 成功持久化助手消息后会调用 `summarize_conversation_if_needed()`。
- 已补充 `tests/test_conversation_summary.py` 和 agent API 长会话摘要测试。
- 验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_db_models.py tests\\test_repositories.py tests\\test_conversations_api.py tests\\test_conversation_summary.py tests\\test_agent_api.py tests\\test_agentic_graph.py -q`，51 passed。

### Phase 6：前端聊天 UI

**状态：已完成**

**解决的问题**：当前 Agent 面板每次提交覆盖上一次结果，用户无法看到对话历史，不是"对话式交流"体验。

**RAG 链路位置**：前端 Agent 面板，从表单 + 单结果框改为聊天气泡列表。

**为什么现在做**：后端会话和历史装配就绪后，前端是用户直接感知的部分。

**任务**
- Agent 面板的 `data-agent-answer-box` 改为可滚动的聊天消息列表容器。
- 用户提交问题后：在列表追加用户气泡，发请求，收到响应后追加助手气泡。
- 助手气泡保留现有的 mode badge、iteration badge、引用标记、拒答分类、workflow steps 展示能力。
- 工具调用/workflow 步骤面板保持独立区域，跟随当前选中/最新消息更新。
- 支持自动滚动到最新消息。
- 输入区域保持底部固定（textarea + 运行按钮）。
- 保持原生 HTML/CSS/JS，不引入前端框架。
- 所有动态 HTML 继续使用 `escapeHtml()`。
- 补充前端静态测试。

**验证方式**
- 运行前端测试。
- 浏览器手动验证：多次提交后消息列表正确累积、滚动正常、mode/workflow/citation 展示正确。

**完成标准**
- 用户可以看到完整的对话历史，消息追加而非覆盖。
- 现有的可观测字段（mode、workflow_steps、citations、refusal_category）在聊天 UI 中保留。

**完成记录（2026-06-11，Codex）**
- Agent 结果区已从单次 `article.answer-box` 改为可滚动 `div.chat-messages`，保留 `data-agent-answer-box` 锚点并新增 `data-agent-chat-list`。
- `submitAgent()` 会先追加用户气泡，响应成功后追加助手气泡，不再覆盖旧结果。
- 助手气泡保留 mode、iteration、citations、invalid_citations、sources、refusal_category、reasoning_summary。
- workflow/tool 面板继续跟随最新响应更新。
- Agent 请求失败时 mode 指示器会从 `pending` 恢复到 `auto`。
- 已补充前端静态测试。
- 验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_frontend_app.py tests\\test_conversations_api.py tests\\test_agent_api.py -q`，26 passed。

### Phase 7：前端会话管理

**状态：已完成**

**解决的问题**：用户刷新页面后需要能找回之前的对话，也需要能开始新对话或切换到不同对话。

**RAG 链路位置**：前端会话管理层，与 `/conversations` API 交互。

**为什么现在做**：聊天 UI 完成后，会话管理是完整体验的最后一环。

**任务**
- 在 Agent 面板区域增加会话管理 UI（侧边栏或顶部会话列表）。
- "新建对话"按钮：调用 `POST /conversations`，清空聊天区域。
- 会话列表：调用 `GET /conversations`，展示最近会话（标题 + 时间），点击切换。
- 切换会话：调用 `GET /conversations/{id}/messages`，加载历史消息到聊天区域。
- 删除会话：调用 `DELETE /conversations/{id}`，从列表移除。
- 会话标题：默认使用第一条用户消息的前 N 个字符；后续可以优化为 LLM 生成标题。
- 页面加载时自动加载最近一次会话（如果有）。
- 补充前端测试。

**验证方式**
- 运行前端测试。
- 浏览器手动验证：新建、切换、删除会话，刷新页面后恢复。

**完成标准**
- 用户可以管理多个对话，刷新不丢失，切换流畅。

**完成记录（2026-06-11，Codex）**
- Agent 面板已新增会话管理栏：新建、会话列表、刷新、删除。
- 前端新增 `/conversations`、`/conversations/{id}`、`/conversations/{id}/messages` API 调用。
- 页面初始化会加载最近会话；无会话时自动创建新会话。
- 切换会话会拉取消息并重建聊天列表。
- 发送 `/agent/query` 时会带上当前 `conversation_id`。
- 删除当前会话后会自动加载下一条会话；无剩余会话时创建新会话。
- 已补充前端静态测试。
- 验证：`.\\.venv\\Scripts\\python.exe -m pytest tests\\test_frontend_app.py tests\\test_conversations_api.py tests\\test_agent_api.py tests\\test_conversation_summary.py -q`，29 passed。

### Phase 8：回归验证与质量门

**状态：已完成**

**解决的问题**：阶段 24 涉及数据库模型、API、前端大改和上下文管理，需要确认既有功能未受破坏。

**RAG 链路位置**：全链路回归。

**为什么现在做**：功能开发完成后必须先测试，再进入文档收尾。

**任务**
- 运行阶段 24 新增测试。
- 运行后端/API/前端相关回归测试。
- 运行全量测试，目标 >= 463（阶段 23 基线）。
- 若失败，定位并修复，补充必要测试。
- 用浏览器桌面/移动视口检查聊天 UI 和会话管理。

**验证方式**
- `pytest` 全量测试。
- 浏览器桌面和移动视口验证。

**完成标准**
- 全量测试通过，且不依赖真实 API。
- 浏览器验证聊天 UI 和会话管理基本可用。

**执行记录**
- 全量测试已通过：`.\\.venv\\Scripts\\python.exe -m pytest -q`，479 passed。
- 浏览器桌面视口 `1280x720` 已验证：会话列表、聊天列表、新建/删除控件存在，旧 `data-agent-mode` 下拉不存在，无横向溢出，无控制台 error。
- 通过“查看来源详情 + 缺失 source_id”路径提交 Agent 请求，触发 `/agent/query` 的非模型调用分支，页面追加 1 条用户气泡和 1 条 Agent 气泡，并显示拒答分类元数据。
- 浏览器移动视口 `390x844` 已验证：会话栏和聊天列表可见，无横向溢出，无控制台 error。
- Phase 8 未让真实 API 成为全量测试或浏览器基本验收前提。

### Phase 9：文档同步、Obsidian 收尾与人工核验待提交状态

**状态：已完成**

**解决的问题**：把阶段 24 的设计、代码行为同步到项目文档和 Obsidian，并停在可核验状态。

**RAG 链路位置**：项目知识层和阶段交付边界。

**为什么现在做**：测试通过后文档才能准确描述最终行为。

**任务**
- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 必要时更新 `AGENT.MD`。
- 建立或更新 Obsidian 阶段 24 目录、汇报索引和各 Phase 小汇报。
- 确认未创建 `phase-24-complete` tag。
- 汇总主要改动、测试结果、未提交状态和人工核验重点。

**验证方式**
- `git status -sb`
- `git tag --list phase-24-complete`
- 文档无过期表述。

**完成标准**
- 当前分支保持阶段 24 分支。
- 所有阶段 24 改动未提交，等待用户人工核验。

**执行记录**
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 已新增/更新 Obsidian 本地知识库：
  - `obsidian-vault/阶段/阶段 24 - 多轮对话 UI 与会话持久化.md`
  - `obsidian-vault/阶段汇报/阶段 24 - 多轮对话 UI 与会话持久化/阶段 24 Phase 汇报索引.md`
  - Phase 0 到 Phase 9 小汇报
  - `obsidian-vault/阶段汇报索引.md`
  - `obsidian-vault/阶段索引.md`
  - `obsidian-vault/首页.md`
  - 阶段 24 相关知识点笔记
- 阶段 24 仍未提交、未创建 `phase-24-complete` tag、未推送，等待用户人工核验。

### Post-review 调整：前端主入口收敛到 Agent

**状态：已完成**

**解决的问题**：前端同时展示“问答”“检索”和“Agent”多个入口，容易让普通用户混淆单轮 `/chat`、底层召回 `/search*` 与多轮 `/agent/query` 的差异。
**RAG 链路位置**：仅影响前端入口展示；后端 `/chat` 单轮 RAG baseline 和 `/search*` 检索 baseline 保留，`/agent/query` 继续作为多轮会话主入口。
**为什么现在做**：阶段 24 已完成 Agent 多轮会话和会话持久化，人工测试时暴露出两个入口的产品认知成本，应在人工核验前收敛 UI。

**任务**
- 隐藏首页独立“问答 + 引用”面板。
- 隐藏首页独立“检索 + 片段”调试面板。
- 保留后端 `POST /chat` API、相关测试和底层引用式问答链路。
- 保留后端 `POST /search`、`POST /search/vector`、`POST /search/hybrid` API、相关测试和底层召回链路。
- 补充前端测试，确认普通用户首页只显示 Agent 主入口。

**验证方式**
- `.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_chat_api.py tests\test_agent_api.py tests\test_frontend_app.py -q`
- `.\.venv\Scripts\python.exe -m pytest -q`
- 浏览器 DOM/CSS 核验 `operationsGridDisplay="none"`、`answerGridDisplay="none"`，`agentGridVisible=true`。

**完成记录：2026-06-11，Codex**
- `app/frontend/index.html` 已将 `.operations-grid` 标记为 `hidden style="display: none"`。
- `app/frontend/index.html` 已将 `.answer-grid` 标记为 `hidden style="display: none"`。
- `app/frontend/static/styles.css` 已增加 `[hidden] { display: none !important; }` 兜底规则。
- `tests/test_frontend_app.py` 已增加检索区、问答区隐藏状态和 CSS 兜底断言。
- 聚焦测试 6 passed、组合回归 30 passed、全量测试 483 passed。
- 浏览器核验通过：检索区和问答区不可见，Agent 区可见，无横向溢出。

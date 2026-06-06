# Findings & Decisions

## Requirements
- 用户要求本线程持续推进到阶段 7：Agent 化完整完成。
- 用户要求线程名称为 `阶段7-Agent化`。
- 用户要求先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 用户要求确认阶段 6 已完成，确认 `phase-6-complete` tag 指向阶段 6 最终功能提交，不移动已有阶段 tag。
- 用户要求目标分支为 `codex/phase-7-agent-tools`。
- 用户要求正式开发前用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 7 不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不做联网爬虫扩展。
- 阶段 7 核心目标是把阶段 6 已稳定的 RAG 能力包装成受控、可测试、可追踪的 Agent 工具调用链路。
- 阶段 7 优先只读工具，写入型动作不能自动执行；source reindex 如接入必须有明确请求字段和测试约束。
- 开发过程中先不要写入 Obsidian 小 Phase 汇报；等阶段 7 全部开发、测试、普通文档完成后，再统一补齐 Obsidian 10 项 Phase 汇报。

## Current Project Findings
- 当前已从 `codex/phase-6-evaluation` 切换到 `codex/phase-7-agent-tools`。
- 阶段 6 tag `phase-6-complete` 指向 `fa11702150d79e036159f427f567051e92bfe8c2`，提交信息为 `feat: complete phase 6 evaluation`。
- 切换前工作区干净，阶段 7 分支此前不存在。
- 阶段 7 启动后全量测试通过：141 passed，说明阶段 7 起点没有破坏阶段 6 既有链路。
- 阶段 6 已实现 `HybridSearchService`、`POST /search/hybrid`、`scripts/evaluate_hybrid_search.py`、`retrieval_error_cases.csv`。
- 阶段 6 评测结果为 keyword 15/15、vector 11/15、hybrid 15/15、chat 6/6、全量测试 141 passed。
- `AGENT.MD` 已明确下一步最适合进入阶段 7：Agent 化。

## Architecture Findings
- `app/main.py` 使用 `create_app()` 组装 FastAPI 应用，当前注册 frontend、health、documents、search、chat、sources 路由。
- 当前分层是 API、Schema、Service、DB、Source Registry、Model Provider、Frontend。
- 阶段 7 应新增 Agent 层，位置应在 API 层和既有 service 之间，负责编排工具，不直接处理数据库细节。
- 当前 RAG 主链路是 sources -> documents/chunks -> chunk_embeddings -> keyword/vector/hybrid retrieval -> prompt -> chat model -> citations -> frontend。
- Agent 层必须复用这个链路，不能直接拼 SQL 或绕过已有问答与引用逻辑。

## Existing Code Findings
- `KeywordSearchService` 已提供关键词检索，包含同义词扩展、泛词降权和来源均衡。
- `VectorSearchService` 已提供 deterministic embedding 下的向量检索。
- `HybridSearchService` 已合并 keyword/vector 候选，按 chunk 去重、归一化和加权排序。
- `CitationAnswerService` 已支持 `retrieval_mode` 为 `auto`、`vector`、`keyword`、`hybrid`，并返回 citations、sources、refused、model 信息。
- `SourceRepository` 和 `SourceRegistryService` 已支持来源查询、同步和 reindex；阶段 7 只读工具可直接查询 repository，暂不自动调用 reindex。
- `QuestionAnswerLogRepository` 已记录 chat 问答日志；Agent 工具调用日志可以先作为响应结构返回，是否入库可作为后续扩展。

## API Contract Findings
- `POST /search`：关键词检索 baseline。
- `POST /search/vector`：向量检索 baseline。
- `POST /search/hybrid`：阶段 6 优化检索入口。
- `POST /chat`：引用式问答入口。
- `GET /sources`、`GET /sources/{source_id}`：来源查询入口。
- 阶段 7 新增 `POST /agent/query` 时不能破坏以上入口的请求和响应结构。

## Evaluation Findings
- `data/evaluation/keyword_queries.csv` 是 keyword/vector/hybrid 检索评测主数据集。
- `data/evaluation/chat_queries.csv` 是引用式问答评测主数据集。
- 阶段 7 应新增 Agent 评测脚本，复用现有问题，检查工具选择、来源命中、citation 有效性、拒答匹配和工具调用记录。
- Agent 评测不能只验证 HTTP 200，还要证明没有降低阶段 6 的检索和引用质量。

## Frontend Findings
- 当前前端是 FastAPI 静态文件 + 原生 HTML/CSS/JS。
- 工作台已有 sources、documents、chunks、keyword/vector/hybrid search、chat、citations、source sync 和 source reindex 入口。
- 阶段 7 如更新前端，应只新增 Agent 最小面板：问题输入、回答、工具调用记录、引用来源；不重构布局，不引入构建链。

## Data Source Findings
- 阶段 7 不新增外部资料来源，不做联网爬虫扩展。
- Agent 只读工具查询的是已有 `sources`、`documents/chunks`、`chunk_embeddings` 和评测数据。
- `docs/data_sources.md` 阶段收尾时应说明 Agent 工具调用不改变来源合规边界。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 新增 Agent 层而不是改造 chat service | 保持 `CitationAnswerService` 稳定，让 Agent 只做工具选择和结果编排 |
| 第一版 Agent 使用规则式意图识别 | 不依赖真实 LLM 或复杂 workflow，便于本地测试和面试解释 |
| Agent 默认优先 hybrid search | 阶段 6 已证明 hybrid 当前质量最好且不破坏 baseline |
| 只读工具优先 | 降低风险，避免 Agent 自动修改来源或资料库 |
| 工具返回结构化结果 | 便于前端展示、评测和排查 |
| 新增 Agent 评测脚本 | 阶段 7 的完成必须能被量化证明，不只是 API 可调用 |
| 先新增 `docs/agent_design.md` 和文档断言测试 | 先把工具边界、权限约束和评测方式固定下来，再进入代码实现 |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| Agent 设计 | `docs/agent_design.md`, `tests/test_agent_design.py` |
| Agent 工具层 | `app/services/agent/__init__.py`, `app/services/agent/tools.py` |
| Agent 编排 | `app/services/agent/service.py` |
| Agent schema/API | `app/schemas/agent.py`, `app/api/agent.py`, `app/main.py` |
| Agent 评测 | `scripts/evaluate_agent.py`, `data/evaluation/agent_queries.csv`, `data/evaluation/agent_results.csv` |
| 测试 | `tests/test_agent_tools.py`, `tests/test_agent_service.py`, `tests/test_agent_api.py`, `tests/test_evaluate_agent.py` |
| 前端 | `app/frontend/index.html`, `app/frontend/static/app.js`, `app/frontend/static/styles.css`, `tests/test_frontend_app.py` |
| 文档 | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | 阶段 7 页面、Phase 汇报、首页、阶段索引、分类页和知识点 |

## Term Explanations
| Term | Explanation |
|------|-------------|
| Agent | 能根据用户意图选择工具并组织结果的编排层 |
| Tool | 被 Agent 调用的受控能力包装，例如检索、问答、来源查询 |
| Orchestration | 编排，决定调用哪个工具、调用顺序和结果汇总方式 |
| Tool call | 一次工具调用记录，包括工具名、输入摘要、输出摘要、成功或失败 |
| Read-only | 只读，不修改数据库、不写入来源、不触发重新索引 |
| Intent routing | 意图路由，根据用户问题判断应该搜索、问答还是查来源 |
| Auditability | 可审计性，能回看 Agent 调用了什么工具、依据是什么、是否拒答 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 暂无 | 暂无 |

## Resources
- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/evaluation_plan.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `app/services/retrieval/keyword_search.py`
- `app/services/retrieval/vector_search.py`
- `app/services/retrieval/hybrid_search.py`
- `app/services/generation/answer_service.py`
- `app/api/search.py`
- `app/api/chat.py`
- `app/api/sources.py`
- `app/db/repositories.py`
- `data/evaluation/`
- `docs/agent_design.md`

## Phase 1 Findings
- `docs/agent_design.md` 已明确阶段 7 不引入复杂 LangGraph workflow，采用轻量规则式编排。
- 最小工具集固定为 `search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- 权限边界固定为只读优先，`source reindex` 不自动执行；后续若要接入写入动作，必须有 `allow_write_actions=true` 类显式字段和测试。
- `reasoning_summary` 被定义为可审计摘要，不暴露内部敏感推理。
- `tests/test_agent_design.py` 已覆盖工具名、只读边界、`POST /agent/query`、`tool_calls`、`reasoning_summary` 和 Agent 评测文件路径。

## Phase 2 Findings
- 新增 `app/services/agent/`，作为阶段 7 Agent 工具层。
- `AgentToolbox` 已实现 5 个工具：`search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- 工具层复用既有 service：`KeywordSearchService`、`HybridSearchService`、`CitationAnswerService`、`SourceRepository`。
- 工具调用记录统一使用 `AgentToolCallRecord`，包含工具名、输入摘要、输出摘要、成功状态和错误信息。
- 工具结果统一使用 `AgentToolResult`，包含 answer、search_results、sources、citations、refused 和 refusal_reason。
- `get_source_detail` 找不到来源时返回可审计失败结果，而不是抛出未处理异常。
- `tests/test_agent_tools.py` 覆盖关键词检索、混合检索、引用式问答、来源列表、来源详情、缺失来源和非法参数。

## Phase 3 Findings
- 新增 `app/services/agent/service.py`，作为 Agent 编排服务。
- `AgentService.query()` 负责校验 question/top_k/max_tool_calls，并根据意图选择工具。
- 第一版意图路由保持保守规则式：问答默认走 `answer_with_citations`，搜索走 `hybrid_search_knowledge`，来源列表走 `list_sources`，来源详情走 `get_source_detail`。
- `AgentQueryResult` 已统一返回 question、answer、tool_calls、sources、search_results、citations、refused、refusal_reason、reasoning_summary。
- 缺少 source_id 的来源详情查询会拒答并解释原因，不会误调用工具。
- `tests/test_agent_service.py` 覆盖问答、搜索、来源列表、来源详情、缺少 source_id、非法参数和意图识别辅助函数。

## Phase 4 Findings
- 新增 `app/schemas/agent.py`，定义 Agent 请求和响应结构。
- 新增 `app/api/agent.py`，实现 `POST /agent/query`。
- `app/main.py` 已注册 Agent router。
- Agent API 响应包含 question、answer、tool_calls、search_results、sources、citations、refused、refusal_reason、reasoning_summary。
- `tests/test_agent_api.py` 覆盖问答、混合检索、来源详情、空问题校验和旧 API 回归。
- 回归测试确认新增 Agent API 后，`POST /search`、`POST /chat`、`GET /sources` 仍可用。

## Phase 5 Findings
- 新增 `data/evaluation/agent_queries.csv`，覆盖 Agent 问答、Agent 搜索、来源列表、来源详情和缺失来源拒答。
- 新增 `scripts/evaluate_agent.py`，直接调用 `AgentService`，输出 `data/evaluation/agent_results.csv`。
- Agent 评测字段包含 expected_tool、actual_tools、tool_matched、refused、citations_valid、expected_source_hit、tool_call_count。
- 新增 `tests/test_evaluate_agent.py`，覆盖 Agent 评测通过、缺失来源拒答和 CSV 读写。
- 真实本地资料库运行 `scripts/evaluate_agent.py` 结果为 5/5 passed，refused=1，tool_failures=0，citation_failures=0。

## Phase 6 Findings
- 现有 FastAPI 静态工作台适合承载 Agent 最小展示，不需要新增前端构建链。
- `app/frontend/index.html` 已新增 Agent 输入区和工具调用展示区，使用 `data-agent-*` 属性保持静态测试和浏览器检查可定位。
- `app/frontend/static/app.js` 已新增 `/agent/query` 调用、Agent 回答渲染、引用渲染和 `tool_calls` 渲染。
- `app/frontend/static/styles.css` 只补充 Agent 面板所需的网格、控制区和工具调用卡片样式，没有重构原有 sources/search/chat 布局。
- `tests/test_frontend_app.py` 已覆盖 Agent 表单、工具调用区域、`/agent/query` 端点和 `renderAgentToolCalls`。
- 浏览器 smoke check 使用本地 `http://127.0.0.1:8002/`，提交“检索 filling capacity 相关资料”后，页面状态为 `answered`，工具调用显示 `hybrid_search_knowledge` 且返回 5 条混合检索结果。
- 视觉检查确认 Agent 区域可见，回答、引用标签和工具调用列表没有明显遮挡或布局错位。

## Phase 7 Findings
- 阶段 7 收尾复跑评测：keyword 15/15、vector 11/15、hybrid 15/15、chat 6/6、agent 5/5，说明 Agent 没有破坏阶段 6 质量基线。
- 全量测试结果为 163 passed。
- `README.md` 已同步阶段 7 当前状态、Agent API、评测结果、前端能力、测试数和阶段 7 面试表达。
- `docs/progress.md` 已新增 2026-06-06 阶段 7 完成记录，并把最新状态从阶段 6 更新到阶段 7。
- `docs/architecture.md` 已新增阶段 7 Agent 总体框架、工具层、编排层、API 和评测策略。
- `docs/data_sources.md` 已说明阶段 7 不新增外部资料来源，Agent 只读查询既有 sources、documents/chunks 和评测文件。
- `AGENT.MD` 已把当前推荐起点从阶段 7 开发前校准到阶段 7 完成后，并记录 `phase-7-complete` tag 口径。
- Obsidian 已新增 `obsidian-vault/阶段/阶段 7 - Agent 化.md`、`阶段 7 Phase 汇报索引`、Phase 0 到 Phase 7 汇报、`Agent 工具调用` 分类和 3 篇知识点。
- Obsidian 检查确认 Phase 0 到 Phase 7 每篇汇报都包含用户要求的 10 个固定小节。

## Current Hypotheses
- 第一版 Agent 不需要真实 LLM 规划；规则式工具选择已经能满足阶段 7 的可控性和可测性目标。
- `answer_with_citations` 应作为问答类问题的主工具，因为它复用现有引用、拒答和日志链路。
- `hybrid_search_knowledge` 应作为搜索类问题的主工具，因为阶段 6 已证明它能救回 vector-only 失败案例。
- Agent API 的关键价值不是“更会聊天”，而是把工具调用过程、来源和引用透明返回。

# Findings & Decisions

## Requirements
- 用户要求持续推进到阶段 8：Brain 中控层与 RAG Workflow 配置化完整完成。
- 用户要求线程名称为 `阶段8-Brain中控层与Workflow配置化`。
- 用户要求先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/agent_design.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 用户要求确认阶段 7 已完成并合并到 `main`，确认 `phase-7-complete` tag 指向阶段 7 最终功能提交，不移动已有阶段 tag。
- 用户要求目标分支为 `codex/phase-8-brain-workflow`。
- 用户要求正式开发前用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 8 不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不做大规模前端重构、不自动接入写入型 Agent 工具。
- 阶段 8 核心目标是新增 Brain 中控层、RAG Workflow 配置化、配置评测，并让 chat 与 agent 复用同一套 RAG workflow。
- 阶段 8 必须参照 Quivr 的 Brain / RetrievalConfig / WorkflowConfig 思想，但不要照搬 Quivr 代码。
- 开发过程中先不要写入 Obsidian 小 Phase 汇报；等阶段 8 全部开发、测试、普通文档完成后，再统一补齐 Obsidian 10 项 Phase 汇报。

## Current Project Findings
- 当前分支已从 `main` 创建为 `codex/phase-8-brain-workflow`。
- `main` 最新提交为 `1ab9d5b merge phase 7 agent tools`，说明阶段 7 已合并。
- `phase-7-complete` 指向 `3a1ad943abe24b2ce9a10e1ee5b2c09225760474`，提交信息为 `feat: complete phase 7 agent tools`。
- 创建阶段 8 分支前工作区干净。
- README 和 docs 当前仍显示“阶段 7 已完成，当前分支为 `codex/phase-7-agent-tools`”，阶段 8 收尾需要更新口径。
- 旧 `task_plan.md`、`findings.md`、`progress.md` 均为阶段 7 工作记忆，符合本阶段启动前校准要求。

## Quivr Findings
- Quivr 的 `Brain` 是核心中控对象，统一管理 storage、processor、vector store、embedder、LLM、chat history 和 RAG 问答。
- Quivr 的 `RetrievalConfig` 聚合 reranker、LLM config、max_history、max_files、k、prompt 和 workflow_config。
- Quivr 的 `WorkflowConfig` 通过节点描述流程，默认 RAG 类似 `START -> filter_history -> rewrite -> retrieve -> generate_rag -> END`。
- Quivr 支持 reranker，但它把 reranker 作为配置项，而不是写死在 API。
- Quivr 的 `Brain.ask()` 接受 retrieval_config，因此同一个 Brain 可以用不同检索/生成配置运行。
- 本项目应该借鉴“中控层 + 配置对象 + workflow 步骤”的架构思想，但不引入 LangGraph、不引入 Quivr 依赖、不照搬其代码。

## Architecture Findings
- 当前项目分层为 API、Schema、Service、Agent、DB、Source Registry、Model Provider、Frontend。
- 阶段 8 应新增 Brain 层，位置在 API/Agent 与现有 retrieval/generation/source service 之间。
- 当前 RAG 主链路是 sources -> documents/chunks -> chunk_embeddings -> keyword/vector/hybrid retrieval -> prompt_builder -> ChatModelProvider -> citations -> qa_logs -> frontend/agent。
- `CitationAnswerService` 当前内部直接完成校验、检索、prompt 构造、模型调用、引用提取和日志写入。
- 阶段 8 可以把上述内部步骤显式迁移到 Brain workflow；`CitationAnswerService` 作为兼容入口调用 Brain。
- Agent 的 `answer_with_citations` 当前调用 `CitationAnswerService`；只要 `CitationAnswerService` 迁移到 Brain，Agent 可以自然复用同一 workflow。

## Existing Code Findings
- `KeywordSearchService` 已提供关键词检索，包含同义词扩展、泛词降权和来源均衡。
- `VectorSearchService` 已提供 deterministic embedding 下的向量检索。
- `HybridSearchService` 已合并 keyword/vector 候选，按 chunk 去重、归一化和加权排序，是当前质量最好的检索入口。
- `CitationAnswerService` 支持 `retrieval_mode` 为 `auto`、`vector`、`keyword`、`hybrid`，并返回 citations、sources、refused、model 信息。
- `build_rag_prompt()` 已把检索结果组织成带 `[1]` 编号的上下文，阶段 8 不需要重写 prompt 体系。
- `QuestionAnswerLogRepository` 已记录 chat 问答日志；Brain workflow 的 generate_answer step 应继续复用该日志链路。
- `AgentToolbox.answer_with_citations()` 当前默认 `retrieval_mode="hybrid"`，调用 `CitationAnswerService` 并映射为 AgentToolResult。

## API Contract Findings
- `POST /search`：关键词检索 baseline。
- `POST /search/vector`：向量检索 baseline。
- `POST /search/hybrid`：阶段 6 优化检索入口。
- `POST /chat`：引用式问答入口，响应结构包含 answer、citations、sources、refused、retrieval_mode、model 信息。
- `POST /agent/query`：阶段 7 Agent 入口，搜索类走 hybrid，问答类走 answer_with_citations。
- 阶段 8 新增 Brain 内部层时，必须保持以上入口的请求和响应结构不破坏。

## Evaluation Findings
- `data/evaluation/keyword_queries.csv` 是 keyword/vector/hybrid 检索评测主数据集。
- `data/evaluation/chat_queries.csv` 是引用式问答评测主数据集。
- `data/evaluation/agent_queries.csv` 是 Agent 工具编排评测主数据集。
- 阶段 8 应新增配置化评测，比较 default_hybrid、keyword_baseline、vector_only 等配置，而不只比较单个 API。
- 配置化评测应记录 workflow steps，证明 Brain 确实按配置执行了 filter_history、rewrite_query、retrieve、optional_rerank、generate_answer。

## Frontend Findings
- 当前前端是 FastAPI 静态文件 + 原生 HTML/CSS/JS。
- 工作台已有 sources、documents、chunks、keyword/vector/hybrid search、chat、agent、citations、source sync 和 source reindex 入口。
- 阶段 8 不应变成前端重构；如果需要展示 Brain，只在文档中说明或保持最小前端变更。

## Data Source Findings
- 阶段 8 不新增外部资料来源，不做联网爬虫扩展。
- Brain workflow 读取的是已有 `sources`、`documents/chunks`、`chunk_embeddings`、`qa_logs` 和评测 CSV。
- 阶段 8 新增的 `brain_workflow_results.csv` 属于评测产物，不是新的资料来源。

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| 中控层命名为 Brain | 用户明确要求，且与 Quivr 中控抽象一致 |
| 新增 `app/services/brain/` | Brain 属于 service 层组合能力，不应放到 API、DB 或 Agent 专属目录 |
| `CitationAnswerService` 保持对外兼容 | 避免破坏 `/chat`、Agent 工具和现有评测 |
| Brain workflow 第一版用普通 Python 类 | 不引入 LangGraph，保持依赖少、行为稳定、测试简单 |
| `filter_history` 和 `rewrite_query` 第一版 no-op | 保留 Quivr 式扩展点，但不提前引入复杂 LLM 改写 |
| `optional_rerank` 第一版可用截断/空重排 | 保留 rerank 配置位置，后续真实 reranker 可接入 |
| 配置化评测独立于现有 baseline | 可以证明不同 RetrievalConfig 的质量差异，而不是覆盖旧结果 |

## Planned File Changes

| Area | Planned Files |
|------|---------------|
| Brain 设计 | `docs/brain_workflow_design.md`, `tests/test_brain_workflow_design.py` |
| Brain 配置 | `app/services/brain/config.py`, `tests/test_brain_config.py` |
| Brain workflow/service | `app/services/brain/workflow.py`, `app/services/brain/service.py`, `tests/test_brain_workflow.py`, `tests/test_brain_service.py` |
| Chat integration | `app/services/generation/answer_service.py`, existing chat tests |
| Agent integration | `app/services/agent/tools.py`, existing agent tests |
| Evaluation | `scripts/evaluate_brain_workflow.py`, `data/evaluation/brain_workflow_results.csv`, `tests/test_evaluate_brain_workflow.py` |
| Documentation | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | 阶段 8 页面、Phase 汇报、首页、阶段索引、分类页和知识点 |

## Term Explanations

| Term | Explanation |
|------|-------------|
| Brain | 本项目阶段 8 的中控层，统一组织资料库检索、配置、问答、日志和 Agent 复用链路 |
| RetrievalConfig | 检索与问答配置，控制检索模式、召回数量、分数阈值、历史数量、重排数量和 prompt 方案 |
| WorkflowConfig | 工作流配置，描述 RAG 每一步的顺序 |
| Workflow step | RAG 流程中的单个步骤，例如过滤历史、改写问题、检索、重排、生成回答 |
| no-op | 空操作。第一版保留步骤位置但不改变输入，用于稳定扩展点 |
| rerank | 重排。先召回候选资料，再重新排序，提高最终上下文质量 |
| baseline | 对照基线。用于比较新配置是否比旧检索或旧问答更好 |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| 暂无 | 暂无 |

## Phase 1 Findings
- `docs/brain_workflow_design.md` 已固定阶段 8 的边界：Brain 是中控层，不是数据库层、爬虫层、外部资料采集层，也不自动执行 source reindex。
- 设计文档明确本阶段只借鉴 Quivr 的 Brain / RetrievalConfig / WorkflowConfig 思路，不照搬 Quivr 代码，不引入复杂 LangGraph workflow。
- 默认 workflow 顺序确定为 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`。
- `filter_history` 和 `rewrite_query` 第一版允许 no-op，但必须保留结构化 step 记录，便于后续多轮问答和真实 query rewrite 扩展。
- Chat 和 Agent 的复用路线已经明确：`POST /chat` 继续通过 `CitationAnswerService`，`AgentToolbox.answer_with_citations` 继续通过同一个回答入口，内部编排迁移到 Brain。
- 阶段 1 文档断言测试结果为 `2 passed`，说明设计文档已覆盖 Brain、配置、workflow steps、边界取舍和配置化评测要求。

## Phase 2 Findings
- 新增 `app/services/brain/config.py`，用 Pydantic 定义 `RetrievalConfig`、`WorkflowConfig` 和 `WorkflowStepConfig`。
- `RetrievalConfig` 已覆盖 `retrieval_mode`、`top_k`、`min_score`、`max_history`、`rerank_top_n`、`prompt_profile`、`model_provider` 和 `workflow_config`。
- `WorkflowConfig` 默认步骤为 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`，并校验 step 不为空、不重复，且 `retrieve` 必须早于 `generate_answer`。
- `rerank_top_n=0` 表示暂不重排，保留与现有 chat 默认行为一致；当 `rerank_top_n>0` 时必须小于或等于 `top_k`。
- `RetrievalConfig.from_chat_request()` 已为后续 `CitationAnswerService.answer()` 迁移提供兼容入口。
- 阶段 2 配置模型测试结果为 `13 passed`，覆盖默认值、非法数值、非法 step、必需 step 和从 chat 参数构造配置。

## Phase 3 Findings
- 新增 `app/services/brain/workflow.py`，集中保存 `BrainAnswerResult`、`BrainRetrievalOutcome`、`BrainWorkflowStepRecord`、默认拒答文本、引用提取和检索结果过滤函数。
- 新增 `app/services/brain/service.py`，实现轻量 `BrainService`，按 `WorkflowConfig.enabled_step_names` 执行 RAG workflow。
- `BrainService.retrieve()` 复用现有 `KeywordSearchService`、`VectorSearchService`、`HybridSearchService`，`auto` 模式保持先 vector、后 keyword fallback 的旧行为。
- `optional_rerank` 第一版是可解释截断：`rerank_top_n=0` 时 disabled，`rerank_top_n>0` 时保留当前排序前 N 个结果，为后续真实 reranker 留出位置。
- `generate_answer` 继续复用 `build_rag_prompt`、`ChatModelProvider`、citation 提取和 `QuestionAnswerLogRepository`，因此 Brain 不直接写 SQL。
- Phase 3 测试结果为 `8 passed`，覆盖 workflow 函数、默认五步、auto fallback、可选 rerank、向量检索、拒答和日志记录。

## Phase 4 Findings
- `app/services/generation/answer_service.py` 已改造为兼容门面：保留 `CitationAnswerService`、`CitationAnswerResult`、`RetrievalOutcome`、`DEFAULT_REFUSAL_ANSWER`、`extract_citations` 等对外符号，内部调用 `BrainService.answer()` 和 `BrainService.retrieve()`。
- `CitationAnswerService.answer()` 继续做旧有参数校验，确保空问题、非法 top_k、非法 min_score、非法 retrieval_mode 的错误信息不退化。
- `CitationAnswerService` 返回结果仍不暴露 workflow steps，保持 `/chat` API 响应结构不变；后续配置化评测会直接调用 `BrainService` 获取 workflow steps。
- `AgentToolbox.answer_with_citations()` 未新增工具，也未改变工具 schema；由于它继续调用 `CitationAnswerService`，因此自然复用 Brain workflow。
- Phase 4 回归测试结果：answer/chat/log/agent tool 组合 `24 passed`，agent API/service 组合 `11 passed`。

## Phase 5 Findings
- 新增 `scripts/evaluate_brain_workflow.py`，复用 `data/evaluation/chat_queries.csv`，对每个问题依次运行 `default_hybrid`、`keyword_baseline`、`vector_only` 三种 Brain 配置。
- 新增 `data/evaluation/brain_workflow_results.csv`，字段覆盖 config 名称、configured/actual retrieval mode、top_k、min_score、rerank_top_n、workflow steps、workflow_succeeded、来源命中、citation 有效性、拒答匹配等。
- 新增 `tests/test_evaluate_brain_workflow.py`，测试三种配置构造、评测执行和 CSV 写出。
- 实际评测结果为 18 次 config-query run：`keyword_baseline` 6/6 passed，`default_hybrid` 4/6 passed，`vector_only` 2/6 passed。
- 该结果说明当前离线 deterministic embedding 和现有资料库条件下，keyword baseline 对 chat 评测集最稳；hybrid 和 vector_only 后续仍需要围绕 embedding 质量、rerank 或 query rewrite 继续优化。

## Phase 6 Findings
- 全量测试结果为 `189 passed`，包含阶段 8 新增 Brain/config/workflow/evaluation 测试和既有 API、source、frontend、agent、chat 回归测试。
- 检索评测复跑结果：keyword 15/15 passed，vector 11/15 passed，hybrid 15/15 passed。
- Chat 评测复跑结果：6/6 passed，refused=1，citation_failures=0。
- Agent 评测复跑结果：5/5 passed，refused=1，tool_failures=0，citation_failures=0。
- Source 评测复跑正常输出 source registry metrics：total_sources=125，status_counts=candidate:8;collected:117。
- Brain workflow 评测复跑结果稳定：`keyword_baseline` 6/6，`default_hybrid` 4/6，`vector_only` 2/6。
- 本阶段没有新增前端配置面板，也没有改动前端静态文件；`tests/test_frontend_app.py` 已包含在全量测试内通过。

## Phase 7 Findings
- `README.md` 已同步阶段 8 当前状态、Brain 中控层说明、配置化评测结果和全量测试数量。
- `docs/progress.md` 已新增阶段 8 完成记录，包含完成内容、设计结论、验证结果、遗留问题、下一阶段任务和面试表达。
- `docs/architecture.md` 已补充 Brain 层、配置模型、RAG workflow 数据流、chat/agent 复用关系和配置化评测。
- `docs/data_sources.md` 已说明阶段 8 不新增外部资料来源，`brain_workflow_results.csv` 是评测产物。
- `AGENT.MD` 已把后续起点校准到阶段 8，并明确本项目中控层正式命名为 Brain。
- Obsidian 本地知识库已新增阶段 8 阶段页、阶段 8 Phase 汇报索引、Phase 0-7 小 Phase 汇报和 3 个知识点。
- Obsidian 小 Phase 检查结果：8 篇 Phase 汇报均包含固定 10 项。
- 阶段收尾最终 Git 操作应创建阶段最终功能提交并创建 `phase-8-complete` tag，tag 指向该提交。

## Resources
- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/agent_design.md`
- `docs/evaluation_plan.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `app/services/generation/answer_service.py`
- `app/services/generation/prompt_builder.py`
- `app/services/agent/tools.py`
- `app/services/agent/service.py`
- `app/services/retrieval/keyword_search.py`
- `app/services/retrieval/vector_search.py`
- `app/services/retrieval/hybrid_search.py`
- `scripts/evaluate_chat.py`
- `scripts/evaluate_agent.py`
- `G:\Codex\program\quivr\core\quivr_core\brain\brain.py`
- `G:\Codex\program\quivr\core\quivr_core\rag\entities\config.py`
- `G:\Codex\program\quivr\docs\docs\workflows\examples\basic_rag.md`

## Current Hypotheses
- Brain 层能减少 `CitationAnswerService` 和 Agent 工具之间的重复编排风险。
- 阶段 8 不需要改变 API schema 就能完成核心目标，因为 Brain 是内部中控层。
- 配置化评测能为阶段 9 真实模型接入提供更稳的比较框架。
- 如果先接真实模型而不先做 Brain/config，模型参数和检索参数会继续散落在多个 service 中。

## Phase 0 Findings
- 阶段 8 启动校准已完成。
- 起点全量测试为 163 passed，说明从 `main` 创建阶段 8 分支后，阶段 7 既有功能仍处于健康状态。
- 阶段 8 的第一项开发应先新增 `docs/brain_workflow_design.md` 和文档断言测试，用文档固定 Brain、配置模型和 workflow 边界，再进入代码实现。
- `AGENT.MD` 中原先写“本项目后续可以对应为 KnowledgeBase 或 Corpus，不一定直接命名为 Brain”，但用户已经明确要求中控层也叫 Brain；阶段 8 收尾时需要同步调整该口径。

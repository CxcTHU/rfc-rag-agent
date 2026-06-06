# 项目进度

## 最新状态：2026-06-06

当前阶段：阶段 8，Brain 中控层与 RAG Workflow 配置化已完成。下一步建议在用户确认后进入阶段 9，优先考虑真实模型接入与模型评测，或进入 Agent 权限审计、部署工程化准备。

当前关键证据：

- `task_plan.md` 当前阶段为 `Phase 7 complete`，阶段 8 已进入收尾。
- 当前分支：`codex/phase-8-brain-workflow`。
- 阶段 3 tag：`phase-3-complete -> 7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，未移动。
- 阶段 4 最终提交：`b044459b9b8c2153e9225daa55af5d82cdcdb282`。
- 阶段 4 tag：`phase-4-complete -> b044459b9b8c2153e9225daa55af5d82cdcdb282`。
- 阶段 5 最终功能提交：`8c885e6cc714cc985933438697a7eb2523b26722`。
- 阶段 5 tag：`phase-5-complete -> 8c885e6cc714cc985933438697a7eb2523b26722`。
- 阶段 6 最终功能提交：由 `phase-6-complete` tag 指向的提交标识。
- 阶段 6 tag：`phase-6-complete`。
- 阶段 7 最终功能提交：由 `phase-7-complete` tag 指向的提交标识。
- 阶段 7 tag：`phase-7-complete`。
- 阶段 8 最终功能提交：由 `phase-8-complete` tag 指向的提交标识。
- 阶段 8 tag：`phase-8-complete`。
- 阶段 4 分支和 tag 已推送到 GitHub。
- `sources` 来源登记表已实现。
- `SourceRepository` 和 `SourceRegistryService` 已实现。
- `scripts/sync_sources.py` 已实现。
- sources API 已实现：`GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`。
- `scripts/evaluate_sources.py` 已实现。
- 真实来源同步：输入 283 条来源候选，创建 125 条来源记录，更新 132 次，合并重复 26 次。
- 来源评测：`total_sources=125`、`linked_documents=0`、`merged_duplicates=14`。
- 来源状态分布：`candidate=8`、`collected=117`。
- 全文保存权限分布：`institutional_access=2`、`metadata_only=110`、`open_access=10`、`unknown=3`。
- 可信度分布：`high=125`。
- `POST /chat` 已实现。
- `ChatModelProvider`、RAG prompt/context builder、`CitationAnswerService` 已实现。
- `qa_logs` 问答日志已落地。
- `scripts/evaluate_chat.py` 已实现。
- `data/evaluation/chat_results.csv` 已生成。
- Chat 评测：6/6 通过。
- `POST /search/vector` 已实现。
- `scripts/build_vector_index.py` 已实现。
- `scripts/evaluate_vector_search.py` 已实现。
- `data/evaluation/vector_results.csv` 已生成。
- 向量检索评测：11/15 通过。
- 关键词 baseline：15/15 通过。
- `docs/evaluation_plan.md` 已新增。
- `scripts/analyze_retrieval_errors.py` 已新增。
- `data/evaluation/retrieval_error_cases.csv` 已生成。
- `HybridSearchService` 已实现。
- `POST /search/hybrid` 已实现。
- `scripts/evaluate_hybrid_search.py` 已实现。
- `data/evaluation/hybrid_results.csv` 已生成。
- 混合检索评测：15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- 错误案例状态：4 个 vector 失败均为 `fixed_by_hybrid`。
- Chat 评测：6/6 通过。
- `docs/agent_design.md` 已新增。
- Agent 工具层已实现：`search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- Agent 编排服务已实现，支持规则式意图路由、最大工具调用步数限制、拒答和 `reasoning_summary`。
- `POST /agent/query` 已实现。
- `scripts/evaluate_agent.py` 已实现。
- `data/evaluation/agent_queries.csv` 和 `data/evaluation/agent_results.csv` 已生成。
- Agent 评测：5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `docs/brain_workflow_design.md` 已新增。
- `app/services/brain/` 已实现 Brain 中控层、配置模型、workflow step 记录和回答编排服务。
- `CitationAnswerService` 已迁移为 Brain 兼容门面，`POST /chat` 与 Agent `answer_with_citations` 复用同一条 Brain workflow。
- `scripts/evaluate_brain_workflow.py` 已新增。
- `data/evaluation/brain_workflow_results.csv` 已生成。
- Brain workflow 评测：18 次 config-query run；`keyword_baseline=6/6`，`default_hybrid=4/6`，`vector_only=2/6`。
- 前端工作台已实现：来源管理、资料列表、chunk 查看、关键词/向量/混合检索、聊天问答、Agent 问答、工具调用记录、引用来源侧栏、source sync 和 source reindex 入口。
- 浏览器验证：桌面加载 sources=125、documents=136、chunks=997；移动视口 390x844 无横向溢出。
- 阶段 6 浏览器 smoke check：搜索模式包含 `keyword/vector/hybrid`，聊天检索模式包含 `auto/hybrid/vector/keyword`。
- 阶段 7 浏览器 smoke check：Agent 面板提交“检索 filling capacity 相关资料”后状态为 `answered`，工具调用为 `hybrid_search_knowledge`，返回 5 条混合检索结果。
- 全量测试：189 个测试通过。

下一步：

- 阶段 8 分支 `codex/phase-8-brain-workflow` 已完成核心开发、验证和普通文档收尾。
- 阶段 8 收尾时确认 `phase-8-complete` tag 指向阶段 8 最终功能提交。
- 阶段 8 之后，建议先由用户确认阶段 9 方向：真实模型接入与模型评测、Agent 权限审计、部署工程化或更大规模用户问题评测。
- 不要移动已有阶段 tag：`phase-4-complete`、`phase-5-complete`、`phase-6-complete`、`phase-7-complete`。

## 2026-06-06 阶段 8 完成记录：Brain 中控层与 RAG Workflow 配置化

当前分支：`codex/phase-8-brain-workflow`

当前阶段：阶段 8 已完成。下一步建议由用户确认阶段 9 方向：真实模型接入与模型评测、Agent 权限审计、部署工程化或更大规模用户问题评测。

阶段最终功能提交：由 `phase-8-complete` tag 指向的提交标识。

阶段 tag：`phase-8-complete`。

已完成：

- 使用 Planning with Files 维护阶段 8 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 7 已完成并合并到 `main`，且 `phase-7-complete` tag 指向阶段 7 最终功能提交，未移动已有阶段 tag。
- 新增 `docs/brain_workflow_design.md`，明确 Brain 中控层目标、与 Quivr 的对应关系、workflow 步骤、配置化评测和阶段边界。
- 新增 `app/services/brain/config.py`，实现 `RetrievalConfig`、`WorkflowConfig` 和 `WorkflowStepConfig`。
- 新增 `app/services/brain/workflow.py`，定义 `BrainAnswerResult`、`BrainRetrievalOutcome`、`BrainWorkflowStepRecord`、引用提取和检索结果过滤函数。
- 新增 `app/services/brain/service.py`，实现轻量 `BrainService`，按 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer` 执行 workflow。
- `filter_history` 和 `rewrite_query` 第一版为 no-op，但保留结构化 step 记录。
- `retrieve` 复用现有 keyword/vector/hybrid service，`auto` 模式保持 vector 优先、keyword fallback。
- `optional_rerank` 第一版采用可解释截断；`rerank_top_n=0` 表示暂不重排。
- `generate_answer` 复用 `build_rag_prompt`、`ChatModelProvider`、citation 提取和 `qa_logs`。
- 改造 `CitationAnswerService` 为兼容门面，`POST /chat` 和 Agent `answer_with_citations` 共享 Brain workflow。
- 新增 `scripts/evaluate_brain_workflow.py` 和 `data/evaluation/brain_workflow_results.csv`，比较 `default_hybrid`、`keyword_baseline`、`vector_only` 三种配置。
- 阶段 8 不引入复杂 LangGraph workflow，不联网爬取新资料，不自动执行 source reindex，不新增前端配置面板。

阶段 8 设计结论：

- Brain 是内部中控层，不替代 keyword/vector/hybrid/source/chat/agent 等既有 service，而是统一编排它们。
- `RetrievalConfig` 解决“本次问答怎么检索、召回多少、是否重排、用什么 prompt/model provider”的问题。
- `WorkflowConfig` 解决“RAG 链路按哪些步骤执行”的问题。
- Chat 和 Agent 共用 Brain 后，后续真实模型接入、query rewrite 或 rerank 不需要分别改两套回答逻辑。
- 配置化评测证明本项目可以用同一批问题横向比较不同检索配置，而不是只看单次演示。

验证结果：

- `python -m pytest tests\test_brain_workflow_design.py -q`：2 个测试通过。
- `python -m pytest tests\test_brain_config.py -q`：13 个测试通过。
- `python -m pytest tests\test_brain_workflow.py tests\test_brain_service.py -q`：8 个测试通过。
- `python -m pytest tests\test_answer_service.py tests\test_chat_logging.py tests\test_chat_api.py tests\test_agent_tools.py -q`：24 个测试通过。
- `python -m pytest tests\test_agent_api.py tests\test_agent_service.py -q`：11 个测试通过。
- `python -m pytest tests\test_evaluate_brain_workflow.py -q`：3 个测试通过。
- `python scripts\evaluate_brain_workflow.py`：18 次 config-query run；`keyword_baseline=6/6`，`default_hybrid=4/6`，`vector_only=2/6`。
- `python scripts\evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts\evaluate_vector_search.py`：vector 11/15 通过。
- `python scripts\evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_agent.py`：agent 5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_sources.py`：`total_sources=125`，`merged_duplicates=14`。
- `python -m pytest -q`：189 个测试通过。

遗留问题：

- 当前 `filter_history` 和 `rewrite_query` 是结构化 no-op，后续阶段可接入真实多轮历史压缩和 query rewrite。
- 当前 `optional_rerank` 是可解释截断，不是真实 reranker；后续可以接入 cross-encoder 或 LLM rerank。
- 当前 deterministic embedding 仍不代表真实语义模型效果；阶段 9 如果接真实 embedding，需要复用现有评测集重新对比。
- `CitationAnswerService` 对外不暴露 workflow steps；如前端需要展示 Brain 过程，应另行设计响应字段或内部调试接口。

下一阶段任务：

- 优先建议阶段 9：真实模型接入与模型评测。
- 可选方向：Agent 权限审计与写入工具安全设计。
- 可选方向：部署工程化、日志观测和运行说明完善。
- 可选方向：扩大用户问题评测集，覆盖更多工程案例和中文问题。

面试表达：

```text
阶段 8 我把原先分散在 CitationAnswerService 和 Agent 工具里的 RAG 问答编排抽成了 Brain 中控层，而不是直接上复杂 LangGraph。

BrainService 接收 RetrievalConfig 和 WorkflowConfig，按 filter_history、rewrite_query、retrieve、optional_rerank、generate_answer 五步执行。前两步第一版是 no-op，但保留结构化 step 记录；retrieve 复用 keyword/vector/hybrid；generate_answer 继续复用 prompt builder、模型 provider、citation 提取和 qa_logs。

这样做的价值是：/chat 和 Agent answer_with_citations 共享同一条回答路径，后续接真实模型、query rewrite 或 rerank 时只需要改 Brain workflow，不用维护两套逻辑。验证上，我新增了 Brain 配置化评测脚本，同一批 chat 问题可以比较 default_hybrid、keyword_baseline 和 vector_only，最终全量测试 189 个通过，说明这是一个可配置、可复用、可评测的 RAG 中控层，而不是只靠演示跑通的问答接口。
```

## 2026-06-06 阶段 7 完成记录：Agent 化

当前分支：`codex/phase-7-agent-tools`

当前阶段：阶段 7 已完成。下一步建议由用户确认真实模型接入、权限审计、部署工程化或更细粒度用户评测方向。

阶段最终功能提交：由 `phase-7-complete` tag 指向的提交标识。

阶段 tag：`phase-7-complete`。

已完成：

- 使用 Planning with Files 维护阶段 7 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 6 已完成，且 `phase-6-complete` tag 指向 `fa11702150d79e036159f427f567051e92bfe8c2`，未移动已有阶段 tag。
- 新增 `docs/agent_design.md`，说明 Agent 工具边界、调用流程、权限约束、失败处理和评测方式。
- 新增 `app/services/agent/tools.py`，实现只读工具：`search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- 新增 `app/services/agent/service.py`，实现规则式意图路由、最大工具调用步数限制、拒答和可审计摘要。
- 新增 `app/schemas/agent.py` 和 `app/api/agent.py`，实现 `POST /agent/query`。
- 在 `app/main.py` 注册 Agent API，保持 search、vector、hybrid、chat 和 sources 既有 API 不变。
- 新增 `data/evaluation/agent_queries.csv`、`scripts/evaluate_agent.py` 和 `data/evaluation/agent_results.csv`。
- 前端工作台新增 Agent 面板，展示回答、引用标签和工具调用记录。
- 开发完成后再统一补写 Obsidian Phase 汇报，符合本阶段用户要求。

阶段 7 设计结论：

- 第一版 Agent 采用只读工具优先，不自动执行 source reindex 等写入型动作。
- Agent 工具必须复用现有 service 和 repository，不绕过 sources、documents/chunks、hybrid search、chat citation 和日志链路。
- 第一版编排采用保守规则式意图路由，避免在 RAG 链路稳定前引入复杂 LangGraph workflow。
- `tool_calls` 和 `reasoning_summary` 是审计字段，帮助用户看见 Agent 调用了什么工具、为什么调用、是否成功。
- Agent 评测必须检查工具选择、来源命中、引用有效性和拒答，而不只是 HTTP 200。

验证结果：

- `python -m pytest tests\test_agent_design.py -q`：2 个测试通过。
- `python -m pytest tests\test_agent_tools.py -q`：6 个测试通过。
- `python -m pytest tests\test_agent_service.py -q`：6 个测试通过。
- `python -m pytest tests\test_agent_api.py tests\test_search_api.py tests\test_chat_api.py tests\test_sources_api.py -q`：16 个测试通过。
- `python -m pytest tests\test_evaluate_agent.py -q`：3 个测试通过。
- `python scripts\evaluate_agent.py`：5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts\evaluate_vector_search.py`：vector 11/15 通过。
- `python scripts\evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_sources.py`：`total_sources=125`，`merged_duplicates=14`。
- `python -m pytest tests\test_frontend_app.py -q`：3 个测试通过。
- 浏览器 smoke check：`http://127.0.0.1:8002/` 页面可提交 Agent 问题并展示 `hybrid_search_knowledge` 工具调用记录。
- `python -m pytest -q`：163 个测试通过。

遗留问题：

- 当前 Agent 意图路由是规则式，适合阶段 7 的可控可测目标；后续若引入真实 LLM 规划，需要保留权限、步数和评测约束。
- 当前 Agent 工具只读优先；写入型工具如 reindex 需要显式字段、人工确认或更严格测试后再接入。
- 当前 Agent 评测集规模较小，后续可扩展更多任务类型和用户日志回放。
- 当前仍使用 deterministic provider 作为本地稳定测试实现，真实模型效果需要后续专项评测。

下一阶段任务：

- 用户确认后，可进入真实模型接入与模型评测。
- 或进入 Agent 权限审计与写入工具安全设计。
- 或进入部署工程化、日志观测和使用说明完善。

面试表达：

```text
阶段 7 我把阶段 6 已经稳定的 RAG 能力包装成受控 Agent 工具调用链路，而不是直接上复杂 workflow。

我先用 docs/agent_design.md 固定工具边界和权限约束，然后新增 AgentToolbox，把关键词检索、混合检索、引用式问答和来源查询封装为只读工具。AgentService 做保守规则式意图路由：搜索类走 hybrid_search_knowledge，问答类走 answer_with_citations，来源类走 sources 工具。POST /agent/query 返回 answer、tool_calls、sources、citations、refused 和 reasoning_summary，前端也能展示工具调用记录。

这样设计的核心是可控和可审计：Agent 不能绕过 source registry、documents/chunks、hybrid search、引用和拒答机制。验证上我新增 Agent 评测脚本，结果 5/5 通过，同时复跑 keyword 15/15、vector 11/15、hybrid 15/15、chat 6/6 和全量 163 个测试。这个阶段证明项目不是一个随意调用工具的 demo，而是一个可回归、只读优先、来源可追踪的 RAG Agent。
```

## 2026-06-05 阶段 6 完成记录：检索优化与评测

当前分支：`codex/phase-6-evaluation`

当前阶段：阶段 6 已完成。下一步准备进入阶段 7：Agent 化。

阶段最终功能提交：由 `phase-6-complete` tag 指向的提交标识。

阶段 tag：`phase-6-complete`。

已完成：

- 使用 Planning with Files 维护阶段 6 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 5 已完成并合并，且 `phase-5-complete` tag 指向 `8c885e6cc714cc985933438697a7eb2523b26722`，未移动已有阶段 tag。
- 新增 `docs/evaluation_plan.md`，定义 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage、Refusal Quality。
- 复跑 keyword、vector、chat baseline。
- 新增 `scripts/analyze_retrieval_errors.py` 和 `data/evaluation/retrieval_error_cases.csv`，记录失败问题、失败原因、期望依据、改进建议和优化后状态。
- 新增 `HybridSearchService`，合并关键词和向量召回，按 chunk 去重，对分数归一化并重排。
- 新增 `POST /search/hybrid`，保留 `POST /search` 和 `POST /search/vector` 既有行为。
- 扩展 `POST /chat` 的显式 `retrieval_mode="hybrid"`，但不改变 `auto` 的既有行为。
- 新增 `scripts/evaluate_hybrid_search.py` 和 `data/evaluation/hybrid_results.csv`，对比 keyword、vector、hybrid 三条链路。
- 前端工作台新增 hybrid 检索模式选择，保持最小改动。
- 开发完成后再统一补写 Obsidian Phase 汇报，符合本阶段用户要求。

阶段 6 设计结论：

- 先建立评测计划和 baseline，再做优化，避免凭感觉调参。
- 保留 keyword 和 vector baseline，hybrid 作为独立入口，便于优化前后对比。
- deterministic embedding 仍适合本地稳定测试；真实语义效果后续可接真实 embedding provider 继续评测。
- 混合检索优先使用保守、可解释的加权重排，不引入复杂 Agent workflow。
- 前端只暴露 hybrid 选项，不做界面重构。

验证结果：

- `python scripts/evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts/evaluate_vector_search.py`：vector 11/15 通过，4 个 `keyword_only_pass`。
- `python scripts/evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts/evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts/analyze_retrieval_errors.py`：4 个 vector 失败均为 `fixed_by_hybrid`。
- `python -m pytest tests\test_frontend_app.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_search_api.py -q`：14 个测试通过。
- 浏览器 smoke check：`http://127.0.0.1:8001/` 页面可见 hybrid 搜索和 hybrid 聊天检索模式。
- `python -m pytest -q`：141 个测试通过。

遗留问题：

- 当前 hybrid 权重是保守静态规则，尚未做真实用户日志驱动调参。
- 当前 deterministic embedding 不代表真实语义模型效果；后续接真实 embedding provider 后应继续复用同一评测集。
- Chat `auto` 模式暂未默认切换到 hybrid，以避免改变既有 baseline 含义；后续可在阶段 7 或真实模型评测后再决定。
- 阶段 6 不做 Agent 工具调用，Agent 化留到阶段 7。

下一阶段任务：

- 阶段 7 进入 Agent 化。
- 将稳定的 search、hybrid search、chat、sources/reindex 能力包装为受控工具。
- 设计工具调用权限、最大步数、日志和失败回退。
- 优先做只读工具，例如知识库搜索、资料总结、来源对比、术语抽取。

面试表达：

```text
阶段 6 我重点解决 RAG 质量怎么证明的问题。

我先写评测计划，把 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage 和 Refusal Quality 映射到当前脚本和 CSV 结果。然后复跑 baseline：关键词检索 15/15，向量检索 11/15，chat 6/6，并把 4 个向量失败案例沉淀成错误案例表。

优化时我没有直接上复杂 Agent 或外部模型，而是实现可解释的 hybrid search。它同时召回关键词和向量结果，按 chunk 去重，对两路分数归一化，再通过权重和双路命中奖励重排。最终 hybrid search 达到 15/15，救回 4 个 vector-only 失败，且没有 keyword baseline 退化。这个阶段体现的是工程评测闭环：有 baseline、有错误分析、有优化策略、有指标对比、有回归测试。
```

## 2026-06-05 阶段 5 完成记录：前端界面

当前分支：`codex/phase-5-frontend`

当前阶段：阶段 5 已完成。下一步准备进入阶段 6：检索优化与评测。

阶段最终功能提交：`8c885e6cc714cc985933438697a7eb2523b26722`

阶段 tag：`phase-5-complete`，已指向阶段最终功能提交。

已完成：

- 使用 Planning with Files 维护阶段 5 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 4 已完成，且 `phase-4-complete` tag 指向 `b044459b9b8c2153e9225daa55af5d82cdcdb282`，未移动已有阶段 tag。
- 新增 `app/api/frontend.py`，提供 `GET /` 前端入口和 `/favicon.ico` 空响应。
- 在 `app/main.py` 中注册 frontend router，并挂载 `/static` 静态资源。
- 新增 `app/frontend/index.html`、`app/frontend/static/styles.css`、`app/frontend/static/app.js`。
- 前端工作台展示 sources、documents、状态、可信度、全文权限、年份、分类、URL/DOI 和 chunk 数量。
- 支持来源关键词、状态和全文权限筛选。
- 支持查看 document chunks。
- 支持关键词检索和向量检索。
- 支持调用 `POST /chat` 提问，展示 answer、citations、sources、refused、retrieval_mode 和模型信息。
- 支持引用来源侧栏，展示 document title、chunk、score、source_path 和片段内容。
- 支持 source sync 操作入口和单条 source reindex 操作入口。
- 新增 `tests/test_frontend_app.py`，验证首页、静态资源、favicon 和关键前端入口。

阶段 5 设计结论：

- 第一版前端采用 FastAPI 静态文件 + 原生 HTML/CSS/JS，不引入 Node/React 构建链。
- 前端是薄展示层，只调用现有 API，不重写来源治理、检索或问答业务逻辑。
- 首页直接是 RAG 工作台，不做营销 landing page。
- sources 和 documents 并列展示，帮助用户理解“来源治理”和“已入库内容”不是同一层。
- reindex 操作会提示必要时刷新向量索引，避免用户误以为 reindex 自动提升语义检索质量。

验证结果：

- `python -m pytest tests\test_frontend_app.py -q`：3 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_sources_api.py tests\test_documents_api.py -q`：9 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_chat_api.py tests\test_answer_service.py -q`：14 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_search_api.py tests\test_vector_search_api.py tests\test_documents_api.py tests\test_sources_api.py -q`：13 个测试通过。
- 浏览器验证桌面页面：sources=125、documents=136、chunks=997。
- 浏览器验证来源筛选：`temperature` -> `7 / 125`。
- 浏览器验证 chunk 查看：document 1 显示 1 个 chunk。
- 浏览器验证关键词检索：`filling capacity` 返回 5 条结果。
- 浏览器验证聊天：问题 `What affects filling capacity in rock-filled concrete?` 返回回答和 5 条引用。
- 浏览器验证 reindex 错误处理：不存在 source 返回可理解错误。
- 浏览器验证移动视口：390x844 下无横向溢出。
- `python -m pytest -q`：126 个测试通过。

遗留问题：

- 阶段 5 使用原生前端，适合当前最小工作台；如果后续交互复杂度提高，可迁移到 React/Next.js。
- 浏览器验证没有执行真实 source reindex 成功路径，避免验证时改动资料库；已验证入口和错误处理。
- 当前没有上传界面；阶段 5 优先完成资料查看、来源管理、检索和问答。
- 当前没有后台任务队列，source sync/reindex 仍是同步请求。

下一阶段任务：

- 阶段 6 进入检索优化与评测。
- 建议建立 `docs/evaluation_plan.md`。
- 继续复用关键词、向量、chat 评测集，补充错误案例分析。
- 优先考虑混合检索、rerank、真实 embedding 或 query expansion。

面试表达：

```text
阶段 5 我补齐了 RAG 系统的前端工作台。

我没有只做聊天框，而是把 sources、documents、chunks、search 和 chat 都串到一个界面里。用户可以先看资料来源是否可信、是否允许保存全文、是否已经入库，再查看资料片段、执行检索，最后通过聊天界面看到回答和引用来源侧栏。

技术上我采用 FastAPI 静态文件加原生 HTML/CSS/JS，避免在当前 Python 项目里过早引入复杂构建链。前端只负责展示、筛选和调用 API，来源治理、检索和问答仍放在后端 service。阶段 5 通过了浏览器验证和 126 个自动化测试，为后续检索优化和 Agent 工具调用提供了可操作入口。
```

## 2026-06-05 阶段 4 完成记录：数据采集与来源管理

当前分支：`codex/phase-4-source-management`

当前阶段：阶段 4 已完成。下一步准备进入阶段 5：前端界面。

阶段最终提交：`b044459b9b8c2153e9225daa55af5d82cdcdb282`

阶段 tag：`phase-4-complete`，已指向阶段最终提交并推送到 GitHub。

已完成：

- 使用 Planning with Files 维护阶段 4 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 3 已完成，且 `phase-3-complete` tag 指向 `7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，未移动已有阶段 tag。
- 新增 `Source` SQLAlchemy 模型，对应 `sources` 表。
- `sources` 表保存来源标识、题名、作者、年份、分类、发现渠道、DOI、URL、PDF URL、摘要、关键词、语言、引用数、来源类型、可信度、访问权限、全文保存权限、状态、本地路径、备注和可选 `document_id`。
- 新增 `normalized_doi`、`normalized_url`、`normalized_title`，支持 DOI、URL、标题三层去重。
- 新增 `SourceCreate` 和 `SourceRepository`，支持来源保存、更新、查询、列表、计数和重复键查询。
- 新增 `SourceRegistryService`，负责来源登记、归一化、去重、重复来源合并、可信度评级、全文权限判断和状态判断。
- 新增来源同步能力，支持读取 `data/source_candidates.csv`、`data/fulltext_manifest.csv`、`data/metadata/rfc_papers_metadata.csv` 和 `data/imports/metadata_corpus/*.md`。
- 新增 `scripts/sync_sources.py`，可幂等同步现有 CSV / manifest / metadata corpus 到 `sources` 表。
- 新增 source reindex 入口：已有本地文件的来源可重新导入原文；metadata-only 来源可重新生成题录卡片后导入 `documents/chunks`。
- 新增 `app/schemas/source.py` 和 `app/api/sources.py`。
- 新增 API：`GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`。
- 新增 `scripts/evaluate_sources.py`，输出来源总数、已关联 document 数、重复合并线索、权限分布、状态分布和可信度分布。
- 新增测试：`tests/test_source_repository.py`、`tests/test_source_registry_service.py`、`tests/test_sync_sources.py`、`tests/test_sources_api.py`、`tests/test_evaluate_sources.py`。

阶段 4 设计结论：

- `sources` 表不替代 `documents/chunks`。`sources` 管来源治理，`documents/chunks` 管已导入并可检索的内容。
- DOI 是最强去重键，URL 次之，标题归一化兜底。
- 可信度 `trust_level` 和全文保存权限 `fulltext_permission` 必须分开。一个来源可以高可信但只能保存题录，也可以开放获取但仍需记录许可边界。
- `status` 先使用固定字符串表达最小生命周期：`candidate`、`collected`、`imported`、`duplicate`、`rejected`。
- 阶段 4 不做复杂爬虫、不做 Agent 工具调用、不做前端。先把来源登记、去重、权限、状态、导入和 reindex 链路稳定下来。

验证结果：

- `python -m pytest tests\test_source_repository.py tests\test_source_registry_service.py tests\test_sync_sources.py tests\test_sources_api.py -q`：15 个测试通过。
- `python -m pytest tests\test_evaluate_sources.py -q`：2 个测试通过。
- `python scripts\sync_sources.py`：`total=283`、`created=125`、`updated=132`、`duplicates=26`。
- `python scripts\evaluate_sources.py --out data\evaluation\source_registry_metrics.csv`：`total_sources=125`、`linked_documents=0`、`merged_duplicates=14`。
- `python -m pytest -q`：123 个测试通过。
- `python scripts\evaluate_keyword_search.py`：15/15 通过。
- `python scripts\evaluate_vector_search.py --skip-index-build`：11/15 通过。
- `python scripts\evaluate_chat.py`：6/6 通过，`refused=1`，`citation_failures=0`。

遗留问题：

- 真实来源评测中 `linked_documents=0`，说明 source registry 已登记来源，但尚未对所有来源批量执行 reindex。阶段 4 已提供入口，后续可由前端或运营脚本触发。
- 向量检索仍保持阶段 3 的 11/15 deterministic embedding 基线。本阶段没有做召回质量优化。
- SQLite 阶段没有引入数据库迁移工具，后续迁移 PostgreSQL 或多人协作时应补 Alembic。

下一阶段任务：

- 阶段 5 进入前端界面。
- 建议先做资料管理界面，展示 `sources`、`documents`、`chunks` 的关系。
- 再做聊天界面、引用来源侧栏、reindex 按钮和来源筛选。
- 暂时继续避免复杂 Agent workflow，先让非技术用户能看懂和操作 RAG 链路。

面试表达：

```text
阶段 4 我补齐了 RAG 项目的来源治理层。

阶段 1 到阶段 3 已经能导入资料、检索 chunks、生成带引用的回答，但资料来源仍散落在 CSV、PDF manifest、题录卡片和 documents 表里。阶段 4 我新增 sources 表作为 source registry，把来源候选、题录、PDF 清单和 metadata cards 统一登记，并用 SourceRegistryService 做 DOI、URL、标题三层去重。

我把可信度 trust_level、全文保存权限 fulltext_permission 和来源状态 status 分成独立字段，避免把“来源可靠”和“能否保存全文”混为一谈。来源可以先处于 candidate 或 collected 状态，等需要进入问答库时再通过 reindex 导入 documents/chunks。

同时我提供了 sync_sources.py、sources API 和 evaluate_sources.py。这样阶段 4 不只是加了一张表，而是形成了可同步、可查询、可重新索引、可评测的来源治理链路，为阶段 5 前端和后续 Agent 工具调用打基础。
```

## 2026-06-05 阶段 3 完成记录：引用式问答

当前分支：`codex/phase-3-cited-chat`

当前阶段：阶段 3 已完成。下一步准备进入阶段 4：数据采集与来源管理。

已完成：

- 使用 `planning-with-files` 维护阶段 3 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage3_learning_notes.md`，沉淀阶段 3 新词解释、设计原因、测试结果和面试表达。
- 新增 `app/services/generation/chat_model.py`，定义 `ChatModelProvider`、`ChatMessage`、`ChatModelResult`，实现 deterministic provider 和 OpenAI-compatible provider。
- 新增 `app/services/generation/prompt_builder.py`，把检索结果组织成带 `[1]`、`[2]` 编号的 RAG 上下文。
- 新增 `app/services/generation/answer_service.py`，实现 `CitationAnswerService`，支持检索、prompt 构造、模型调用、引用提取、拒答和日志写入。
- 新增 `app/schemas/chat.py` 和 `app/api/chat.py`，实现 `POST /chat`。
- 新增 `qa_logs` 问答日志表、`QuestionAnswerLog` 模型和 `QuestionAnswerLogRepository`。
- 新增 `scripts/evaluate_chat.py`、`data/evaluation/chat_queries.csv` 和 `data/evaluation/chat_results.csv`。
- 新增测试：`tests/test_chat_model_provider.py`、`tests/test_prompt_builder.py`、`tests/test_answer_service.py`、`tests/test_chat_api.py`、`tests/test_chat_logging.py`、`tests/test_evaluate_chat.py`。

阶段 3 设计结论：

- 本阶段参考 Quivr 的 `LLMEndpoint`、RAG prompt、source index 和 response metadata 思路，但不引入 LangGraph。
- `ChatModelProvider` 对齐模型调用抽象，避免业务服务绑定具体国产模型或 OpenAI-compatible API。
- prompt builder 负责给 sources 编号，AnswerService 负责过滤 citations，不能完全相信模型自己输出的来源编号。
- 拒答机制放在 service 层，不只靠 prompt。
- `/chat` 是薄 API，RAG 业务逻辑集中在 `CitationAnswerService`。
- `qa_logs` 是阶段 3 最小可观测性，支持后续排查检索、引用、拒答和模型配置问题。
- Chat 评测默认使用 deterministic chat provider，保证没有真实模型 key 也能稳定回归。

验证结果：

- `python scripts\evaluate_chat.py`：6/6 通过。
- `python scripts\evaluate_keyword_search.py`：15/15 通过。
- `python scripts\evaluate_vector_search.py --skip-index-build`：11/15 通过。
- `python -m pytest -q`：106 个测试通过。

已处理问题：

- `truncate_text()` 初版没有把 `... [truncated]` 后缀长度纳入计算，导致截断后仍超过 `max_chars`；已修复。
- deterministic provider 初版回显完整 RAG prompt，导致上下文里的 `[2]` 被误识别为答案引用；已新增 `extract_question()`，只提取问题正文。
- 首次真实 chat 评测为 4/6；质量控制问题期望词过窄，无依据英文问题被常见词误召回。已调整评测集，最终 6/6 通过。

遗留问题：

- 当前 deterministic chat provider 只用于稳定开发和评测，不代表真实国产大模型回答质量。
- 当前向量检索仍为 11/15，真实语义检索效果需要后续接入真实 embedding、混合检索或 rerank。
- 当前 `qa_logs` 使用 Text 存 JSON 字符串保存 id 列表，后续迁移 PostgreSQL 时可升级为 JSON 字段。
- 当前没有多轮聊天历史，阶段 3 只做单轮引用式问答。
- 当前没有 Agent 工具调用，符合阶段 3 目标；Agent 化留到后续阶段。

面试表达：

```text
阶段 3 我完成了引用式问答的最小稳定链路。

我先抽象 ChatModelProvider，把聊天模型供应商和业务逻辑解耦；再用 prompt_builder 把检索到的 chunks 组织成带来源编号的上下文；CitationAnswerService 负责检索、prompt 构造、模型调用、引用提取和拒答判断；最后通过 POST /chat 返回 answer、citations、sources、refused、retrieval_mode 和 model 信息。

为了保证可追溯，我让 citations 只能引用本次 sources 中存在的编号，并新增 qa_logs 记录问题、答案、召回 chunk、引用、模型和拒答状态。为了避免只靠演示判断效果，我新增了 chat 评测集和 evaluate_chat.py，当前 chat 评测 6/6 通过，全量测试 106 个通过。

这个阶段没有引入复杂 Agent workflow，而是先保证 RAG 问答链路稳定、可测试、可引用、可拒答。
```

## 2026-06-04

当时阶段：阶段 1，本地资料导入与关键词检索已完成，并已合并到 `main`。下一步准备进入阶段 2：Embedding 与向量检索。

已完成：

- 明确项目主题：面向水利工程堆石混凝土技术的 RAG 问答 Agent。
- 编写项目指南 `AGENT.MD`。
- 创建初始项目目录。
- 准备连接 GitHub 仓库。
- 创建阶段 0 开发分支 `codex/phase-0-health-api`。
- 建立 FastAPI 应用入口 `app/main.py`。
- 实现健康检查接口 `GET /health`。
- 建立基础配置读取 `app/core/config.py`。
- 增加健康检查响应模型 `app/schemas/health.py`。
- 增加最小接口测试 `tests/test_health.py`。
- 增加项目依赖与测试配置 `pyproject.toml`。
- 在 `AGENT.MD` 中补充 Obsidian 知识库维护规则。
- 创建 Obsidian 知识库 `obsidian-vault/`。
- 为阶段 0 沉淀知识点笔记，并用双链连接阶段页与分类页。
- 更新 `AGENT.MD` 的协作与教学规则，要求新名词首次出现时结合本项目解释，并按“是什么 -> 在本项目哪里出现 -> 有什么作用 -> 面试怎么说”的顺序沉淀。
- 在 `AGENT.MD` 中补充本地 Quivr 项目作为 RAG 工程拆分参考，明确本项目学习其模块边界、数据流、配置方式和测试思路，但不直接复制代码。
- 增加 Obsidian 知识点 `obsidian-vault/知识点/新词解释机制.md`，并链接到阶段 0 与项目方法论分类。
- 重新阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、主要代码文件和测试文件，确认当前仍处于阶段 0 完成、准备进入阶段 1 的状态。

验证结果：

- `python -m pytest`：1 个测试通过。
- 本地服务验证：`GET http://127.0.0.1:8000/health` 返回 `{"status":"ok","service":"RFC-RAG-Agent","environment":"development"}`。
- 重新运行 `python -m pytest`：1 个测试通过。
- Git 当前分支为 `codex/phase-0-health-api`；更新前工作区干净，本次仅修改 `docs/progress.md`。
- 已确认本地参考项目 `G:\Codex\program\quivr` 存在，后续涉及架构、导入、检索、问答或评测设计时可按 `AGENT.MD` 规则参考其工程拆分思路。

阶段 0 知识点：

- FastAPI 用来声明 API 应用和路由。
- Pydantic schema 用来约束接口返回结构，避免返回格式随意变化。
- 配置读取集中放在 `app/core/config.py`，避免把环境变量散落在业务代码里。
- 测试使用 `TestClient` 模拟 HTTP 请求，能在不启动真实端口的情况下验证接口行为。
- 健康检查接口是服务可观测性的起点，后续可扩展为数据库、向量库和模型服务状态检查。

Obsidian 知识库已记录：

- `obsidian-vault/阶段/阶段 0 - FastAPI 工程底座.md`
- `obsidian-vault/知识点/FastAPI 应用入口与工厂函数.md`
- `obsidian-vault/知识点/API 路由分层.md`
- `obsidian-vault/知识点/健康检查接口.md`
- `obsidian-vault/知识点/Pydantic 响应模型.md`
- `obsidian-vault/知识点/Pydantic Settings 配置读取.md`
- `obsidian-vault/知识点/pytest 与 TestClient.md`
- `obsidian-vault/知识点/pyproject.toml 项目依赖管理.md`
- `obsidian-vault/知识点/uvicorn 与 ASGI 服务.md`
- `obsidian-vault/知识点/阶段分支开发.md`
- `obsidian-vault/知识点/Obsidian 双链知识库.md`
- `obsidian-vault/知识点/新词解释机制.md`

当前状态判断：

- 阶段 0 的 FastAPI 工程底座已经完成并通过测试。
- 最新项目规则强调“边做边讲清楚”，后续新增 REST、ORM、chunk、embedding、rerank 等概念时，需要及时解释并判断是否沉淀到 Obsidian。
- 阶段 1 应优先打通本地资料链路：Markdown/TXT 导入、文本清洗、chunk 切分、SQLite 保存和关键词检索。
- 阶段 1 设计时可以参考 Quivr 的 storage、processor、splitter、配置对象和测试组织方式，但本项目要保持简化，聚焦堆石混凝土资料与引用溯源。

遗留问题：

- `AGENT.MD` 的“当前推荐的第一步”曾停留在阶段 0 初始化任务；已在 2026-06-05 阶段 1 收尾时校准为阶段 2 启动建议。
- `AGENT.MD` 中检索策略部分曾有一处阶段表述需要校准；已在 2026-06-05 修正为阶段 1 先做关键词检索、阶段 2 再做向量检索。

依赖说明：

- `pyproject.toml` 中的 `httpx2>=2.3.0` 不是拼写错误；在当前安装到的 Starlette 新版分支里，它是 `TestClient` 优先使用的测试依赖，当前保留该写法。

面试表达：

```text
阶段 0 我没有直接接入大模型，而是先搭建 FastAPI 工程底座。
我把应用入口、路由、配置和响应模型分开，保证后续 documents、search、chat 等模块可以按同样结构扩展。
我实现了 /health 接口，并用自动化测试验证 HTTP 状态码和 JSON 返回结构。
这样可以证明服务可启动、接口可访问，也为后续 CI、部署和监控打基础。
```

下一步：

- 根据 `docs/architecture.md` 中的阶段 1 总体框架，先实现 SQLite 数据库层。
- 设计并落地 `documents` 与 `chunks` 两张表。
- 实现 Markdown/TXT 导入、文本清洗和 chunk 切分。
- 实现 `POST /documents/import`、`GET /documents` 和 `POST /search`。
- 完成关键词检索并补充最小自动化测试。

## 2026-06-04 阶段 1 启动记录

当前分支：`codex/phase-1-document-ingestion`

已完成：

- 正式进入阶段 1：本地资料导入与关键词检索。
- 按照 `AGENT.MD` 的要求重新确认阶段 1 目标：先打通本地资料链路，不接大模型，不接向量库。
- 参考本地 Quivr 项目的 `storage / processor / splitter` 模块边界，确定本项目阶段 1 只借鉴其工程拆分思路，不复制代码。
- 在 `docs/architecture.md` 中新增“阶段 1 总体框架”，明确数据流、目录规划、数据库表、API 草案、关键词检索策略和测试顺序。
- 增加 `SQLAlchemy` 依赖，用于 SQLite 数据库建模和读写。
- 新增 `app/db/session.py`，集中创建数据库连接、数据库会话和建表入口。
- 新增 `app/db/models.py`，定义 `documents` 和 `chunks` 两张表。
- 新增 `tests/test_db_models.py`，验证数据库表能创建，并能保存一篇资料及其 chunk。
- 新增 `app/services/ingestion/parser.py`，支持读取 Markdown/TXT，并从 Markdown 一级或多级标题中推断资料标题。
- 新增 `app/services/ingestion/cleaner.py`，清理 BOM、空字符、换行差异、多余空白和连续空行。
- 新增 `app/services/ingestion/splitter.py`，把长文本切成带 `chunk_index`、`char_count`、`heading_path`、`start_char`、`end_char` 的 chunk。
- 新增 `tests/test_ingestion_parser.py`、`tests/test_ingestion_cleaner.py`、`tests/test_ingestion_splitter.py`，分别验证解析、清洗和切分逻辑。
- 新增 `app/db/repositories.py`，封装 `documents` 和 `chunks` 的保存、查询和 chunk 计数逻辑。
- 新增 `app/services/ingestion/loader.py`，负责计算文件 hash，并把原始文件保存到 raw 目录。
- 新增 `app/services/ingestion/service.py`，把 parser、cleaner、splitter、loader 和 repository 串成完整导入链路。
- 新增 `tests/test_repositories.py`，验证 repository 可以保存和查询资料。
- 新增 `tests/test_ingestion_service.py`，验证 Markdown 文件能完成导入、切分、保存，重复文件不会重复入库，空文件会被拒绝。
- 新增 `python-multipart` 依赖，用于 FastAPI 接收上传文件。
- 新增配置项 `RAW_DATA_DIR`，用于控制原始资料保存目录。
- 新增 `app/schemas/document.py`，定义文档导入和文档列表接口的响应结构。
- 新增 `app/api/documents.py`，实现 `POST /documents/import` 和 `GET /documents`。
- 更新 `app/main.py`，注册 documents 路由，并在应用启动时自动创建数据库表。
- 新增 `tests/test_documents_api.py`，验证上传 Markdown 可完成导入，`GET /documents` 可返回文档列表，不支持的文件类型会返回 400。
- 在 `pyproject.toml` 中显式声明只打包 `app` 包，避免本地运行目录 `data/` 被 setuptools 误识别为顶层包。
- 新增 `app/services/retrieval/keyword_search.py`，实现阶段 1 的关键词检索服务。
- 新增 `app/schemas/search.py`，定义搜索请求和搜索结果响应结构。
- 新增 `app/api/search.py`，实现 `POST /search`。
- 更新 `app/main.py`，注册 search 路由。
- 新增 `tests/test_keyword_search.py`，验证关键词检索能返回命中的 chunk，并过滤无关 chunk。
- 新增 `tests/test_search_api.py`，验证完整 API 流程：上传 Markdown 后，可以通过 `POST /search` 搜到相关片段。
- 搜索结果已包含 `document_title`、`source_path`、`file_name`、`chunk_index`、`content` 和 `score`，满足阶段 1 对“来源、标题和片段”的基本要求。
- 新增 `GET /documents/{document_id}/chunks`，支持按资料编号查看该资料切出的全部 chunk。
- 新增 `tests/test_documents_api.py` 对 chunk 查看接口的正常返回和 404 场景测试。

阶段 1 设计结论：

- 本阶段只支持 Markdown/TXT。
- 原始文件保存到 `data/raw/`。
- 解析、清洗、切分逻辑放到 `app/services/ingestion/`。
- 数据库存储放到 `app/db/`，先落地 `documents` 和 `chunks`。
- 检索放到 `app/services/retrieval/keyword_search.py`，先做可解释的关键词检索。
- API 层新增 `documents.py` 和 `search.py`，保持与阶段 0 的路由分层一致。

下一步：

- 用 5 到 10 篇真实 Markdown/TXT 堆石混凝土资料做本地试导入。
- 手动验证关键词如“堆石混凝土”“自密实混凝土”“施工质量”能返回合理片段。
- 根据真实资料效果微调 chunk_size、chunk_overlap 和关键词评分规则。

验证结果：

- `python -m pytest`：21 个测试通过。

## 2026-06-04 阶段 1 真实资料试导入记录

已完成：

- 使用公开学术页面、高校页面、期刊页面和开放获取论文，整理 10 条堆石混凝土资料卡到 `data/imports/rfc_seed/`。
- 用户补充确认 CNKI 摘要页为《堆石混凝土及堆石混凝土大坝》的主来源入口，已更新 `rfc_seed_001` 资料卡和 `docs/data_sources.md`。
- 通过本地导入链路写入 SQLite，当前资料库包含 10 篇 documents 和 17 个 chunks。
- 搜索校准覆盖关键词：金峰、堆石混凝土、自密实混凝土、施工质量、填充密实性、水化热、低碳筑坝、rock-filled concrete。
- 校准结果显示：开篇论文、施工方法专利、填充能力研究、绝热温升研究和 2023 年综述能被相关关键词召回。

设计说明：

- 本批资料只保存题录、公开摘要转述、检索关键词和来源链接，不保存受版权限制全文。
- CNKI 的 `kcms2/article/abstract?v=...` 链接可能包含临时参数，因此同时保留 ResearchGate、期刊页面或高校页面作为辅助线索。
- 现阶段资料卡中的题名、作者和来源也会进入 chunk 正文，便于关键词检索；后续阶段可以把这些信息拆成 metadata 字段，提高正文检索的纯净度。

验证结果：

- 本地数据库检查：10 篇 documents，17 个 chunks。
- 《堆石混凝土及堆石混凝土大坝》的 `source_path` 已更新为用户提供的 CNKI 摘要页。

## 2026-06-04 阶段 1 chunk 检查接口记录

已完成：

- 在 `app/db/repositories.py` 中增加按 `document_id` 查询文档和 chunk 的方法。
- 在 `app/schemas/document.py` 中增加 chunk 查看接口的响应结构。
- 在 `app/api/documents.py` 中实现 `GET /documents/{document_id}/chunks`。
- 在 `tests/test_documents_api.py` 中增加接口测试，覆盖正常查看 chunk 和文档不存在返回 404。

设计说明：

- 该接口用于提升阶段 1 的可观测性，方便直接检查真实资料被切分后的内容是否合理。
- API 层仍通过 repository 读取数据库，保持 API、schema、database 的分层清晰。

验证结果：

- `python -m pytest tests\test_documents_api.py`：4 个测试通过。

## 2026-06-04 阶段 1 splitter 真实资料微调记录

已完成：

- 检查 10 条真实堆石混凝土资料卡生成的 chunk，发现旧 splitter 会把 `source_id`、URL、`copyright_note` 等资料卡元信息切进正文。
- 发现旧 overlap 可能让新 chunk 从 URL、英文单词或元信息字段中间开始，影响 chunk 可读性和检索结果展示。
- 发现旧 `heading_path` 按 chunk 结束位置附近的标题计算，容易显示成 chunk 内最后一个标题，而不是 chunk 开始处所属标题。
- 更新 `app/services/ingestion/splitter.py`：
  - 自动跳过 Markdown 资料卡开头的元信息块。
  - 新 chunk 起点优先贴近段落、换行或句号等自然边界。
  - `heading_path` 改为按 chunk 开始位置计算。
- 更新 `tests/test_ingestion_splitter.py`，新增元信息跳过和自然边界起点测试。
- 使用新 splitter 重新切分 `data/imports/rfc_seed/` 下的 10 条资料卡，并刷新本地 SQLite 中的 chunks。

设计说明：

- 当前导入的是摘要型资料卡，每条资料卡正文大多在 500 到 800 字之间，因此重切后每篇资料保留 1 个 chunk 更合理。
- 这次不是减少知识量，而是去掉检索噪声，避免把来源登记字段当作知识正文。
- 后续导入长论文、长报告或规范时，splitter 仍会按 `chunk_size` 和自然边界切成多个 chunk。

校准结果：

- 数据库当前为 10 篇 documents，10 个 chunks。
- 搜索“堆石混凝土”时，《堆石混凝土及堆石混凝土大坝》排在前列。
- 搜索“水化热”时，《堆石混凝土绝热温升性能初步研究》排在前列。
- 搜索“填充密实性”时，能召回自密实混凝土充填试验和流动模拟相关资料。

验证结果：

- `python -m pytest tests\test_ingestion_splitter.py -q`：6 个测试通过。
- `python -m pytest`：25 个测试通过。

## 2026-06-04 阶段 1 论文原文导入记录

已完成：

- 新增 `pypdf` 依赖，用于抽取 PDF 文字层。
- 更新 `app/services/ingestion/parser.py`，支持导入 `.pdf` 文件。
- PDF 解析会按页加入 `## Page N` 标记，方便后续检查 chunk 来源页。
- 更新 `tests/test_ingestion_parser.py`，新增 PDF 文字抽取测试。
- 更新 `tests/test_documents_api.py`，将不支持格式测试从 PDF 改为 DOCX。
- 更新 `app/services/ingestion/service.py`，支持传入 `source_type`，用于标记 `open_access_pdf`。
- 更新 `tests/test_ingestion_service.py`，验证自定义来源类型可以写入数据库。
- 新增 `data/fulltext_manifest.csv`，记录 PDF 原文的标题、作者、年份、分类、访问权限、许可备注、URL、PDF URL 和本地文件名。
- 新增 `docs/source_catalog.md`，建立来源分类目录和 CNKI / 机构访问优先下载清单。
- 更新 `.gitignore`，忽略 `data/fulltext/`，避免将论文全文提交到 GitHub。

本次已下载开放全文 PDF：

- `Research on Rock-Filled Concrete Dam`
- `Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete`
- `Experimental Research on the Properties of Rock-Filled Concrete`
- `Filling Capacity Evaluation of Self-Compacting Concrete in Rock-Filled Concrete`
- `A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology`
- `A Mesoscale Comparative Analysis of the Elastic Modulus in Rock-Filled Concrete for Structural Applications`
- `A Comprehensive Literature Review on the Elastic Modulus of Rock-filled Concrete`
- `Seismic Behavior of Rock-Filled Concrete Dam Compared with Conventional Vibrating Concrete Dam Using Finite Element Method`
- `3D mesoscopic numerical investigation on the uniaxial compressive behavior of rock-filled concrete with different ITZ and aggregate properties`
- `Full-Scale micromechanical simulation of rock-filled concretes using Peridynamics`

导入结果：

- 当前数据库总计：20 篇 documents，800 个 chunks。
- 资料卡：10 篇 documents，10 个 chunks。
- 开放全文 PDF：10 篇 documents，790 个 chunks。

搜索校准：

- `rock-filled concrete dam review` 能召回 2023 年 Engineering 综述全文。
- `filling capacity` 能召回填充能力相关资料卡和 2020 年 Materials 全文。
- `elastic modulus` 能召回 2024 年 Buildings 和 ETASR 弹性模量论文。
- `seismic behavior` 能召回 2024 年 Infrastructures 地震响应论文。
- `Peridynamics` 能召回 2025 年 Acta Geotechnica 全文。
- `hydration heat` 目前仍需要补充中文温控全文，下一批优先下载《堆石混凝土绝热温升性能初步研究》。

设计说明：

- 开放全文 PDF 可进入本地全文库，但不提交到远程仓库。
- CNKI 机构访问论文只用于本地私有学习和检索，不公开再分发全文。
- 不使用网盘盗版、破解下载、绕过验证码或反爬限制的来源。
- 当前 PDF 解析只支持文字层，不支持扫描版 OCR。

验证结果：

- `python -m pytest tests\test_ingestion_parser.py tests\test_documents_api.py -q`：8 个测试通过。
- `python -m pytest`：27 个测试通过。

## 2026-06-04 阶段 1 CNKI 机构访问原文导入记录

已完成：

- 使用用户已登录的 Chrome / CNKI 页面下载《堆石混凝土及堆石混凝土大坝》PDF。
- 在 `C:\Users\admin\Downloads` 中发现 5 个重复下载文件，保留原下载不动，复制最新文件到 `data/fulltext/cnki_pending/`。
- 复制后的稳定文件名为 `rfc_cnki_2005_jin_an_study_on_rock_fill_concrete_dam.pdf`。
- 检查 PDF 有文字层：共 6 页，前 3 页可抽取 4231 个字符。
- 更新 `data/fulltext_manifest.csv`，新增 `rfc_cnki_001`，来源类型为 `institutional_access_pdf`。
- 更新 `docs/source_catalog.md`，在“已下载机构访问全文”中登记该论文。
- 导入 SQLite，新增 document_id `21`，切分出 11 个 chunks。

校准结果：

- 当前数据库：21 篇 documents，811 个 chunks。
- 搜索“堆石混凝土大坝”可召回 CNKI 原文第 1 页和第 5 页相关 chunk。
- 搜索“新坝型”可召回 CNKI 原文摘要相关 chunk。
- 搜索“自密实混凝土 填充 堆石体”可召回 CNKI 原文中关于 1500 mm 堆石体填充能力、流动距离和施工质量控制的 chunk。

设计说明：

- 该 PDF 来自机构账号授权访问，只用于本地私有检索，不提交到 GitHub，不公开再分发全文。
- Chrome 下载列表中的重复文件暂不删除，避免误删用户原始下载记录。
- 当前 PDF 抽取文本中存在少量 `` 等 PDF 编码符号，后续可在 cleaner 中增加针对 PDF 的符号清洗规则。

## 2026-06-04 阶段 1 语料库自动扩容管道记录

已完成：

- 新增 `app/services/source_collection.py`，封装来源候选的结构、分类、去重、文件名清洗和 PDF 校验逻辑。
- 新增 `scripts/collect_sources.py`，支持从 OpenAlex、Semantic Scholar、Crossref 批量发现堆石混凝土相关论文候选，并可下载开放 PDF。
- 新增 `scripts/import_fulltext.py`，支持从 manifest 和本地目录批量导入 PDF，重复文件会通过 content hash 识别为 duplicate。
- 新增 `scripts/import_zotero.py`，支持 Zotero 本地 API 可用时读取 Zotero 条目和 PDF 附件并导入。
- 新增 `tests/test_source_collection.py`，验证主题分类、DOI 去重和安全文件名生成。
- 新增 `docs/corpus_pipeline.md`，记录学术 API、Zotero、本地 PDF 的自动扩容方式。

验证结果：

- `scripts/import_fulltext.py --manifest data\fulltext_manifest.csv`：已导入 PDF 均识别为 duplicate，没有重复入库。
- `scripts/import_zotero.py --query "rock-filled concrete"`：当前 Zotero 本地 API 不可用，脚本给出可理解提示。
- `python -m pytest`：30 个测试通过。

当前限制：

- 本机直连 OpenAlex、Semantic Scholar、Crossref 时出现 `SSL: UNEXPECTED_EOF_WHILE_READING`，PowerShell 和 Python 都复现。
- 判断为当前网络或代理层中断 HTTPS 连接；API 管道已实现，但需要配置代理或换网络后才能批量拉取候选。
- Zotero 当前未发现本地配置文件，需要先启动 Zotero Desktop 并启用本地 API。

## 2026-06-04 阶段 1 三通道扩容运行记录

用户要求使用三条通道获取资料，并及时反馈问题。

已运行：

- 学术 API 通道：`scripts/collect_sources.py`
- 本地 PDF / manifest 通道：`scripts/import_fulltext.py`
- Zotero 附件通道：`scripts/import_zotero.py`

学术 API 通道结果：

- 查询词：`rock-filled concrete`、`rock-filled concrete dam`、`self-compacting concrete rock-filled concrete`。
- OpenAlex 和 Crossref 成功返回候选。
- Semantic Scholar 返回 `HTTP 429`，表示当前请求被限流，后续需要降低频率或配置 API key。
- `data/source_candidates.csv` 当前记录 40 条候选。
- 其中 4 条包含 PDF URL，但本轮自动下载均失败：
  - MDPI `/pdf` 链接返回 403；该类链接后续应转换为 `mdpi-res.com` 静态 PDF 地址。
  - Springer 部分链接返回 HTML，不是直接 PDF，可能是受限或书籍资源。
  - EasyChair 预印本链接返回 404。
- 候选清单中出现相邻但不完全相关主题，例如 `concrete-faced rock-fill dam`，后续应增加 RFC 相关性过滤。

本地 PDF / manifest 通道结果：

- 扫描 `data/fulltext_manifest.csv`、`data/source_candidates.csv`、`data/fulltext/open_access/`、`data/fulltext/cnki_pending/`、`data/fulltext/open_access_auto/`。
- 已存在 PDF 均识别为 `duplicate`，没有重复入库。
- 数据库保持 21 篇 documents，811 个 chunks。

Zotero 通道结果：

- Zotero 本地 API 当前不可用。
- `zotero.py status --json` 显示未发现 Zotero profile / prefs file，`api_running=false`。
- `scripts/import_zotero.py` 给出提示：需要先启动 Zotero Desktop 并启用本地 API。

下一步改进：

- 为 `collect_sources.py` 增加更严格的堆石混凝土相关性过滤，排除混凝土面板堆石坝等相邻主题。
- 为 Semantic Scholar 增加 API key 支持和退避重试。
- 为 MDPI 链接增加 `/pdf` 到 `mdpi-res.com` 静态 PDF 的转换规则。
- 启动 Zotero Desktop 后重跑 Zotero 通道。

## 2026-06-04 阶段 1 题录优先语料库扩容记录

用户调整方向：当前不再需要更多论文全文，优先从 Google Scholar、CNKI 等大型学术入口及开放学术 API 获取可直接获得的题名、作者、期刊、摘要、关键词、DOI 和链接等题录语料，追求数量更大。

设计判断：
- 不把 Google Scholar 页面硬爬作为主链路，因为 Google Scholar 没有官方公开批量 API，直接抓页面容易触发验证码，且摘要字段不稳定。
- 不把 CNKI 全文批量抓取作为主链路，因为机构账号授权和网站访问边界需要保留；当前优先支持 CNKI 导出的题录/摘要文件导入。
- 主链路改为 `metadata-first`：先用 OpenAlex、Crossref、Semantic Scholar 等来源扩大题录覆盖面，再把高价值记录或已授权全文逐步补入。

已完成：
- 扩展 `app/services/source_collection.py` 的 `SourceCandidate`，新增 `abstract`、`keywords`、`language`、`citation_count` 字段。
- 修正来源过滤中的中文关键词乱码，使 `堆石混凝土`、`自密实堆石混凝土`、`混凝土面板堆石坝` 等中文判断可用。
- 新增 OpenAlex 摘要还原、Crossref/Semantic Scholar 摘要去标签、语言推断、JSONL 输出和题录 Markdown 卡片生成能力。
- 更新 `scripts/collect_sources.py`，使学术 API 采集从“PDF 候选优先”升级为“题录元数据优先，PDF 可选下载”。
- 新增 `scripts/collect_metadata_corpus.py`，支持：
  - 从 OpenAlex、Semantic Scholar、Crossref 批量采集题录元数据。
  - 跳过某个 API，例如 `--skip-semantic-scholar`。
  - 合并 CNKI、Google Scholar 辅助工具、EndNote、Zotero 或 Publish or Perish 导出的 CSV/TSV/RIS/EndNote 文本文件。
  - 生成 `data/metadata/rfc_papers_metadata.csv`、`data/metadata/rfc_papers_metadata.jsonl` 和 `data/imports/metadata_corpus/*.md`。
  - 将题录卡片以 `metadata_record` 类型导入 SQLite。
- 增加题录导入去重保护：重新生成卡片时，若数据库已存在相同 `metadata_record` 的题名或来源路径，则跳过，避免重复刷屏。

本轮运行命令：

```powershell
.\.venv\Scripts\python.exe scripts\collect_metadata_corpus.py `
  --skip-semantic-scholar `
  --query "rock-filled concrete" `
  --query "rock filled concrete" `
  --query "rock-fill concrete dam" `
  --query "self-compacting rock-filled concrete" `
  --query "self-compacting concrete prepacked rock" `
  --query "堆石混凝土" `
  --query "自密实堆石混凝土" `
  --query "金峰 堆石混凝土" `
  --limit 100 `
  --max-records 300 `
  --import-to-db
```

运行结果：
- OpenAlex + Crossref 共返回 562 条原始候选。
- RFC 相关性过滤后保留 116 条题录。
- 69 条含公开摘要。
- 生成 116 个 Markdown 题录卡片。
- 当前 SQLite：136 篇 documents、997 个 chunks。
- 来源类型分布：`local_file=10`、`open_access_pdf=10`、`institutional_access_pdf=1`、`metadata_record=115`。
- `data/metadata/rfc_papers_metadata.csv` 来源分布：OpenAlex 52 条、OpenAlex+Crossref 44 条、Crossref 20 条。

检索校准：
- `filling capacity` 可以命中填充能力相关题录、资料卡和 PDF chunk。
- `temperature rock-filled concrete` 可以命中温度场、绝热温升、施工参数影响等题录和全文片段。
- `Quality Control Instrumentation` 可以命中 RFC 大坝质量控制相关题录章节。
- 中文 `施工质量` 和 `堆石混凝土` 可以命中 CNKI 原文、早期资料卡和相关题录。

暴露问题：
- Semantic Scholar 未配置 API key 时容易返回 `HTTP 429`，当前用 `--skip-semantic-scholar` 保证批量运行速度。
- Crossref 的 `select` 字段不支持 `language`，已去掉该字段并完成补跑。
- 有 1 个题名对应两个 DOI，文件名已改为包含 `source_id`，避免卡片文件覆盖；数据库检索层仍按题名跳过重复显示。
- 当前 `metadata_record` 作为 Markdown 卡片进入 `documents/chunks`，这是阶段 1 的最小实现；后续阶段 4 更适合新增独立 `sources` 或 `papers` 表。

验证结果：
- `python -m pytest tests\test_source_collection.py -q`：9 个测试通过。
- `python -m pytest`：36 个测试通过。

## 2026-06-04 阶段 1 关键词检索评测与微调记录

用户要求：
- 建立 `data/evaluation/keyword_queries.csv`，记录问题、关键词、期望命中文档和备注。
- 编写 `scripts/evaluate_keyword_search.py`，自动运行关键词检索并输出命中结果。
- 根据结果微调关键词检索，重点检查中文、英文、同义词、标题加分和 `metadata_record` 是否过度刷屏。

已完成：
- 新增 `data/evaluation/keyword_queries.csv`，包含 15 个阶段 1 代表性问题，覆盖：
  - 施工质量 / 质量控制
  - 填充能力
  - 温升 / 水化热 / 温控
  - 弹性模量
  - 抗震 / seismic
  - 综述 / next generation
  - 细观 / 数值模拟
  - 冷缝 / 剪切
  - Peridynamics
  - 施工信息管理
  - 密实度检测
  - 坝型设计
  - 再生骨料
- 新增 `scripts/evaluate_keyword_search.py`：
  - 读取评测 CSV。
  - 调用 `KeywordSearchService`。
  - 判断期望题名、期望内容词和期望来源类型是否命中。
  - 输出 `data/evaluation/keyword_results.csv`。
  - 汇总每条查询的 pass/fail、hit_rank、hit_title、hit_source_type、metadata_ratio。
- 初次评测结果：11/15 通过。
- 失败集中在：
  - `弹性模量` 没有稳定召回 `elastic modulus`。
  - `细观 / 数值 / 模拟` 没有稳定召回 `mesoscopic / simulation`。
  - `peridynamics` 被 `rock-filled concrete / concrete` 等泛词淹没。
  - `quality control instrumentation RFC dam` 没有稳定召回质量控制章节。
- 更新 `app/services/retrieval/keyword_search.py`：
  - 增加 `SearchTerm`，让每个查询词带权重和“是否具体词”的标记。
  - 增加中英文同义词扩展，例如：
    - `弹性模量` -> `elastic modulus`
    - `细观` -> `mesoscopic / mesoscale`
    - `施工质量` -> `quality control / construction quality / instrumentation`
    - `温升 / 水化热` -> `temperature / hydration heat / adiabatic temperature rise`
    - `抗震` -> `seismic / earthquake`
  - 降低 `concrete`、`dam`、`rock-filled`、`堆石混凝土` 等领域泛词在多词查询中的权重。
  - 对命中次数做上限裁剪，避免长 PDF 中泛词重复次数过多导致分数虚高。
  - 加入来源均衡：当存在全文或资料卡命中时，`metadata_record` 在 top_k 中最多优先占约 60%，避免题录卡片刷屏。
  - 检索结果新增 `source_type`，便于 API 和评测识别来源类型。
- 更新 `app/schemas/search.py` 和 `app/api/search.py`，让 `POST /search` 返回每条结果的 `source_type`。
- 更新 `tests/test_keyword_search.py`：
  - 验证中文 `弹性模量 堆石混凝土` 可以召回英文 `Elastic Modulus` 题录。
  - 验证 `peridynamics` 这类具体词不会被泛词重复次数淹没。

最终评测结果：
- `scripts/evaluate_keyword_search.py`：15/15 通过。
- `metadata_ratio` 最高控制在 0.50。
- `data/evaluation/keyword_results.csv` 已记录本轮评测结果。

验证结果：
- `python -m pytest tests\test_keyword_search.py tests\test_search_api.py -q`：6 个测试通过。
- `python -m pytest`：38 个测试通过。
- `python -m py_compile scripts\evaluate_keyword_search.py app\services\retrieval\keyword_search.py app\schemas\search.py app\api\search.py`：通过。

面试表达：

```text
阶段 1 不只是实现关键词检索，还建立了一个小型检索评测集。评测集把典型问题、查询词和期望命中文档写成 CSV，再由脚本自动运行检索并输出命中排名和来源类型。根据评测结果，我发现关键词检索容易被领域泛词影响，所以加入了中英文同义词扩展、具体词加权、泛词降权和 metadata_record 来源均衡。最终 15 个代表性问题全部通过，形成了后续向量检索的 baseline。
```

## 2026-06-05 阶段 1 合并与文档校准记录

已完成：

- 将 `codex/phase-1-document-ingestion` 合并到 `main`。
- 推送远程 `origin/main`。
- 校准 `README.md`，明确当前阶段为阶段 1 已完成，并列出 documents/chunks、导入链路、关键词检索、评测集和测试覆盖。
- 校准 `obsidian-vault/阶段索引.md`，将阶段 1 从“计划中”移动到“已完成”，并把阶段 2 标为下一阶段。
- 校准 `obsidian-vault/首页.md`，将当前重点从阶段 0 更新为阶段 1 已完成、阶段 2 下一阶段。
- 校准 `obsidian-vault/阶段/阶段 1 - 本地资料导入与关键词检索.md`，将状态从“待开发”改为“已完成”，并补充完成内容、验证结果、知识点链接和面试表达。
- 校准 `AGENT.MD` 末尾的“当前推荐的第一步”，不再指向阶段 0 初始化，而是指向阶段 2 的 Embedding 与向量检索。
- 校准 `AGENT.MD` 的“检索策略”，修正为阶段 1 关键词检索、阶段 2 embedding 向量检索、后续再做 rerank 和引用式问答。

验证结果：

- 合并前运行 `python -m pytest`：38 个测试通过。

当前文档权威性：

- `docs/progress.md` 是最权威的阶段进度记录。
- `README.md` 是新读者入口。
- `AGENT.MD` 是后续 agent 的工作规则。
- `obsidian-vault/阶段索引.md` 是复习和知识库导航。

下一步：

- 新开阶段 2 分支 `codex/phase-2-vector-search`。
- 设计 embedding 模型选择、向量索引方案、chunk embedding 保存结构和向量检索评测方式。

## 2026-06-05 阶段 2 完成记录：Embedding 与向量检索

当前分支：`codex/phase-2-vector-search`

当前阶段：阶段 2 已完成。下一步准备进入阶段 3：引用式问答。

已完成：

- 使用 `planning-with-files` 生成并维护阶段 2 规划文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- 新增 `docs/stage2_learning_notes.md`，按步骤沉淀阶段 2 学习笔记和面试表达。
- 新增 `app/services/retrieval/embedding.py`：
  - 定义 `EmbeddingProvider` 抽象。
  - 实现 `DeterministicEmbeddingProvider`，用于无 API key 的本地开发和稳定测试。
  - 提供 `create_embedding_provider()`，为后续切换真实 embedding 模型预留入口。
- 新增 `chunk_embeddings` 表：
  - 记录 `chunk_id`、`provider`、`model_name`、`dimension`、`embedding_json`、`content_hash`。
  - 使用 `chunk_id + provider + model_name` 唯一约束避免重复索引。
  - 与 `chunks` 建立关联，删除 chunk 时可级联删除对应 embedding。
- 扩展 `ChunkEmbeddingRepository`：
  - 支持保存、更新、查询、列出和统计 chunk embeddings。
  - 支持 `serialize_embedding()` 和 `deserialize_embedding()`。
  - 支持批量索引时延迟提交，减少大量写入时的数据库提交次数。
- 新增 `VectorIndexService`：
  - 扫描 chunks。
  - 判断已有 embedding 是否过期。
  - 批量调用 embedding provider。
  - 写入或更新 `chunk_embeddings`。
  - 返回 total、indexed、updated、skipped 等构建统计。
- 新增 `scripts/build_vector_index.py`：
  - 支持从命令行构建向量索引。
  - 默认使用 `.env` 中的 `EMBEDDING_PROVIDER`，未配置时使用 deterministic provider。
- 新增 `VectorSearchService`：
  - 把用户问题转成 query embedding。
  - 读取同一 provider/model/dimension 的 chunk embedding。
  - 计算余弦相似度并按 score 排序。
  - 跳过内容 hash 不一致的 stale embedding。
- 扩展 `app/api/search.py`：
  - 保留阶段 1 的 `POST /search` 关键词检索。
  - 新增 `POST /search/vector` 向量检索入口。
- 扩展 `app/schemas/search.py`：
  - 新增 `VectorSearchRequest`。
  - 新增 `VectorSearchResponse`，返回 provider 和 model_name，便于排查当前使用的 embedding 实现。
- 新增 `scripts/evaluate_vector_search.py`：
  - 复用 `data/evaluation/keyword_queries.csv`。
  - 输出 `data/evaluation/vector_results.csv`。
  - 读取 `data/evaluation/keyword_results.csv`，对比关键词 baseline 和向量检索结果。
- 新增和更新自动化测试：
  - `tests/test_embedding_provider.py`
  - `tests/test_db_models.py`
  - `tests/test_repositories.py`
  - `tests/test_vector_index_service.py`
  - `tests/test_vector_search.py`
  - `tests/test_vector_search_api.py`
  - `tests/test_evaluate_vector_search.py`

阶段 2 设计结论：

- 本阶段没有直接接入 FAISS、Chroma 或云端 embedding 模型，而是先用 SQLite + deterministic embedding 跑通最小链路。
- `documents` 和 `chunks` 仍是主数据源，`chunk_embeddings` 是可重建索引数据。
- 向量检索与关键词检索保持并行：
  - `POST /search` 是阶段 1 keyword baseline。
  - `POST /search/vector` 是阶段 2 vector search。
- 评测必须复用同一批问题，避免不同检索方式比较口径不一致。
- 当前 deterministic embedding 只能证明链路和工程边界可运行，不能证明真实语义召回效果已经优于关键词检索。

评测结果：

- `scripts/evaluate_keyword_search.py`：关键词 baseline 15/15 通过。
- `scripts/evaluate_vector_search.py`：向量检索 11/15 通过。
- 向量检索失败样例：
  - `filling_capacity_en`
  - `mesoscopic_modeling`
  - `peridynamics`
  - `construction_management`

验证结果：

- `python -m pytest tests/test_embedding_provider.py -q`：7 个测试通过。
- `python -m pytest tests/test_vector_index_service.py -q`：5 个测试通过。
- `python -m pytest tests/test_vector_search.py tests/test_vector_search_api.py -q`：7 个测试通过。
- `python -m pytest tests/test_evaluate_vector_search.py -q`：3 个测试通过。
- `python scripts/evaluate_vector_search.py`：向量检索 11/15，关键词 baseline 15/15。
- `python -m pytest -q`：63 个测试通过。

已处理问题：

- 写出 `def batched[T]` 后发现该语法只支持 Python 3.12；项目使用 Python 3.11，因此改为 `TypeVar` 写法。
- 首次运行向量评测脚本超时；定位为首次索引构建时逐条 commit 成本高，已改为 batch commit。
- 用户指出“新词解释”规则容易遗漏；已将新词解释写入 `AGENT.MD` 的自检要求、`task_plan.md` 验收项和 `docs/stage2_learning_notes.md`。

遗留问题：

- 当前 deterministic embedding 是稳定测试用实现，不是真实语义模型。
- 向量检索 11/15 弱于关键词 baseline 15/15，说明下一步需要真实 embedding、混合检索或 query expansion。
- 尚未实现引用式回答、上下文组织、拒答机制和聊天模型调用，这些属于阶段 3。
- 尚未接入 FAISS/Chroma/PGVector；当前 SQLite 向量保存适合阶段 2 最小链路和迁移前验证。

面试表达：

```text
阶段 2 我没有直接把文本丢进向量库，而是先把 embedding 模型调用、向量保存、索引构建、向量检索和评测拆成独立模块。

EmbeddingProvider 负责把文本转成向量；chunk_embeddings 表保存每个 chunk 的向量、模型信息、维度和内容 hash；VectorIndexService 负责批量构建索引；VectorSearchService 负责把用户问题向量化并按余弦相似度召回 chunk。API 层只暴露 /search/vector，不直接写检索细节。

为了防止只凭演示判断效果，我复用了阶段 1 的关键词评测集，对关键词 baseline 和向量检索使用同一批问题做对比。当前 deterministic embedding 下向量检索为 11/15，关键词 baseline 为 15/15，这说明工程链路已经打通，但真实语义效果还需要后续接入更好的 embedding 模型或混合检索。
```

下一步：

- 进入阶段 3：引用式问答。
- 先基于 `POST /search/vector` 的返回结果组织上下文。
- 新增聊天模型 provider 抽象。
- 实现 `POST /chat`，返回回答和来源。
- 遇到资料不足时明确拒答，不让模型硬编。

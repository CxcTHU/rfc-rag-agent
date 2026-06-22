# 阶段 51 任务计划：Phase 50 性能评测与全周期架构演进对照

## Goal

在阶段 50 已合并到 `main`、`phase-50-complete` tag 已存在且不移动任何阶段 tag 的前提下，从 `main` 创建/切换到 `codex/phase-51-performance-evaluation`，完成阶段 51 的开发、测试、普通文档和 Obsidian 草稿收尾；用户已于 2026-06-22 明确授权提交、打 `phase-51-complete` tag、推送、创建 PR 并合并。

核心交付：
- 将 LangGraph 节点命名从 `route_query_node` 重命名为 `planner_node`，保持行为不变。
- 新增 `scripts/evaluate_phase51_performance.py`，默认 dry-run，显式 `--execute` 才调用真实 provider。
- 输出 `data/evaluation/phase51_performance_results.csv` 与 `data/evaluation/phase51_performance_summary.csv`。
- 扩展 `G:\Codex\program\关键提升\agent_evolution_comparison.md` 为 Brain 直通到 LangGraph + Planner + Cache 命中的全周期对照。
- 完成 `docs/phase_reviews/phase-51.md`、普通文档与 Obsidian 阶段汇报。
- 人工核验授权后执行 `git add`、commit、`phase-51-complete` tag、push、PR 创建与 merge。

## Baseline

- 当前分支：`codex/phase-51-performance-evaluation`
- 起点：`main -> a32fd804 Merge phase 50 LangGraph Redis and pgvector`
- 阶段 50 tag：`phase-50-complete -> b1dc0ff7 Complete phase 50 LangGraph Redis and pgvector`
- 核验：`phase-50-complete` 是 `main` 祖先；未移动任何已有阶段 tag。
- 默认链路：LangGraph + Flash Planner + pgvector HNSW；阶段 51 未改 `app/core/config.py` 默认值。

## Phase Order

### Phase 0：启动校准与 `planner_node` 重命名

**RAG 链路位置**：LangGraph Agent 的规划节点，位于 `/agent/query mode="langgraph_agent"` 进入 StateGraph 后、具体工具节点执行前。

**为什么现在做**：阶段 50 已把该节点职责扩展为“选择下一步 ReAct action”，继续叫 `route_query_node` 容易误导；阶段 51 评测前先统一术语。

任务：
- [x] 将 `route_query_node` 重命名为 `planner_node`。
- [x] 更新 `graph_nodes.py`、`graph_builder.py`、相关测试和文档引用。
- [x] 保持行为不变：图像/表格硬规则、planner provider、deterministic fallback、latency trace 均不变。
- [x] 运行聚焦测试与全量 pytest。
- [x] 更新 `task_plan.md`、`findings.md`、`progress.md`。

验证方式：
- 聚焦测试覆盖 LangGraph node/builder/planner。
- `python -m pytest -q` 通过。

完成标准：
- 代码和当前文档无 `route_query_node` 作为现行节点名残留。
- 全量 pytest 通过。

### Phase 1：阶段 51 评测脚本设计与 dry-run

**RAG 链路位置**：评测层，调用 `/chat` 与 `/agent/query` 的公开服务路径，不直接改默认运行链路。

**为什么现在做**：阶段 50 新增 LangGraph、planner、pgvector、Semantic Cache 后，需要可复跑、可脱敏、可切换的统一评测脚本。

任务：
- [x] 新增 `scripts/evaluate_phase51_performance.py`。
- [x] 复用 Phase 37 的 8 个评测问题。
- [x] 覆盖 `brain_baseline`、`react_agent`、`tool_calling_agent`、`langgraph_deterministic`、`langgraph_flash_planner`、`langgraph_faiss_fallback`。
- [x] 覆盖 Semantic Cache 命中场景。
- [x] 默认 dry-run，使用 deterministic/fake provider，不调用真实 API。
- [x] 所有对照配置通过脚本内部临时切换或显式 mode 参数实现，评测结束后恢复，不改默认配置。
- [x] 输出 results/summary CSV。
- [x] 补充脚本测试。
- [x] 更新三份工作记忆文件。

验证方式：
- 脚本 dry-run 能生成 CSV。
- 测试验证配置矩阵、字段、默认 dry-run、敏感信息不落盘。

完成标准：
- dry-run 完整覆盖六种配置 + cache 场景。
- CSV 仅包含配置、延迟、质量指标、脱敏错误摘要，不包含 raw provider response 或受限全文。

### Phase 2：真实 Provider 执行与数据采集

**RAG 链路位置**：端到端评测层，显式 `--execute` 调用真实 provider，读取 latency trace 与检索后端信息。

**为什么现在做**：dry-run 只能证明脚本正确；真实 provider 数据用于回答“性能提升多少、质量是否退化、pgvector 与 FAISS 子链路差异多大”。

任务：
- [x] 运行 `python scripts/evaluate_phase51_performance.py --execute`。
- [x] 采集 6 x 8 延迟/质量数据。
- [x] 采集 pgvector HNSW vs FAISS 的向量检索子链路后端与延迟对照。
- [x] 采集 Semantic Cache 命中率与命中延迟。
- [x] 生成并复核 summary CSV。
- [x] 如真实配置缺失，记录 skipped/error，不伪造成成功。
- [x] 更新三份工作记忆文件。

验证方式：
- `phase51_performance_results.csv` 与 `phase51_performance_summary.csv` 存在且 schema 正确。
- CSV 不含 API key、Bearer token、raw response、reasoning_content、hidden thought、受限全文。

完成标准：
- 真实评测完成或以明确 skipped/error 状态记录不可执行原因。
- 默认链路仍为 LangGraph + Flash Planner + pgvector HNSW。

### Phase 3：全周期架构演进对照表更新

**RAG 链路位置**：架构复盘层，把 Brain 直通、Agent 编排、tool calling、LangGraph、向量后端和 cache 收益放到同一张表。

**为什么现在做**：阶段 51 的性能数据需要沉淀为长期可读的架构演进材料，而不是只留下 CSV。

任务：
- [x] 更新 `G:\Codex\program\关键提升\agent_evolution_comparison.md`。
- [x] 从三列 P32/P34/P37 扩展为全周期：Brain 直通、MIMO ReAct、Flash+Pro、Tool Calling、LG 规则路由、LG+Planner、Cache 命中。
- [x] 新增路由架构类型、向量检索后端、向量检索延迟、planner latency、端到端延迟、Semantic Cache 收益等行。
- [x] 写明关键结论和适用边界。
- [x] 更新三份工作记忆文件。

验证方式：
- 对照表存在新增列和新增维度行。
- 数值引用来自阶段 37、阶段 50、阶段 51 CSV 或明确标注为历史/缺失/不适用。

完成标准：
- 对照表能支撑面试表达：架构为什么演进、每代解决什么问题、代价是什么、阶段 51 数据说明了什么。

### Phase 4：回归验证、普通文档与 Obsidian 收尾

**RAG 链路位置**：阶段收尾层，验证运行链路、质量门、文档和知识库一致。

**为什么现在做**：阶段 51 涉及评测脚本、CSV、跨目录文档和 Obsidian 汇报，必须在人工核验前留下完整可审查状态。

任务：
- [x] 运行全量 pytest。
- [x] 运行 `python scripts/score_stage30_quality.py`，确认 91.52/A/pass 不退化。
- [x] 更新 `README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- [x] 新增 `docs/phase_reviews/phase-51.md`。
- [x] 建立 `obsidian-vault/阶段汇报/阶段 51 - 性能评测与架构演进对照/`。
- [x] 建立阶段 51 Phase 汇报索引与 Phase 0 到 Phase 4 小汇报。
- [x] 更新 `obsidian-vault/阶段汇报索引.md`。
- [x] 每篇 Obsidian 小汇报包含：目标、主要任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达。
- [x] 更新三份工作记忆文件为最终人工核验前状态。

验证方式：
- 全量 pytest 通过。
- Stage 30 `91.52 / A / pass`。
- 普通文档、阶段 review、Obsidian 汇报齐全。
- `git status -sb` 显示未提交状态；不执行 stage/commit/tag/push/PR。

完成标准：
- 阶段 51 开发、测试、普通文档、Obsidian 草稿均完成。
- 最终停在用户人工核验前状态。

## Safety Boundaries

- 不新增外部数据源。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始敏感响应、`raw_response`、`reasoning_content`、hidden thought、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 不移动已有阶段 tag。
- 不执行 `git add`、commit、tag、push、PR。
- 不重置 Git，不覆盖无关用户改动。
- 默认链路锁定为 LangGraph + Flash Planner + pgvector HNSW；评测对照通过显式 mode 和脚本内部临时开关完成，结束后恢复。

## Completion Checklist

- [x] `planner_node` 重命名完成。
- [x] 全量 pytest 通过：`1112 passed, 1 skipped`。
- [x] 评测脚本 dry-run 通过：`rows=56 summary=7`。
- [x] 真实评测执行并生成 results/summary CSV：`rows=56 summary=7`。
- [x] `agent_evolution_comparison.md` 扩展为全周期对照。
- [x] Stage 30 仍为 `91.52 / A / pass`。
- [x] 普通文档和 Obsidian 草稿完成。
- [x] 已获用户人工核验授权，进入提交、tag、push、PR 与 merge 流程。

## Follow-up Plan: LangGraph Cross-turn Evidence Memory

**RAG 链路位置**：LangGraph Agent 的 `initialize_state()` 之后、`planner_node` 决策之前，以及 `generate_answer_node` 生成最终引用回答时。

**为什么现在做**：用户追问“请详细回答”时，后端已经传入 `conversation_id` 并使用同一 `thread_id` 做 checkpoint，但新一轮 state 会清空 `sources` / `citations` / `search_results`。如果 planner 看不到上一轮 evidence，就只能重新检索，浪费一次 hybrid 检索和一次 LLM 调用。

任务：
- [x] `LangGraphAgentState` 新增 `prior_sources`、`prior_citations`、`prior_answer_summary`。
- [x] `LangGraphAgentService.query()` 在 invoke 前读取同一 thread 最新 checkpoint，提取最近一轮 evidence，失败时 fail-open。
- [x] `prior_sources` 只保留 source id、标题、heading、截断 content 等轻量字段，避免 checkpoint state 膨胀。
- [x] `planner_node` 让 deterministic planner 和 LLM planner 都能看到 prior evidence；展开类追问且 prior evidence 充足时直接选择 `answer_with_citations`，新方向问题仍走 `search_knowledge`。
- [x] `generate_answer_node` 在当前轮无 sources 但存在 prior_sources 时，复用 prior evidence 走轻量 evidence prompt 生成回答。
- [x] 补充 checkpoint 读取失败、prior evidence 压缩、planner 决策、prior_sources 回答生成测试。
- [x] 同步修正“请详细回答”不再走硬编码 `followup_transform` 的 API/intent 测试预期。

验证方式：
- `python -m pytest tests/test_intent_router.py tests/test_agent_api.py::test_agent_api_detail_followup_uses_agent_tool_decision -q`
- `python -m pytest tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py -q`
- `python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py tests/test_phase50_semantic_cache.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py -q`
- `python -m pytest -q`
- `python scripts/score_stage30_quality.py`

完成标准：
- LangGraph 可以从上一轮 checkpoint 恢复最近 evidence，但不覆盖当前轮 `sources` / `citations`。
- 展开类追问可直接基于 prior evidence 回答；新方向问题仍检索。
- checkpoint 读取失败不影响原链路。
- 默认配置和 `app/core/config.py` 不变。
- 用户已授权执行 `git add`、commit、tag、push、PR 与 merge；仍不得提交敏感信息或运行态大文件。

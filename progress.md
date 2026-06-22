# 阶段 51 Session Progress

## 阶段信息

- 阶段：51 - Phase 50 性能评测与全周期架构演进对照
- 当前分支：`codex/phase-51-performance-evaluation`
- 起点：`main -> a32fd804 Merge phase 50 LangGraph Redis and pgvector`
- 阶段 50 tag：`phase-50-complete -> b1dc0ff7 Complete phase 50 LangGraph Redis and pgvector`
- tag 状态：`phase-50-complete` 存在且是 `main` 祖先；未移动任何 tag
- 提交状态：用户已于 2026-06-22 明确授权 `git add`、commit、`phase-51-complete` tag、push、PR 创建与 GitHub merge

## 启动日志：2026-06-21

- 已按入口规则阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 已阅读阶段 51 专项计划：`docs/stage51_evaluation_plan.md`。
- 已阅读根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 已运行 `git status -sb`、`git log --oneline -5`、tag/main 祖先核验。
- 当前 `main` 与 `origin/main` 对齐，最新提交为 `a32fd804`。
- 可见未跟踪文件：`docs/stage51_evaluation_plan.md`。
- Planning with Files catchup 脚本未在 `.claude` 路径找到；已手动完成上下文恢复。
- 已从 `main` 创建并切换到 `codex/phase-51-performance-evaluation`。
- 已将当前对话线程标题改为“阶段51-性能评测与架构演进对照”。
- 已校准 `task_plan.md`、`findings.md`、`progress.md` 为阶段 51 计划、关键理解和启动状态。

## Phase Log

- Phase 0：complete
- Phase 1：complete
- Phase 2：complete
- Phase 3：complete
- Phase 4：complete

## Phase 0：`planner_node` 重命名

本 Phase 解决 LangGraph 节点命名与职责不一致的问题。在 RAG 链路中，它位于 LangGraph Agent 进入状态图后、具体工具节点执行前，负责选择下一步 ReAct action。现在先做，是为了让阶段 51 的评测与文档使用统一术语。

完成内容：
- `app/services/agent/graph_nodes.py`：`route_query_node` 重命名为 `planner_node`。
- `app/services/agent/graph_builder.py`：StateGraph 节点名从 `"route"` 改为 `"planner"`，entry point 与回边同步更新。
- `tests/test_phase50_langgraph_planner.py`、`tests/test_phase50_langgraph_nodes.py`、`tests/test_phase50_langgraph_builder.py`：测试名称、import 和断言同步为 `planner_node` / `"planner"`。
- 当前文档：README、AGENT.MD、docs/architecture.md、docs/phase_reviews/phase-50.md 已同步现行命名。
- 验证：聚焦 `21 passed`；全量 `1110 passed, 1 skipped`。
- 提交状态：未 `git add`、未 commit、未 tag、未 push、未 PR。

## Phase 1：评测脚本设计与 dry-run

本 Phase 解决阶段 50 新增 LangGraph、planner、pgvector 和 Semantic Cache 后缺少统一量化对照的问题。在 RAG 链路中，它位于评测层，通过 `/chat` 与 `/agent/query` 的公开服务路径采集端到端和子链路指标，不改默认运行链路。

完成内容：
- 新增 `scripts/evaluate_phase51_performance.py`。
- 复用 Phase 37 的 8 题，覆盖 Brain baseline、ReAct、Tool Calling、LangGraph deterministic、LangGraph flash planner、LangGraph FAISS fallback 与 Semantic Cache hit 场景。
- 默认 dry-run 使用内存 SQLite fixture、deterministic chat/embedding 和 dry-run planner provider；不调用真实 API。
- `--execute` 路径读取本地配置和真实数据库；真实 planner 未配置时写 skipped，不伪造成成功。
- 输出 `data/evaluation/phase51_performance_results.csv` 与 `data/evaluation/phase51_performance_summary.csv`。
- 验证：新增测试 `2 passed`；相关回归 `11 passed`；完整 dry-run `rows=56 summary=7`。
- 提交状态：未 `git add`、未 commit、未 tag、未 push、未 PR。

## Phase 2：真实 Provider 评测执行

本 Phase 解决 dry-run 只能验证脚本正确、无法回答真实性能收益的问题。在 RAG 链路中，它是端到端评测执行层，通过显式 `--execute` 使用本地配置的真实 provider 和数据库采集 6 x 8 延迟/质量数据、pgvector vs FAISS 子链路差异和 Semantic Cache 命中收益。

完成内容：
- 真实评测最终完成：`data/evaluation/phase51_performance_results.csv` 为 56 行，`data/evaluation/phase51_performance_summary.csv` 为 7 行。
- 每个配置均 8/8 ok，无 skipped、无 errors。
- pgvector 对照：`react_agent`、`tool_calling_agent`、`langgraph_deterministic`、`langgraph_flash_planner` primary backend 为 `pgvector_hnsw`。
- FAISS fallback 对照：`langgraph_faiss_fallback` primary backend 为 `faiss`。
- Semantic Cache hit：8/8，avg final latency `1.000 ms`。
- 两次长时间真实执行超时后，脚本补充 checkpoint 与 `--resume`，最终用 resume 补齐缺口。
- 敏感字段扫描通过：CSV 未包含 API key、Bearer、Authorization、raw_response、reasoning_content。
- 提交状态：未 `git add`、未 commit、未 tag、未 push、未 PR。

## Phase 3：全周期架构演进对照表

本 Phase 解决 CSV 数据尚未沉淀成长期架构复盘材料的问题。在 RAG 链路中，它属于架构复盘层，把 Brain 直通、ReAct、Tool Calling、LangGraph、pgvector/FAISS 和 Semantic Cache 放进同一张演进表。

完成内容：
- 更新 `G:\Codex\program\关键提升\agent_evolution_comparison.md`。
- 对照表从历史三阶段扩展为 Brain 直通、MIMO ReAct、Flash+Pro、Tool Calling、LG 规则路由、LG+Planner、Cache 命中。
- 纳入 Phase 51 真实评测 summary：每个配置 8/8 ok，Semantic Cache hit 8/8。
- 写明 pgvector HNSW vs FAISS 的当前量化边界：记录后端与端到端延迟，recall@5 需后续专门检索评测进一步量化。
- 提交状态：未 `git add`、未 commit、未 tag、未 push、未 PR。

## Phase 4：回归验证与文档收尾

本 Phase 解决阶段成果需要进入人工核验前一致状态的问题。在 RAG 链路中，它不改变 runtime，而是验证默认链路、质量门、普通文档和 Obsidian 汇报一致。

完成内容：
- 新增 `docs/phase_reviews/phase-51.md`。
- 更新 `README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 建立 `obsidian-vault/阶段汇报/阶段 51 - 性能评测与架构演进对照/`。
- 建立阶段 51 Phase 汇报索引和 Phase 0-4 小汇报。
- 更新 `obsidian-vault/阶段汇报索引.md`。
- 更新 `task_plan.md`、`findings.md`、`progress.md` 到最终人工核验前状态。
- 提交状态：未 `git add`、未 commit、未 tag、未 push、未 PR。

## Test Results

- Phase 0 focused regression：`python -m pytest tests/test_phase50_langgraph_planner.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py -q` -> `21 passed`
- Phase 0 full regression attempt 1：`python -m pytest -q` -> timeout after 124 seconds; no failure conclusion
- Phase 0 full regression attempt 2：`python -m pytest -q` -> `1110 passed, 1 skipped`
- Phase 1 focused tests：`python -m pytest tests/test_phase51_performance_eval.py -q` -> `2 passed`
- Phase 1 related regression：`python -m pytest tests/test_phase51_performance_eval.py tests/test_phase50_langgraph_planner.py tests/test_phase50_langgraph_builder.py -q` -> `11 passed`
- Phase 1 full dry-run：`python scripts/evaluate_phase51_performance.py` -> `rows=56 summary=7`
- Phase 2 execute attempt 1：`python scripts/evaluate_phase51_performance.py --execute` -> timeout after 904 seconds
- Phase 2 execute attempt 2 with checkpoint：`python scripts/evaluate_phase51_performance.py --execute` -> timeout after 1804 seconds, checkpoint kept 53 rows
- Phase 2 resume：`python scripts/evaluate_phase51_performance.py --execute --resume` -> `rows=56 summary=7`
- Phase 2 sensitive scan：results/summary CSV contained no matches for api key, bearer, authorization, raw_response, reasoning_content
- Phase 4 full regression：`python -m pytest -q` -> `1112 passed, 1 skipped in 119.05s`
- Phase 4 Stage 30 quality gate：`python scripts/score_stage30_quality.py` -> `stage30 quality score overall=91.52 grade=A release_decision=pass`

## Follow-up：LangGraph 回答节点性能修复（2026-06-22）

本次修复解决 LangGraph 回答节点在已有检索证据后仍二次调用 `answer_with_citations()` 的问题。在 RAG 链路中，它位于 `search_knowledge_node` 写入 evidence 后、最终中文引用回答生成前；现在做，是为了让 LangGraph 像 Tool Calling 一样复用已有 sources，避免重复 hybrid 检索和重型 Brain citation prompt。

完成内容：
- `app/services/agent/graph_nodes.py`：`generate_answer_node` 在 state 中已有 `sources` 时直接调用 `chat_model_provider.generate()`，使用轻量 evidence prompt 生成引用回答。
- 保留 citation 抽取与轻量 citation repair；无 sources 时 fallback 到旧 `answer_with_citations()` 全流程。
- 加入 responsibility gate 与 topic anchor gate，确保 off-topic / 工程责任判断问题不会因为已有相似 evidence 被强答。
- `scripts/evaluate_phase51_performance.py`：新增 `--config` 过滤能力，可只重跑并覆盖指定配置旧行，保留其他对照数据。
- 测试更新：补充已有 sources 不二次检索、sources 缺失 fallback、off-topic 不调用 LLM 的覆盖。
- 真实评测：`python scripts/evaluate_phase51_performance.py --execute --config 'langgraph_deterministic,langgraph_flash_planner'` -> `rows=56 summary=7`。
- 新延迟：`langgraph_deterministic 41214.309 ms -> 34284.103 ms`；`langgraph_flash_planner 47157.740 ms -> 21110.586 ms`；对照 `tool_calling_agent` 仍为 `21204.028 ms`。
- 敏感字段扫描：Phase 51 results/summary CSV 未命中 API key、Bearer、Authorization、raw_response、reasoning_content。
- 聚焦回归：`python -m pytest tests/test_phase51_performance_eval.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py -q` -> `27 passed`。
- 全量回归：`python -m pytest -q` -> `1116 passed, 1 skipped in 170.94s`。
- Stage 30：`python scripts/score_stage30_quality.py` -> `stage30 quality score overall=91.52 grade=A release_decision=pass`。
- 为避免本地 `.env` 的 Redis/Semantic Cache 状态污染 SSE timing 测试，`tests/test_agent_stream_api.py` 已在相关测试中显式关闭外部缓存；stream cache lookup 已改为 50ms fail-open。
- 当前仍未 `git add`、未 commit、未 tag、未 push、未 PR。

## Follow-up：LangGraph 跨轮 Agent 可决策记忆（2026-06-22）

本次修复解决同一会话追问时 LangGraph 看不到上一轮结构化 evidence 的问题。在 RAG 链路中，它位于 `initialize_state()` 与 `planner_node` 之间，以及 `generate_answer_node` 生成最终引用回答时；现在做这一步，是为了让“请详细回答”这类展开追问可以由 LangGraph planner 基于上一轮 evidence 决策，而不是每轮从零开始检索。

完成内容：
- `app/services/agent/graph_state.py`：新增 `prior_sources`、`prior_citations`、`prior_answer_summary` 字段。
- `app/services/agent/graph_builder.py`：`LangGraphAgentService.query()` 在 invoke 前用同一 `thread_id` 读取最新 checkpoint，压缩并注入 prior evidence；读取失败时 fail-open。
- `app/services/agent/graph_nodes.py`：`planner_node` 将 prior evidence 传给 deterministic/LLM planner；LLM planner prompt 增加 prior answer summary 和 prior evidence 摘要；`generate_answer_node` 可在当前轮无 sources 时复用 `prior_sources` 生成回答。
- `app/services/agent/react_actions.py`：`DeterministicReActPlanner` 增加 prior evidence + 展开追问决策路径。
- 测试补充：覆盖 prior_sources + 展开追问直接回答、prior_sources + 新方向追问仍检索、prior_sources 为空行为不变、checkpoint 读取失败 fallback、prior_sources 生成回答。
- API/intent 测试同步修正：“请详细回答”不再硬编码为 `followup_transform`，保持交给 agent/tool decision。
- 静态前端测试同步当前 `phase51-followup-toolcalling-fix1` 资源版本号。

验证结果：
- `python -m pytest tests/test_intent_router.py tests/test_agent_api.py::test_agent_api_detail_followup_uses_agent_tool_decision -q` -> `5 passed`
- `python -m pytest tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py -q` -> `31 passed`
- `python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py tests/test_phase50_semantic_cache.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py -q` -> `97 passed`
- `python -m pytest -q` -> `1128 passed, 1 skipped in 180.29s`
- `python scripts/score_stage30_quality.py` -> `stage30 quality score overall=91.52 grade=A release_decision=pass`

边界：
- 未修改 `app/core/config.py`。
- 默认配置保持不变。
- 未新增外部数据源。
- 当前仍未 `git add`、未 commit、未 tag、未 push、未 PR，等待用户人工核验。

## Submission Boundary

阶段 51 已完成开发、测试、普通文档和 Obsidian 草稿收尾。用户已在 2026-06-22 明确授权进入提交、tag、GitHub 推送与合并流程。

- 允许提交阶段 51 整体开发工作。
- 允许创建 `phase-51-complete` tag。
- 允许推送当前分支和 tag 到 GitHub。
- 允许创建 PR 并合并到 `main`。
- 仍不得提交 `.env`、`.env.prod`、数据库密码、JWT secret、API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought 或受限全文。

# 阶段 51 Findings：性能评测与全周期架构演进对照

## 启动核对

- 已阅读：`AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage51_evaluation_plan.md`、`task_plan.md`、`findings.md`、`progress.md`。
- Planning with Files catchup 脚本未在 `.claude` 路径找到；已手动完整读取规划文件并校准。
- 起点：`main -> a32fd804 Merge phase 50 LangGraph Redis and pgvector`。
- `phase-50-complete` tag 存在，指向 `b1dc0ff7 Complete phase 50 LangGraph Redis and pgvector`，且是 `main` 的祖先。
- 已从 `main` 创建并切换到 `codex/phase-51-performance-evaluation`。
- 可见未跟踪文件：`docs/stage51_evaluation_plan.md`，这是阶段 51 计划文件，已保留并纳入本阶段。

## Phase 37 评测数据理解

- 阶段 37 的真实对照文件是 `data/evaluation/stage37_tool_calling_vs_react_real_results.csv`。
- 评测集为 8 题，覆盖 single-hop definition、comparison、multi-dimensional、bilingual terms、follow-up、evidence insufficient、off-topic refusal、multi-hop retrieval。
- 阶段 51 复用这 8 题，便于把 Tool Calling、ReAct、Brain 直通和 LangGraph 放到同一问题集上比较。
- 阶段 37 的架构结论：Tool Calling 是轻量工具运行时，不是 LangGraph/checkpointing；它限制单轮只执行一个只读 RAG search，并没有 citation repair 和收敛策略。

## Phase 50 架构理解

### LangGraph Agent

- `mode="langgraph_agent"` 是显式模式，不删除 `react_agent`、`tool_calling_agent` 或旧 `default`。
- LangGraph 只做编排；检索、图片、表格、上传图分析、引用式回答仍复用 `AgentToolbox`。
- Runtime-only 对象通过 `ContextVar` 注入，避免 Redis checkpoint 保存 DB session、callback 或 provider 对象。
- Phase 51 已把 `route_query_node` 改名为 `planner_node`，因为该节点职责已经是“规划下一步 action”。

### Planner

- Phase 50 已引入 optional fast planner：配置 `PLANNER_CHAT_MODEL_*` 时，LangGraph planner 用快模型输出 JSON action；未配置或异常时 fallback 到 `DeterministicReActPlanner`。
- 最终 `answer_with_citations` 仍使用主 `chat_model_provider`，不让 planner 生成最终答案。
- latency trace 中已有 `planner_model` 与 `planner_latency_ms`，阶段 51 CSV 已采集这些字段。

### pgvector HNSW

- 阶段 50 最终默认意图是 HNSW-first：PostgreSQL + pgvector + 2048 维 GLM embedding 可用时走 `pgvector_hnsw`，否则 fallback 到 FAISS/numpy。
- `embedding_json` 仍是历史序列化表示；`embedding_vector Vector(2048)` 与 HNSW index 是数据库检索表示。
- 因 pgvector `vector` HNSW 维度限制，阶段 50 使用 `halfvec(2048)` 表达式索引。
- 阶段 51 未修改默认值，只用评测脚本显式临时切换 pgvector vs FAISS 对照。

### Semantic Cache

- Semantic Cache 是 answer-level cache，不是 query embedding cache。
- 默认配置不因阶段 51 改动；评测脚本显式控制 cache 场景，避免污染默认链路。
- cache payload 必须保持脱敏，不写 raw provider response。
- 阶段 51 记录了 cache miss/hit 的端到端 latency、hit rate 和 `semantic_cache_hit`。

## Brain 直通路径理解

- `brain_baseline` 走 `/chat` 等价路径，表示无 Agent 循环、无 tool call 编排的 Brain 直通基线。
- 它用于量化 Agent 编排开销：ReAct/Tool Calling/LangGraph 相对 `/chat` 增加了多少延迟，换来了哪些可观测性、工具控制和可扩展性。
- 阶段 51 不改 BrainService 默认链路，只作为评测对照。

## 既有演进对照表理解

- `G:\Codex\program\关键提升\agent_evolution_comparison.md` 是长期架构对照表，阶段 51 已扩展为全周期表。
- 新列覆盖 Brain 直通、MIMO ReAct、Flash+Pro、Tool Calling、LG 规则路由、LG+Planner、Cache 命中。
- 关键新增维度：路由架构类型、向量检索后端、子链路延迟、Semantic Cache 收益。

## 关键决策

- 评测脚本默认 dry-run，真实 provider 必须显式 `--execute`。
- 六种配置通过显式 `mode`、`/chat` 路径和脚本内部临时开关切换，不改 `app/core/config.py` 默认值。
- 真实 provider、Redis、PostgreSQL 或 pgvector 不可用时记录 skipped/error，不伪造成 completed。
- CSV 记录数值指标、配置名、脱敏错误摘要和安全质量指标，不保存供应商原始响应、完整 answer raw body、hidden thought 或受限全文。
- 阶段开发完成后不执行 `git add`、commit、tag、push 或 PR。

## Phase 0 Findings：`planner_node` 重命名

- 代码层重命名完成：`app/services/agent/graph_nodes.py::planner_node` 取代旧函数名。
- 图结构同步完成：`build_langgraph_agent_graph()` 的节点名从 `"route"` 改为 `"planner"`，entry point 与 search/table/figure 回边同步指向 `"planner"`。
- 保留 `route_after_planner()`：该函数表达 planner 输出后的条件边选择，不是被重命名的现行 LangGraph 节点。
- 行为保持不变：图像上传优先 `analyze_user_image`、表格问题优先 `search_tables`、有证据后 `answer_with_citations`、planner provider 异常 fallback deterministic。
- 验证：聚焦测试 `21 passed`；全量 pytest 最终通过。

## Phase 1 Findings：评测脚本 dry-run

- 新增 `scripts/evaluate_phase51_performance.py`，默认 dry-run，不调用真实 provider、Redis 或 PostgreSQL。
- 评测集复用 Phase 37 八类问题。
- 配置矩阵覆盖 Brain baseline、ReAct、Tool Calling、LangGraph deterministic、LangGraph flash planner、LangGraph FAISS fallback、Semantic Cache hit。
- CSV 输出：
  - `data/evaluation/phase51_performance_results.csv`
  - `data/evaluation/phase51_performance_summary.csv`
- 字段包含端到端延迟、planner latency、聚合 search latency、vector backend、planner model、tool/iteration/citation/source 数、cache hit、与 ReAct 的 refusal/top-source 对齐。
- 安全边界：错误只写 `safe_error_summary`；脚本不写 raw provider response、API key、Bearer token、`reasoning_content` 或受限全文。
- dry-run 结果：`rows=56 summary=7`。
- 验证：新增测试 `2 passed`；补跑 LangGraph 相关测试合计 `11 passed`。

## Phase 2 Findings：真实 Provider 评测

- 真实评测使用 `python scripts/evaluate_phase51_performance.py --execute`，读取本地 `.env`、真实数据库和 provider 配置。
- 第一次真实执行 904 秒超时，未形成完整输出。
- 为避免真实 provider 长时间评测白跑，脚本增加 checkpoint：每完成一条 outcome 即刷新 results/summary CSV。
- 第二次真实执行 1804 秒超时，但 checkpoint 已保留 53/56 行。
- 增加 `--resume` 后续跑，跳过已有 `(query_id, config_id)`，补齐到 56/56 行。
- 原始真实评测结果（Follow-up 修复前）：
  - `brain_baseline`：8/8 ok，avg final latency 34095.671 ms。
  - `react_agent`：8/8 ok，avg final latency 41928.377 ms，primary backend `pgvector_hnsw`。
  - `tool_calling_agent`：8/8 ok，avg final latency 21204.028 ms，primary backend `pgvector_hnsw`，planner label `native_tool_calls`。
  - `langgraph_deterministic`：8/8 ok，avg final latency 41214.309 ms，primary backend `pgvector_hnsw`。
  - `langgraph_flash_planner`：8/8 ok，avg final latency 47157.740 ms，primary backend `pgvector_hnsw`。
  - `langgraph_faiss_fallback`：8/8 ok，avg final latency 51098.842 ms，primary backend `faiss`。
  - `semantic_cache_hit`：8/8 ok，avg final latency 1.000 ms，cache hits 8。
- CSV 敏感字段扫描未命中：`api key`、`bearer`、`authorization`、`raw_response`、`reasoning_content`。
- 当前真实评测主要记录 vector backend 与端到端延迟字段；FAISS vs pgvector 的质量对照目前以 top source parity 和来源数量作为轻量代理，细粒度 recall@5 仍需后续专项评测。

## Phase 3 Findings：全周期演进对照表

- 已整体更新 `G:\Codex\program\关键提升\agent_evolution_comparison.md` 为 UTF-8 清晰版全周期表。
- 扩展列覆盖 Brain 直通、MIMO ReAct、Flash+Pro、Tool Calling、LG 规则路由、LG+Planner、Cache 命中。
- 新增/补齐维度：代表路径、路由架构类型、向量检索后端、平均端到端延迟、p90/最大延迟可复算说明、成功率、工具调用、planner latency、Semantic Cache、Stage 30。
- Phase 51 真实评测摘要直接写入表中，便于和 CSV 互相校验。
- 原始子链路观察写明：`langgraph_deterministic` 使用 `pgvector_hnsw`，`langgraph_faiss_fallback` 使用 `faiss`；Follow-up 修复前平均端到端延迟分别为 41.21s 和 51.10s。
- 关键结论：Tool Calling 在本轮同题集仍有显著延迟优势；LangGraph 的主要收益是状态图、checkpoint、可观测和可演进；Semantic Cache 命中是重复问答的最大延迟收益。
- 限制说明：Phase 51 当前 FAISS vs pgvector 对照记录后端和端到端延迟，细粒度 recall@5 仍需后续专门检索评测以 source-id set overlap 进一步量化。

## Phase 4 Findings：回归验证与收尾

- 普通文档已更新：`README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-51.md`。
- Obsidian 草稿已建立：`obsidian-vault/阶段汇报/阶段 51 - 性能评测与架构演进对照/`，含索引和 Phase 0-4 小汇报。
- `obsidian-vault/阶段汇报索引.md` 已增加阶段 51 入口。
- 全量回归：`python -m pytest -q -> 1112 passed, 1 skipped in 119.05s`。
- Stage 30 质量门：`python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`。
- 当前保持未提交、未暂存、未打 tag、未 push、未创建 PR，等待用户人工核验。

## Phase 51 Follow-up Findings：LangGraph `generate_answer_node` 冗余检索修复

- 问题定位：`generate_answer_node` 原先调用 `AgentToolbox.answer_with_citations()`，该路径进入 `CitationAnswerService -> BrainService.answer()`，即使 `search_knowledge_node` 已把 `search_results` / `sources` 写入 LangGraph state，也会再次执行完整 hybrid 检索并使用更重的 Brain citation prompt。
- 修复方式：当 state 中已有 `sources` 时，`generate_answer_node` 直接复用这些 evidence，调用 `_toolbox(state).chat_model_provider.generate()` 与 `evidence_answer_messages()` 生成最终引用回答；若初稿无有效引用，则用轻量 `citation_repair_messages()` 修复引用。
- 安全/质量边界：保留 `extract_citations()` 引用抽取；新增与 Tool Calling 一致的 responsibility gate 和 topic anchor gate，避免 off-topic 问题因为已有相似 sources 被强答。若 state 中没有 sources，仍 fallback 到旧 `answer_with_citations()` 全流程。
- 评测脚本补强：`scripts/evaluate_phase51_performance.py` 新增 `--config` 过滤，可只覆盖指定配置的旧行并保留其他对照行。
- 真实评测命令：`python scripts/evaluate_phase51_performance.py --execute --config 'langgraph_deterministic,langgraph_flash_planner'`。
- 新真实评测结果：`langgraph_deterministic` 8/8 ok，平均 `34284.103 ms`；`langgraph_flash_planner` 8/8 ok，平均 `21110.586 ms`；两个配置 off-topic refusal 均恢复为 true。
- 修复前后对比：`langgraph_deterministic` `41214.309 ms -> 34284.103 ms`；`langgraph_flash_planner` `47157.740 ms -> 21110.586 ms`；对照 `tool_calling_agent` 保持 `21204.028 ms`。
- 结论：移除回答节点二次 hybrid 检索与重型 Brain citation prompt 后，LG+Planner 已接近 Tool Calling 延迟；deterministic LG 仍受个别真实 provider 长尾影响，但平均延迟下降约 6.93s。
- 回归补充：`python -m pytest -q -> 1116 passed, 1 skipped in 170.94s`；`python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`。
- 流式测试补充：本地 `.env` 开启 Redis/Semantic Cache 时，SSE timing 测试会被外部 Redis lookup 阻塞；已在测试中显式关闭外部缓存，并让 stream semantic cache lookup 以 50ms fail-open，避免缓存优化破坏首 token。

## Phase 51 Follow-up Findings：LangGraph 跨轮 evidence 记忆

- 问题定位：`LangGraphAgentService.query()` 每轮都会通过 `initialize_state()` 创建新的空 state，当前轮 `sources`、`citations`、`search_results` 都为空；即使 Redis checkpoint 已按 `thread_id=f"conversation:{conversation_id}"` 保存上一轮状态，planner 也看不到上一轮结构化 evidence。
- 修复边界：只恢复最近一轮 checkpoint 中的结构化 evidence，不做多轮堆积；恢复内容注入为 `prior_sources`、`prior_citations`、`prior_answer_summary`，不覆盖当前轮 `sources` / `citations`。
- state 控制：`prior_sources` 只保留轻量摘要字段，包括 `source_id`、`document_title`、`heading_path`、截断到约 300 字的 `content`，以及必要 source metadata；`prior_answer_summary` 截断到约 200 字，避免 checkpoint state 膨胀。
- checkpoint 读取：`load_prior_evidence_from_checkpoint()` 通过 `compiled_graph.get_state(config)` 获取同一 thread 最新 state；任何异常都 fail-open 返回空 dict，保持原行为不阻塞。
- planner 决策：deterministic planner 新增 `prior_source_count` 与 `expand_followup` 输入；当用户是“请详细回答/展开/继续”等展开类追问且 prior evidence 数量足够时，直接选择 `answer_with_citations`。LLM planner prompt 同步展示 prior answer summary 与 prior evidence 摘要，让模型也能做同类判断。
- 新方向边界：如果追问明显是新方向问题，即使存在 `prior_sources`，planner 仍选择 `search_knowledge`，避免把旧证据强行套到新问题上。
- 生成节点：`generate_answer_node` 在当前轮 `sources` 为空但 `prior_sources` 非空时，复用 prior evidence 走已修复的轻量 `evidence_answer_messages()` 生成引用回答；当前轮仍无 evidence 时才 fallback 到旧 `answer_with_citations()` 全流程。
- Tool Calling 边界：本次只改 LangGraph；Tool Calling / ReAct 不改。同步修正测试语义：“请详细回答”不再走硬编码 `followup_transform`，而是交给默认 agent/tool decision。
- 默认配置：未修改 `app/core/config.py`，未改变默认链路配置。
- 验证结果：
  - `python -m pytest tests/test_intent_router.py tests/test_agent_api.py::test_agent_api_detail_followup_uses_agent_tool_decision -q` -> `5 passed`
  - `python -m pytest tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py -q` -> `31 passed`
  - `python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py tests/test_phase50_semantic_cache.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py -q` -> `97 passed`
  - `python -m pytest -q` -> `1128 passed, 1 skipped in 180.29s`
  - `python scripts/score_stage30_quality.py` -> `overall=91.52 grade=A release_decision=pass`
- 当前状态：用户已在 2026-06-22 明确授权提交阶段 51 整体开发工作、创建 `phase-51-complete` tag、推送 GitHub、创建 PR 并合并；进入提交前安全核验与提交流程。

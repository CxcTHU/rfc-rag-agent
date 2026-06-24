# 阶段 53 任务计划：GraphRAG 知识图谱增强检索

## 总目标

在 Phase 52 已合并后的 `main` 基线上，完成阶段 53：生产/测试配置收口、Adaptive RAG 显式策略标签、领域实体关系抽取、NetworkX 知识图谱存储、图增强检索、LangGraph 集成、GraphRAG 评测与文档收尾。最终停在用户人工核验前，不执行 `git add`、commit、tag、push 或 PR。

## 当前状态

- 当前分支：`codex/phase-53-graphrag`
- 基线：`main / origin/main -> 29229270 Merge pull request #20 from CxcTHU/codex/phase-52-default-reranker-chain`
- 阶段状态：Phase 53G 完成，等待用户人工核验
- 线程标题：已设置为“阶段53-GraphRAG知识图谱增强检索”

## 安全边界

- 保留 reranker stash/分支，不触碰 reranker 工作。
- 不提交、不打 tag、不 push、不创建 PR，直到用户人工核验并明确授权。
- 不把 `.env`、`.env.prod`、数据库密码、JWT secret、API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk、受限全文或长期用户画像写入 Git/CSV/文档/测试/Obsidian。
- 真实 API 评测必须显式 `--execute`，默认 dry-run / deterministic。
- 每个小 Phase 开始前重读 `task_plan.md`、`findings.md`、`progress.md`；完成后先自验收，再更新三份规划文件。

## 子阶段

### Phase 53A：Prod/Test 配置收口

状态：complete

目标：

- 将生产 planner 配置收口到实际 LLM provider，使生产环境默认走 LLM planner。
- 确认测试 deterministic fixture 覆盖所有 planner 调用点，测试仍走 deterministic 路径。
- 运行最小验收和全量 pytest。

验收：

- `.env.example` 中 planner provider/model 显式收口为 `openai-compatible` / `deepseek-v4-flash`，真实 key/base URL 仍为空占位。
- `docker-compose.prod.yml` 要求 `.env.prod` 显式提供 `PLANNER_CHAT_MODEL_*`，避免生产静默回退 deterministic planner。
- `tests/conftest.py` 清空 planner 和 vision provider 环境变量，测试继续走 deterministic / local 路径。
- focused tests：`53 passed in 50.87s`。
- prod compose placeholder config：passed。
- 全量 `python -m pytest -q`：`1207 passed, 1 skipped, 1 warning in 227.16s`。

### Phase 53B：Adaptive RAG 显式包装

状态：complete

目标：在 planner 层新增 `AdaptiveRetrievalStrategy` 标签体系，将现有 planner 路由包装为显式检索策略选择，并在 `latency_trace` 暴露 `retrieval_strategy`。

验收：

- 新增 `app/services/agent/adaptive_retrieval.py`，集中定义 `AdaptiveRetrievalStrategy` 与 action 映射。
- `LatencyTrace` 默认含 `retrieval_strategy=none`。
- ReAct 与 LangGraph planner 选出 action 后写入 `retrieval_strategy`，不改变 `next_action` 或工具顺序。
- prior evidence 直接回答标记为 `answer_from_prior_evidence`。
- 新增 `docs/stage53_adaptive_rag_graphrag.md`。
- focused tests：`36 passed in 5.22s`。

### Phase 53C：领域实体关系 Schema + LLM 抽取

状态：complete

目标：定义 RFC/建筑规范领域实体与关系 schema，实现 LLM-based 三元组抽取器和批量抽取脚本，先支持 100 条 chunk 采样。

验收：

- 实体类型：Standard, Material, Parameter, Value, Organization, Method。
- 关系类型：standard_defines, standard_references, material_has_property, parameter_range, applies_to。
- 默认 dry-run / deterministic，不让真实 API 进入 CI。
- 抽取结果 JSON 不保存完整 chunk 或原始 provider 响应。
- 新增 `app/services/graphrag/schema.py` 与 `app/services/graphrag/extractor.py`。
- 新增 `scripts/extract_phase53_graphrag_triples.py`，默认 deterministic，`--execute` 才调用真实 chat model。
- focused tests：`40 passed in 5.09s`。

### Phase 53D：知识图谱存储

状态：complete

目标：使用 NetworkX 构建、持久化、加载内存知识图谱，并输出图统计。

验收：

- 节点含 type、chunk_ids。
- 边含 type、source_chunk_id。
- JSON 持久化和加载可重复。
- 图统计脚本输出节点数、边数、连通分量、度分布。
- 新增 `app/services/graphrag/graph_store.py` 与 `scripts/build_phase53_graphrag_graph.py`。
- 新增 `networkx>=3.4.0` 项目依赖，`.venv` 已安装 `networkx-3.6.1`。
- focused tests：`43 passed in 5.43s`。

### Phase 53E：图增强检索

状态：complete

目标：实现查询实体提取、1-2 hop 图遍历、关联 chunk 收集、向量检索 + 图检索融合，并支持 fail-open。

验收：

- 图不可用时回退纯向量/既有 hybrid 检索。
- 去重、合并、rerank 路径有测试覆盖。
- latency trace 记录图检索摘要字段。
- 新增 `app/services/graphrag/graph_search.py`。
- `LatencyTrace` 新增 graph search 摘要字段。
- focused tests：`47 passed in 6.24s`。

### Phase 53F：LangGraph 集成

状态：complete

目标：新增 `search_graph_knowledge` 工具/节点，planner 可为跨文档关联和标准引用链问题路由到图检索。

验收：

- LangGraph state / nodes / builder 测试通过。
- SSE/API 响应契约不破坏。
- graph trace 字段可见且脱敏。
- 新增 `search_graph_knowledge` ReAct action、AgentToolbox 工具、LangGraph 节点和路由。
- Adaptive RAG 新增 `graph_enhanced_search` 策略标签。
- API/SSE focused tests：`99 passed in 59.97s`。

### Phase 53G：评测与文档收尾

状态：complete

目标：构建 30-50 条 GraphRAG 评测集，对比 baseline 与 graph-enhanced，输出 CSV、ablation 和 phase review。

验收：

- focused tests 通过。
- 全量 `python -m pytest -q` 通过。
- `python scripts/score_stage30_quality.py` 仍为 A / pass。
- `git diff --check` 无 whitespace error。
- 同步 `README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-53.md`。
- 新增 30 条 GraphRAG dry-run ablation 评测集与 CSV 输出。
- focused/API/SSE：`108 passed in 65.01s`。
- 全量 pytest：`1226 passed, 1 skipped, 1 warning in 237.07s`。
- Stage 30：`overall=91.52 grade=A release_decision=pass`。
- `git diff --check` passed；仅有 CRLF conversion warnings。

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| `docs/stage53_graphrag_prompt.md` not found in current HEAD | Initial read by user path | Located blob `557f438744e2d1b0f4c842d8ba5b6ca9c849d704` via `git rev-list --objects --all` and restored as a tracked planning doc |
| `git fetch --all --prune` failed with connection reset | Remote refresh | Non-blocking because `main...origin/main` was already clean and Phase 52 merge was present locally |
| Planning skill session-catchup could not run because `python` was not in PATH | Session recovery | Non-blocking; root planning files were read directly and worktree was clean |

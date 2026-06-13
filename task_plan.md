# 阶段 33 任务计划：RAG 链路性能优化与 Embedding 迁移验证

## 目标

在阶段 32「ReAct Agent 决策升级与工具调用实时可视化」已经完成、打 `phase-32-complete` tag 并合并到 `main` 的基础上，进入阶段 33：围绕真实暴露的 RAG 性能瓶颈做核心链路优化，并对 GLM-Embedding-3 迁移后的检索质量做诚实验证。

目标分支：`codex/phase-33-rag-performance-embedding-validation`

本阶段不是继续扩 Agent 花活，也不是直接替换默认模型。核心原则是：先量化慢在哪里，再优化确定浪费；保留旧 Jina 索引作为回滚和质量对照；DeepSeek 只作为 benchmark candidate，不直接替换默认 MIMO；真实 provider 只做显式 smoke 或 benchmark，不进入 CI 或本地全量测试前提。

## 背景

阶段 31 引入 FAISS `IndexFlatIP` 与父子块检索，阶段 32 引入 `react_agent` 与实时 SSE 可观测。联调后发现真实 ReAct 查询约 33-44 秒，同时存在一个确定浪费点：

```text
VectorIndexCache._ensure_loaded()
-> 先从 SQLite 读取全部 chunk_embeddings
-> 反序列化 12,731 x 2048 维向量
-> 构建 numpy normalized matrix，约 208MB
-> 再加载 FAISS index
-> 搜索实际走 FAISS，numpy matrix 在主路径中未参与搜索
```

GLM-Embedding-3 维度为 2048，不是 2028。相比 Jina v3 的 1024 维，SQLite 反序列化、numpy matrix、FAISS index 体积和冷启动成本都会放大。因此阶段 33 应优先处理 FAISS 可用时的冗余 matrix 构建，并补上 GLM vs Jina 的迁移质量对照。

## 当前基线

```text
main / origin/main -> 608a6e9 Merge phase 32 react agent observability
phase-32-complete -> f259f97 Complete phase 32 react agent observability
当前阶段分支 -> codex/phase-33-rag-performance-embedding-validation
```

阶段 32 验证基线：

```text
阶段 32 聚焦测试：106 passed
全量 pytest：629 passed, 1 warning
阶段 30 score：overall=83.17 grade=B release_decision=review_required
Browser smoke：desktop 与 390x844 mobile 均通过，console errors=0
```

## Phase 顺序

### Phase 0：启动校准与规划落盘

状态：已完成。

本 Phase 解决的问题：确认阶段 33 从阶段 32 已合并后的正确基线出发，避免沿用阶段 32 人工核验前的旧描述。

RAG 链路位置：版本基线、协作边界与规划层，不改运行链路。

为什么现在做：性能优化会碰到检索缓存、FAISS、provider benchmark 和评测脚本，必须先锁定基线、分支和不提交边界。

- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 运行 `git status -sb`、`git log --oneline -5`。
- 确认 `phase-32-complete` 存在并指向阶段 32 功能提交。
- 确认 `phase-32-complete` 已合并到 `main`，不移动任何已有阶段 tag。
- 从最新 `main` 创建或切换到目标分支。
- 将三份 planning 文件改写为阶段 33 规划。

验证方式：

```text
git status -sb
git log --oneline -5 --decorate
git merge-base --is-ancestor phase-32-complete main
```

### Phase 1：阶段 33 设计文档与性能观测口径

状态：已完成。

本 Phase 解决的问题：先定义本阶段优化目标、指标、边界和验收口径，避免“感觉变快”或“换模型试试”式开发。

RAG 链路位置：设计文档、性能观测与评测口径层。

为什么现在做：后续会改 VectorIndexCache、embedding cache、latency trace 和 benchmark，如果没有统一指标，就无法判断收益和退化。

- 新增 `docs/stage33_rag_performance_embedding_validation.md`。
- 明确 P0-P4 范围：FAISS-only 冷启动、query embedding cache、latency trace、GLM vs Jina 质量验证、DeepSeek benchmark。
- 明确不做事项：不删旧 Jina、不直接替换 MIMO、不新增外部数据源、不做写入型工具、不把真实 API 变成 CI 前提。
- 固定 before/after 指标：cold_start_ms、first_query_ms、query_embedding_latency_ms、faiss_search_latency_ms、rerank_latency_ms、planner_latency_ms、answer_latency_ms、time_to_first_token_ms、time_to_final_ms、memory estimate。
- 明确安全边界：不记录 hidden thought、reasoning_content、raw provider response、API key、Bearer token、受限全文。
- 新增 `tests/test_stage33_design.py`，把 2048 维、FAISS-only/fallback、query latency trace、安全字段和 provider benchmark 边界固化为回归测试。

验证方式：

```text
python -m pytest tests\test_stage33_design.py -q
2 passed
```

### Phase 2：FAISS 可用时跳过 numpy matrix 构建

状态：已完成。

本 Phase 解决的问题：消除阶段 31/32 后真实存在的冷启动冗余成本。

RAG 链路位置：`VectorIndexCache.search()` 的向量检索执行层，位于 `/search/vector`、hybrid search、Brain、`/chat`、`/agent/query` 和 `react_agent` 的共同底座。

为什么现在做：这是确定存在、风险低、收益可量化的浪费点；它不改变 FAISS 排序语义，只改变加载路径。

- 调整 `app/services/retrieval/vector_cache.py`。
- 如果完整 FAISS index 和 ids metadata 可用，优先只加载 FAISS index + ids 映射所需的 chunk metadata。
- 跳过 SQLite -> embedding_json -> numpy matrix 的全量反序列化。
- 如果 FAISS 缺失、损坏、provider/model/dimension 不匹配、ids 缺失或不完整，则 fallback 到 SQLite/numpy。
- 保留纯 numpy fallback 与纯 Python cosine 对照测试。
- 记录或暴露缓存加载模式：`faiss_only` / `numpy_fallback` / `empty`。
- 新增 `scripts/benchmark_stage33_rag_latency.py`，默认支持 deterministic 离线 benchmark，显式配置后可测真实 GLM-Embedding-3 2048 维链路。

验证方式：

```text
python -m pytest tests\test_vector_cache_faiss.py tests\test_hybrid_search.py tests\test_vector_search.py -q
python -m pytest tests\test_vector_cache_faiss.py tests\test_vector_cache.py tests\test_vector_search.py -q
13 passed

python -m py_compile scripts\benchmark_stage33_rag_latency.py
python scripts\benchmark_stage33_rag_latency.py --provider deterministic --dimension 64 --limit 1 --output data\evaluation\stage33_rag_latency_benchmark.csv
```

### Phase 3：query embedding cache

状态：已完成。

本 Phase 解决的问题：避免同一问题在 ReAct、多次刷新、benchmark 或重复查询中反复调用真实 embedding provider。

RAG 链路位置：query embedding 层，位于 `VectorSearchService` 和 hybrid/vector search 入口。

为什么现在做：GLM-Embedding-3 是 2048 维且真实 provider 有网络延迟；query embedding cache 能降低重复查询延迟和供应商调用次数，但不改变文档索引。

- 为 query embedding 增加进程内缓存或轻量可清理缓存。
- cache key 至少包含 provider、model、dimension、normalized query text。
- 设置容量上限或 TTL，避免无限增长。
- 只缓存 query embedding，不缓存文档写入型 embedding，不改变 `chunk_embeddings`。
- 提供关闭或清理入口，便于测试和 benchmark。
- 确认 deterministic 测试不依赖真实 API。
- 新增 `app/services/retrieval/query_embedding_cache.py`，并在 `VectorSearchService` query embedding 层接入。

验证方式：

```text
python -m pytest tests\test_query_embedding_cache.py tests\test_embedding_provider.py tests\test_vector_search.py -q
28 passed
```

### Phase 4：RAG/ReAct latency trace

状态：已完成。

本 Phase 解决的问题：把 33-44 秒端到端耗时拆开，判断慢在 embedding、FAISS、rerank、planner、answer generation 还是 SSE 首 token。

RAG 链路位置：检索、Agent 编排、回答生成和 SSE 输出的观测层。

为什么现在做：没有分段耗时就无法判断 MIMO 是否真是主因，也无法客观比较 DeepSeek。

- 为 `/agent/query` 和 `/agent/query/stream` 的 `react_agent` 路径增加安全 latency trace。
- 尽量复用到 default / old agentic 路径，便于对照。
- 至少记录：
  - `query_embedding_latency_ms`
  - `faiss_search_latency_ms` 或 `vector_search_latency_ms`
  - `rerank_latency_ms`
  - `planner_latency_ms`
  - `answer_latency_ms`
  - `tool_latency_ms`
  - `time_to_first_token_ms`
  - `time_to_final_ms`
  - `iteration_count`
  - `tool_call_count`
- metadata 可携带摘要级 timing；前端可暂不新增复杂 UI。
- 错误和 refusal 路径也要记录总耗时并安全收敛。
- 新增 `app/services/observability/latency_trace.py`，通过 request-local trace 汇总检索、rerank、planner、tool、answer 和 SSE 首 token。
- `AgentQueryResponse.latency_trace` 与会话 metadata 同步保留安全耗时字段。

验证方式：

```text
python -m pytest tests\test_react_latency_trace.py tests\test_agent_api.py tests\test_react_stream_events.py -q
python -m pytest tests\test_react_latency_trace.py tests\test_agent_api.py tests\test_react_stream_events.py tests\test_agent_stream_api.py -q
31 passed
```

### Phase 5：GLM-Embedding-3 vs Jina 检索质量迁移验证

状态：已完成。

本 Phase 解决的问题：确认从 Jina v3 1024 维迁移到 GLM-Embedding-3 2048 维后，检索质量没有静默退化。

RAG 链路位置：评测层与向量检索质量校准层。

为什么现在做：阶段 30/29 的质量分数仍主要基于旧 Jina 缓存；迁移 provider 后必须诚实复核，而不是假设新模型更好。

- 不删除旧 Jina FAISS 文件：
  - `data/faiss/jina_jina-embeddings-v3_dim1024.index`
  - `data/faiss/jina_jina-embeddings-v3_dim1024_ids.json`
- 保留 GLM FAISS 文件：
  - `data/faiss/paratera_GLM-Embedding-3_dim2048.index`
  - `data/faiss/paratera_GLM-Embedding-3_dim2048_ids.json`
- 新增 `scripts/evaluate_stage33_embedding_migration.py`。
- 复用阶段 29/30 题集或 fixture，对比 Jina 与 GLM：
  - precision@k
  - hit@k
  - source/citation 覆盖
  - unsupported/refusal 边界
  - 查询耗时
- 输出 CSV 与摘要文档。
- 缺少真实 index 或 API 时，不伪造成通过；自动测试使用小型 fixture。
- 新增 `scripts/evaluate_stage33_embedding_migration.py`，默认 dry-run，显式 `--execute-real` 才调用真实 provider。
- 本地真实评测结果：GLM candidate completed；Jina baseline 因本地缺少 provider 配置 skipped。

验证方式：

```text
python -m pytest tests\test_stage33_embedding_validation.py -q
2 passed

python scripts\evaluate_stage33_embedding_migration.py
dry_run_only

python scripts\evaluate_stage33_embedding_migration.py --execute-real
glm_candidate: status=completed p@5=0.867 coverage=0.637 latency=1469.98ms decision=review_for_silent_regression
jina_baseline: status=skipped p@5=0.000 coverage=0.000 latency=0.00ms decision=skipped_missing_real_config
```

### Phase 6：MIMO baseline 与 DeepSeek chat provider benchmark

状态：已完成。

本 Phase 解决的问题：用数据判断 DeepSeek 是否值得作为后续 chat provider 候选，而不是直接替换默认 MIMO。

RAG 链路位置：回答生成 provider benchmark 层，不改变默认业务链路。

为什么现在做：当前 33-44 秒不一定全来自 MIMO；必须先把 provider 放进同一批问题和同一套指标比较。

- 新增 `scripts/benchmark_stage33_chat_providers.py`。
- MIMO 作为 baseline，DeepSeek chat 作为 candidate。
- 可选 DeepSeek reasoner smoke，但必须防止 `reasoning_content` 泄露到前端、日志、CSV、文档。
- 指标：
  - `time_to_first_token`
  - `time_to_final`
  - `planner_latency`
  - `answer_latency`
  - `token_count`
  - `tokens_per_second`
  - citation 是否稳定
  - refusal 是否一致
  - 是否泄露 reasoning_content
- 只输出 benchmark 结论和切换建议，不修改默认模型。
- 新增 `scripts/benchmark_stage33_chat_providers.py`，默认 dry-run，显式 `--execute-real` 才调用真实 chat provider。
- 本地真实 benchmark：MIMO baseline completed；DeepSeek candidate 因缺少本地配置 skipped。

验证方式：

```text
python -m pytest tests\test_stage33_provider_benchmark.py -q
2 passed

python scripts\benchmark_stage33_chat_providers.py --dry-run
python scripts\benchmark_stage33_chat_providers.py
dry_run rows written

python scripts\benchmark_stage33_chat_providers.py --execute-real
mimo_baseline/citation_case: status=completed ttft=6265.58ms total=6952.99ms tokens_per_second=1.58 leak=false
mimo_baseline/refusal_case: status=completed ttft=2909.34ms total=6800.78ms tokens_per_second=9.26 leak=false
deepseek_candidate: skipped_missing_config
```

### Phase 7：文档、Obsidian 与阶段验收准备

状态：已完成。

本 Phase 解决的问题：把性能优化、迁移验证、benchmark 结论和边界沉淀为项目文档，停在用户人工核验前。

RAG 链路位置：项目交接、知识沉淀与发布前核验层。

为什么现在做：阶段 33 的价值在于“有证据的性能优化和迁移判断”，必须把 before/after 与质量结论写清楚。

- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 按需更新 `AGENT.MD`，尤其是阶段 33 交接状态、性能规则、provider benchmark 边界。
- 新增 `docs/phase_reviews/phase-33.md` 人工核验草稿。
- 更新 Obsidian 阶段页、阶段汇报目录、阶段索引、相关知识点。
- 运行阶段 33 聚焦测试、全量 pytest、`scripts/score_stage30_quality.py`。
- 浏览器 smoke：Agent 查询、折叠思考过程、最终答案、无横向溢出、console errors=0。
- 最终停在用户人工核验前，不执行 `git add`、commit、tag、push 或 PR。

验证方式：

```text
python -m pytest tests\test_stage33_design.py tests\test_vector_cache_faiss.py tests\test_query_embedding_cache.py tests\test_react_latency_trace.py tests\test_stage33_embedding_validation.py tests\test_stage33_provider_benchmark.py -q
16 passed

python -m pytest -q
643 passed

python scripts\score_stage30_quality.py
stage30 quality score overall=83.17 grade=B release_decision=review_required

browser smoke:
desktop: Agent query final answer present, collapsible thought panel present, horizontal overflow=false, console errors=0
390x844 mobile: Agent query final answer present, collapsible thought panel present, horizontal overflow=false, console errors=0
```

## 完成标准

- FAISS 完整可用时，`VectorIndexCache` 不再构建无用 numpy matrix。
- FAISS 不可用或不匹配时，SQLite/numpy fallback 仍正常。
- 同一 query 的 embedding 可缓存，重复查询不会重复调用真实 embedding provider。
- RAG/ReAct 链路能输出安全的 latency trace。
- GLM-Embedding-3 vs Jina 检索质量有对比结果，确认是否存在静默退化。
- DeepSeek 只作为 benchmark provider，有对比报告，不直接替换默认 MIMO。
- `default`、`agentic`、`react_agent` 核心 API 不破坏。
- `/chat` 默认链路不破坏。
- `/agent/query/stream` 保持 `token`、`metadata`、`done`、`error` 兼容，并继续支持阶段 32 新事件。
- 全量 pytest 通过。
- 阶段 30 score 保持 `>= 83.17`。
- 浏览器冒烟通过：Agent 查询、折叠思考过程、最终答案、无横向溢出、console errors=0。
- 不写入 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content` 或受限全文。
- 最终停在用户人工核验前：不 `git add`、不 commit、不创建 `phase-33-complete` tag、不 push、不创建 PR。

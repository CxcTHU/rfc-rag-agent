# 阶段 33 进度日志：RAG 链路性能优化与 Embedding 迁移验证

## 当前状态

- 当前阶段：阶段 33 开发、测试、普通文档和 Obsidian 草稿已完成，等待用户人工核验。
- 当前本地分支：`codex/phase-33-rag-performance-embedding-validation`。
- 当前 Git 基线：`main / origin/main -> 608a6e9 Merge phase 32 react agent observability`。
- 阶段 tag：`phase-32-complete -> f259f97 Complete phase 32 react agent observability`。
- 当前提交边界：已完成阶段 33 收尾，但不执行 `git add`、commit、tag、push 或 PR，等待用户人工核验。

## 阶段 32 验收基线

```text
阶段 32 功能提交：f259f97 Complete phase 32 react agent observability
阶段 32 merge commit：608a6e9 Merge phase 32 react agent observability
phase-32-complete -> f259f97
```

阶段 32 最终验证：

```text
阶段 32 聚焦测试：106 passed
全量测试：629 passed, 1 warning
阶段 30 评分：overall=83.17 grade=B release_decision=review_required
API smoke：/health, /quality-report, /chat, /agent/query, /agent/query/stream, /search/hybrid 均 200
Browser smoke：desktop 与 390x844 mobile 均通过，console errors=0
```

## 本次规划操作记录

已完成：

- 已读取 planning-with-files 技能规则。
- 已运行 `git status -sb` 与 `git log --oneline -5 --decorate`。
- 已确认当前 `main` 与 `origin/main` 同步。
- 已确认阶段 32 已合并到 `main`，`phase-32-complete` 指向阶段 32 功能提交。
- 已读取根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 已读取 `AGENT.MD`、`README.md`、`docs/architecture.md` 的关键开头与阶段状态。
- 已检索 `docs/progress.md`、`docs/data_sources.md`、`docs/architecture.md` 中与 FAISS、VectorIndexCache、Jina、GLM、DeepSeek、性能和 embedding 迁移相关的内容。
- 已读取 `obsidian-vault/模板/goal prompt.md`，确认 goal prompt 不超过 4000 字符的模板要求。
- 已创建并切换到 `codex/phase-33-rag-performance-embedding-validation`。
- 已将 `task_plan.md`、`findings.md`、`progress.md` 改写为阶段 33 规划。

未执行：

- 未开始代码实现。
- 未运行阶段 33 测试。
- 未修改普通文档、Obsidian 或业务代码。
- 未执行 `git add`、commit、tag、push 或 PR。

## 阶段 33 目标概述

阶段 33 要完成五条主线：

1. **FAISS 冷启动优化**：完整 FAISS 可用时跳过无用 numpy matrix 构建。
2. **query embedding cache**：同一问题重复查询不重复调用真实 embedding provider。
3. **RAG/ReAct latency trace**：把 33-44 秒端到端耗时拆成 embedding、FAISS、rerank、planner、answer、SSE 首 token 等指标。
4. **GLM-Embedding-3 vs Jina 迁移验证**：用阶段 29/30 题集或 fixture 对比新旧 embedding 检索质量。
5. **DeepSeek benchmark**：DeepSeek 作为 chat provider candidate，不直接替换默认 MIMO。

## 关键执行边界

- 不删除旧 Jina embedding/index。
- 不直接替换默认 MIMO provider。
- 不引入新的外部数据源。
- 不做写入型 Agent 工具。
- 不做部署/运维。
- 不扩大成完整质量闭环。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不写入 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content` 或受限全文。
- 阶段完成后停在用户人工核验前，不提交、不 tag、不 push、不建 PR。

## Phase 日志

### Phase 0：启动校准与规划落盘

状态：已完成。

本 Phase 解决的问题：确认阶段 33 的正确起点，并建立本阶段任务书、发现记录和进度日志。

RAG 链路位置：版本基线和协作边界，不改运行链路。

为什么现在做：性能优化会触及检索缓存、FAISS、provider benchmark 和评测脚本，必须先确认阶段 32 已完成合并并固定回归基线。

已完成：

- 已读取项目规则和阶段 32/31/30 关键状态。
- 已确认 `phase-32-complete -> f259f97`，`main -> 608a6e9`。
- 已创建阶段 33 分支。
- 已改写三份 Planning with Files 文件。

验证状态：

```text
git status -sb: 当前分支为 codex/phase-33-rag-performance-embedding-validation
git log --oneline -5 --decorate: main 顶部为 608a6e9，phase-32-complete 指向 f259f97
```

### Phase 1：阶段 33 设计文档与性能观测口径

状态：已完成。

计划产物：

```text
docs/stage33_rag_performance_embedding_validation.md
tests/test_stage33_design.py
```

本 Phase 解决的问题：把性能指标、安全边界、FAISS-only/fallback 策略、query embedding cache、latency trace、GLM vs Jina 迁移验证和 DeepSeek benchmark 范围先固化下来。

RAG 链路位置：设计文档与观测口径层，不改业务运行链路。

为什么现在做：后续会同时碰缓存、provider 调用、SSE metadata 和评测脚本，如果没有固定契约，容易出现“换模型”“加指标”时越界。

已完成：

- 新增 `docs/stage33_rag_performance_embedding_validation.md`。
- 新增 `tests/test_stage33_design.py`。
- 固定 `GLM-Embedding-3` 为 2048 维。
- 固定 DeepSeek 只做 benchmark candidate，不直接替换默认 MIMO。
- 固定 latency trace 安全边界，不记录 hidden thought、`reasoning_content`、provider raw response、API key、Bearer token 或受限全文。

验证：

```text
python -m pytest tests\test_stage33_design.py -q
2 passed
```

### Phase 2：FAISS 可用时跳过 numpy matrix 构建

状态：已完成。

计划产物：

```text
app/services/retrieval/vector_cache.py
tests/test_vector_cache_faiss.py
scripts/benchmark_stage33_rag_latency.py
```

本 Phase 解决的问题：完整 FAISS 可用时，旧链路仍构建无用 numpy matrix，造成 SQLite 读取、embedding JSON 反序列化和内存浪费。

RAG 链路位置：`VectorIndexCache.search()`，是 `/search/vector`、hybrid search、Brain、`/chat`、`/agent/query` 和 `react_agent` 共用的向量检索底座。

为什么现在做：这是阶段 32 后真实性能问题里最确定的浪费点；改动只拆加载路径，不改变 FAISS 排序语义。

已完成：

- `VectorIndexCache` 先尝试完整 FAISS index。
- 完整 FAISS 可用时只加载 FAISS index 和 chunk metadata，跳过 numpy matrix。
- 新增 `load_mode`：`faiss_only` / `numpy_fallback` / `empty`。
- FAISS 缺失、不完整或 ids 与当前有效 embedding 集合不一致时 fallback。
- 新增测试覆盖 FAISS-only 不反序列化 `embedding_json`、不完整 FAISS fallback、ids 不完整 fallback。
- 新增 `scripts/benchmark_stage33_rag_latency.py`。

验证：

```text
python -m pytest tests\test_vector_cache_faiss.py tests\test_vector_cache.py tests\test_vector_search.py -q
13 passed

python -m py_compile scripts\benchmark_stage33_rag_latency.py
python scripts\benchmark_stage33_rag_latency.py --provider deterministic --dimension 64 --limit 1 --output data\evaluation\stage33_rag_latency_benchmark.csv
stage33_filling_capacity: provider=deterministic model=hash-token-v1 dim=64 load_mode=numpy_fallback query_embedding=0.05ms vector_search=558.45ms total=558.51ms results=5
```

### Phase 3：query embedding cache

状态：已完成。

计划产物：

```text
app/services/retrieval/query_embedding_cache.py 或等价本地模块
tests/test_query_embedding_cache.py
```

本 Phase 解决的问题：同一 query 在 ReAct、多次刷新或 benchmark 中重复触发真实 embedding provider。

RAG 链路位置：query embedding 层，位于 `VectorSearchService.search()` 中调用 `index_cache.search()` 之前。

为什么现在做：GLM-Embedding-3 query embedding 是真实网络调用，重复 query 适合缓存；但文档索引不能被缓存策略污染。

已完成：

- 新增 `QueryEmbeddingCache`，支持 TTL、容量上限和 LRU 淘汰。
- cache key 包含 provider、model_name、dimension、normalized query text。
- `VectorSearchService` 使用 query cache 调用 `embed_query()`。
- 测试覆盖重复 query 命中、provider/model/dimension 隔离、容量淘汰和 query 规范化。

验证：

```text
python -m pytest tests\test_query_embedding_cache.py tests\test_vector_search.py tests\test_embedding_provider.py -q
28 passed
```

### Phase 4：RAG/ReAct latency trace

状态：已完成。

计划产物：

```text
app/services/agent/react_service.py
app/api/agent.py
tests/test_react_latency_trace.py
tests/test_react_stream_events.py
```

本 Phase 解决的问题：把端到端慢查询拆成可观察的安全耗时字段。

RAG 链路位置：vector search、FAISS/numpy search、hybrid rerank、ReAct planner、tool 调用、answer generation 和 SSE metadata。

为什么现在做：后续 GLM/Jina 和 MIMO/DeepSeek 对照需要同一套指标，不能凭感觉判断慢在哪里。

已完成：

- 新增 `LatencyTrace` request-local 聚合器。
- `VectorSearchService` 记录 query embedding 和 vector search。
- `VectorIndexCache` 记录 FAISS 或 numpy search 子路径耗时。
- `HybridSearchService` 记录 rerank，并兼容并行 vector worker。
- `ReActAgentService` 记录 planner、tool、answer、final、iteration/tool call 计数。
- `/agent/query/stream` metadata 记录 `time_to_first_token_ms`。
- `AgentQueryResponse` 和会话 metadata 新增 `latency_trace`。

验证：

```text
python -m pytest tests\test_react_latency_trace.py tests\test_agent_api.py tests\test_react_stream_events.py tests\test_agent_stream_api.py -q
31 passed
```

### Phase 5：GLM-Embedding-3 vs Jina 检索质量迁移验证

状态：已完成。

计划产物：

```text
scripts/evaluate_stage33_embedding_migration.py
data/evaluation/stage33_embedding_migration_results.csv
data/evaluation/stage33_embedding_migration_summary.csv
tests/test_stage33_embedding_validation.py
```

本 Phase 解决的问题：确认 GLM-Embedding-3 2048 维迁移后是否存在静默检索退化。

RAG 链路位置：检索质量评测层，不改变默认业务链路。

为什么现在做：阶段 30 分数和阶段 29 质量基线主要来自旧 Jina；迁移后必须诚实对照，不能默认新模型更好。

已完成：

- 新增 `scripts/evaluate_stage33_embedding_migration.py`。
- 新增 `tests/test_stage33_embedding_validation.py`。
- dry-run 输出 Jina 1024 与 GLM 2048 两个候选，作为 CI/离线安全入口。
- `--execute-real` 本地真实运行：GLM completed，Jina skipped。
- 输出 `data/evaluation/stage33_embedding_migration_results.csv` 与 `stage33_embedding_migration_summary.csv`。

验证：

```text
python -m pytest tests\test_stage33_embedding_validation.py -q
2 passed

python scripts\evaluate_stage33_embedding_migration.py
dry_run_only

python scripts\evaluate_stage33_embedding_migration.py --execute-real
glm_candidate: status=completed p@5=0.867 coverage=0.637 latency=1469.98ms decision=review_for_silent_regression
jina_baseline: status=skipped p@5=0.000 coverage=0.000 latency=0.00ms decision=skipped_missing_real_config
```

当前结论：GLM candidate 可运行，但缺少本地 Jina query provider 配置，因此真实同环境对照未完全闭合；不能声称 GLM 已证明优于或等价于 Jina，只能说当前 GLM 结果需要与阶段 29/30 Jina 历史结果人工对照。

### Phase 6：MIMO baseline 与 DeepSeek chat provider benchmark

状态：已完成。

计划产物：

```text
scripts/benchmark_stage33_chat_providers.py
data/evaluation/stage33_chat_provider_benchmark.csv
tests/test_stage33_provider_benchmark.py
```

本 Phase 解决的问题：把 DeepSeek 放在候选 benchmark 位置，而不是直接替换默认 MIMO。

RAG 链路位置：chat provider 对照层，不改变默认业务链路。

为什么现在做：latency trace 已经能拆耗时，provider 对照可以用同一指标输出候选报告。

已完成：

- 新增 `scripts/benchmark_stage33_chat_providers.py`。
- 新增 `tests/test_stage33_provider_benchmark.py`。
- dry-run 生成 MIMO baseline 与 DeepSeek candidate 行。
- `--execute-real` 本地运行：MIMO completed，DeepSeek skipped。
- 输出 `data/evaluation/stage33_chat_provider_benchmark.csv`。

验证：

```text
python -m pytest tests\test_stage33_provider_benchmark.py -q
2 passed

python scripts\benchmark_stage33_chat_providers.py
dry_run rows written

python scripts\benchmark_stage33_chat_providers.py --execute-real
mimo_baseline/citation_case: status=completed ttft=6265.58ms total=6952.99ms tokens_per_second=1.58 leak=false
mimo_baseline/refusal_case: status=completed ttft=2909.34ms total=6800.78ms tokens_per_second=9.26 leak=false
deepseek_candidate/citation_case: status=skipped
deepseek_candidate/refusal_case: status=skipped
```

当前结论：没有 DeepSeek 本地配置，不能声称 DeepSeek 优于或劣于 MIMO；阶段 33 只保留 benchmark candidate，不切默认 provider。

### Phase 7：文档、Obsidian 与阶段验收准备

状态：已完成。

计划产物：

```text
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
AGENT.MD（按需）
docs/phase_reviews/phase-33.md
obsidian-vault/阶段/阶段 33 - RAG链路性能优化与Embedding迁移验证.md
obsidian-vault/阶段汇报/阶段 33 - RAG链路性能优化与Embedding迁移验证/
```

已完成：

- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 更新 `AGENT.MD` 阶段 33 最新交接状态。
- 新增 `docs/phase_reviews/phase-33.md`。
- 新增 Obsidian 阶段页和阶段汇报索引，并更新首页、阶段索引、阶段汇报索引。
- 完成阶段 33 聚焦测试、全量 pytest、阶段 30 评分和浏览器桌面/移动端核验。

验证：

```text
python -m pytest tests\test_stage33_design.py tests\test_vector_cache_faiss.py tests\test_query_embedding_cache.py tests\test_react_latency_trace.py tests\test_stage33_embedding_validation.py tests\test_stage33_provider_benchmark.py -q
16 passed

python -m pytest -q
643 passed

python scripts\score_stage30_quality.py
stage30 quality score overall=83.17 grade=B release_decision=review_required

Browser smoke:
desktop: Agent query final answer present, collapsible thought panel present, horizontal overflow=false, console errors=0
390x844 mobile: Agent query final answer present, collapsible thought panel present, horizontal overflow=false, console errors=0
```

## 当前遗留风险与人工核验重点

- 阶段 33 入口文档已同步为最新状态，但仍需用户人工核验后才允许提交、tag 和 push。
- Phase 33 的真实 benchmark 依赖本地 `.env`、网络和 provider 状态；自动测试必须使用 deterministic 或 fixture。
- 旧 Jina 与新 GLM 的 FAISS 文件在 `data/faiss/`，该目录为 gitignored 派生产物，不能提交。
- DeepSeek reasoner 如参与 smoke，必须额外检查 `reasoning_content` 不泄露。

## 面试表达草稿

```text
阶段 33 我会把阶段 32 后暴露出来的真实慢查询做成一次可量化的 RAG core 优化。重点不是马上换模型，而是先拆清楚慢在哪里：embedding、FAISS、rerank、planner、answer generation 还是首 token。

第一个确定优化点是 VectorIndexCache：完整 FAISS 可用时，原链路还会把 12,731 条 2048 维向量从 SQLite 反序列化成约 208MB 的 numpy matrix，但搜索实际走 FAISS。阶段 33 会把它改成 FAISS-only 主路径，只有索引缺失或不匹配时才回退 numpy。

同时我会补 query embedding cache 和 latency trace，并用阶段 29/30 的题集对比 Jina 1024 维与 GLM-Embedding-3 2048 维，确认迁移没有静默退化。DeepSeek 只作为 benchmark candidate，和 MIMO baseline 用同一批指标比较，不直接替换默认 provider。
```

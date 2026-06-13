# 阶段 33 发现与关键决策

## 当前 Git 基线

阶段 32 已经完成提交、tag、合并和推送。阶段 33 的正确起点是最新 `main`：

```text
main / origin/main -> 608a6e9 Merge phase 32 react agent observability
phase-32-complete -> f259f97 Complete phase 32 react agent observability
当前阶段分支 -> codex/phase-33-rag-performance-embedding-validation
git status -sb: clean at start
```

决策：阶段 33 从阶段 32 合并后的 `main` 出发，不从阶段 32 的人工核验前描述继续。既有阶段 tag 不移动。

## 观察 1：Phase 33 应做 RAG core 性能，而不是继续扩 Agent

阶段 32 已经完成受控 ReAct、SSE 事件和前端折叠思考过程。继续做更激进的“真 LLM 自主 ReAct”会提高不确定性，而当前真实暴露的问题是端到端耗时约 33-44 秒。

关键判断：Phase 33 的主线应是 RAG core 性能优化和观测能力，而不是继续堆 Agent 能力。

面试表达：阶段 32 解决“Agent 会不会思考和可观测”，阶段 33 解决“真实链路能不能快、瓶颈能不能被量化、迁移有没有退化”。

## 观察 2：确定浪费点在 VectorIndexCache 冷启动

位置：`app/services/retrieval/vector_cache.py`。

当前结构：

```text
VectorIndexCache._ensure_loaded()
-> _load_entries_and_matrix()
   -> 从 SQLite 读取 chunk_embeddings
   -> JSON 反序列化 embedding
   -> 构建 numpy matrix
-> normalize_matrix()
-> _load_faiss_index_if_available()
-> search() 中如果 _faiss_index 不为空，走 FAISS
```

问题：FAISS 可用时，numpy matrix 不参与主搜索，却仍承担了全量 SQLite 读取、JSON 反序列化和内存占用成本。

规模估算：

```text
12,731 x 2048 x 8 bytes ~= 208MB float64 numpy matrix
```

如果考虑 JSON 解析临时对象和 Python list，中间峰值还会更高。

关键决策：Phase 33 P0 必须改为 FAISS 完整可用时只加载 FAISS index + ids 映射所需 metadata，跳过 embedding matrix。FAISS 缺失或不匹配时才 fallback 到 SQLite/numpy。

## 观察 3：GLM-Embedding-3 是 2048 维，不是 2028

维度核对结论：新 embedding 为 2048 维。

影响：

- 单条向量体积相比 Jina 1024 维约翻倍。
- SQLite `embedding_json` 反序列化成本翻倍。
- numpy matrix 内存成本翻倍。
- FAISS index 体积放大。
- query embedding 与 rerank 前检索链路更容易暴露网络和 CPU 成本。

关键决策：所有 Phase 33 文档、测试、benchmark 和 cache key 必须使用 `dimension=2048`，避免 2028 这种误写进入代码或报告。

## 观察 4：旧 Jina 资产应保留为对照组

旧 Jina FAISS 文件仍有价值：

```text
data/faiss/jina_jina-embeddings-v3_dim1024.index
data/faiss/jina_jina-embeddings-v3_dim1024_ids.json
```

新 GLM FAISS 文件：

```text
data/faiss/paratera_GLM-Embedding-3_dim2048.index
data/faiss/paratera_GLM-Embedding-3_dim2048_ids.json
```

旧 Jina 不应删除，理由：

- 回滚保险。
- GLM-Embedding-3 迁移质量对照。
- 复现阶段 29/30 旧评分。
- 节省重新 embedding 成本。
- 排查召回差异。

关键决策：Phase 33 的迁移验证不是“新开质量闭环”，而是给 provider 迁移补上诚实验收：同题集对比 Jina 与 GLM 的 precision@k、hit@k、source/citation 覆盖和 unsupported/refusal 边界。

## 观察 5：FAISS 当前是 IndexFlatIP，不是 HNSW

位置：`app/services/retrieval/faiss_index.py`。

当前 FAISS 类型：

```text
faiss.IndexFlatIP(dimension)
```

含义：

- `IndexFlatIP` 是精确内积搜索。
- embedding 已 L2 归一化，因此内积排序等价于余弦相似度。
- 12K 级别向量使用精确搜索合理，结果稳定、可解释，也方便和旧 numpy cosine search 对齐。

关键决策：Phase 33 不引入 HNSW。HNSW 适合十万级以上或延迟瓶颈明确来自向量扫描时再评估；当前优先修冷启动冗余。

## 观察 6：MIMO 慢不能先验成立

用户实测 ReAct 查询约 33-44 秒，但这段耗时可能包括：

- query embedding provider 网络延迟。
- FAISS / fallback 检索加载。
- rerank provider 网络延迟。
- ReAct planner 多轮调用。
- answer generation。
- SSE 首 token 等待。

关键决策：Phase 33 必须先加 latency trace，再比较 chat provider。DeepSeek 可以作为 benchmark candidate，但不直接替换默认 MIMO。

## 观察 7：DeepSeek benchmark 的边界

DeepSeek 可用于 benchmark，但不能直接变成默认 provider。

需要对比：

- MIMO baseline。
- DeepSeek chat candidate。
- 可选 DeepSeek reasoner smoke。

指标：

- `time_to_first_token`
- `time_to_final`
- `planner_latency`
- `answer_latency`
- `tool_latency`
- `token_count`
- `tokens_per_second`
- citation 是否稳定
- refusal 是否一致
- 是否泄露 `reasoning_content`

关键决策：DeepSeek reasoner 如做 smoke，必须确保 `reasoning_content` 不写入前端、日志、CSV、文档、测试或 Obsidian。

## 观察 8：baseline 与 benchmark 的区别

baseline：当前参照方案，例如 MIMO 当前链路。

benchmark：对照测试过程，用同一批问题和同一套指标比较 MIMO、DeepSeek 等方案。

一句话：baseline 是 benchmark 里的参照组；benchmark 是比较方法。

## 风险与防线

- 风险：FAISS-only 加载误用不完整索引。
  - 防线：必须验证 provider、model、dimension、complete、ids metadata、chunk_id 映射完整性，不满足即 fallback。
- 风险：跳过 numpy 后破坏 deterministic / CI。
  - 防线：FAISS 缺失时继续 numpy fallback；测试 fixture 不依赖本地 `.index`。
- 风险：query embedding cache 命中错误。
  - 防线：cache key 必须包含 provider、model、dimension、normalized query。
- 风险：latency trace 泄露敏感信息。
  - 防线：只记录数值耗时、计数和安全摘要，不记录 prompt、hidden thought、raw response、key、受限全文。
- 风险：GLM 质量验证缺少真实 index 或 API。
  - 防线：自动测试走 fixture；真实评测缺失时写 skipped/error，不伪造成 pass。
- 风险：DeepSeek benchmark 变相改默认模型。
  - 防线：Phase 33 只输出报告和建议，不改默认 provider。

## Phase 1 发现：设计契约先行可降低后续实现漂移

已新增 `docs/stage33_rag_performance_embedding_validation.md` 和 `tests/test_stage33_design.py`。测试把以下边界固定为可回归检查：

- GLM-Embedding-3 维度是 2048。
- FAISS 完整时走 `FAISS-only`，不可用或不匹配时走 `numpy_fallback`。
- latency trace 必须包含 query embedding、FAISS/vector search、rerank、planner、answer、tool、首 token 和最终耗时。
- DeepSeek 只作为 benchmark candidate，MIMO 仍是 baseline，不直接替换默认 provider。
- 不记录 hidden thought、`reasoning_content`、provider raw response、API key、Bearer token 或受限全文。

验证：

```text
python -m pytest tests\test_stage33_design.py -q
2 passed
```

## Phase 2 发现：FAISS-only 主路径不需要 embedding_json

已调整 `app/services/retrieval/vector_cache.py`：

- `_ensure_loaded()` 先尝试完整 FAISS index。
- FAISS provider/model/dimension/complete/ids 校验通过时，只加载 chunk/document metadata。
- FAISS 主路径把 `load_mode` 设为 `faiss_only`，并保持 `_normalized_matrix` 为空。
- FAISS 缺失、不完整、ids 不完整或 DB 有效 embedding 集合与 ids 不一致时，回退 `numpy_fallback`。

新增测试证明：

- 完整 FAISS 存在时不会调用 `deserialize_embedding()`，也就不会反序列化 SQLite 的 `embedding_json`。
- `complete=false` 会回退 numpy。
- ids metadata 不完整会回退 numpy。

验证：

```text
python -m pytest tests\test_vector_cache_faiss.py tests\test_vector_cache.py tests\test_vector_search.py -q
13 passed
```

新增 `scripts/benchmark_stage33_rag_latency.py`，默认 deterministic 离线运行，只写 provider/model/dimension、load_mode、query embedding latency、vector search latency、total latency 和 result_count，不写 provider raw response。

## Phase 3 发现：query cache 必须停在 query 层

已新增 `app/services/retrieval/query_embedding_cache.py`，并在 `VectorSearchService` 中接入。关键边界：

- cache key = provider + model_name + dimension + normalized query text。
- normalized query text 只做 trim 和空白折叠，不做 casefold，避免真实 provider 在大小写敏感时串用 embedding。
- 只缓存 `embed_query()` 结果，不缓存 `embed_texts()`，所以不改变文档写入型 embedding 和 `chunk_embeddings`。
- 缓存有 `max_size` 和 `ttl_seconds`，超过容量按 LRU 淘汰。
- `clear()` 和 `stats()` 可供测试、benchmark 或后续 smoke 使用。

验证：

```text
python -m pytest tests\test_query_embedding_cache.py tests\test_vector_search.py tests\test_embedding_provider.py -q
28 passed
```

## Phase 4 发现：latency trace 可以用 request-local 聚合

已新增 `app/services/observability/latency_trace.py`，通过 `ContextVar` 在一次请求内聚合安全耗时字段。当前覆盖：

- `VectorSearchService`：`query_embedding_latency_ms`、`vector_search_latency_ms`。
- `VectorIndexCache`：`faiss_search_latency_ms` 或 `numpy_search_latency_ms`。
- `HybridSearchService`：`rerank_latency_ms`，并把 trace 显式传入并行 vector worker。
- `ReActAgentService`：`planner_latency_ms`、`tool_latency_ms`、`answer_latency_ms`、`time_to_final_ms`、`iteration_count`、`tool_call_count`。
- `/agent/query/stream`：首个 token 输出前补 `time_to_first_token_ms`。

安全边界：`latency_trace` 只包含数值、计数和空值，不包含 hidden thought、`reasoning_content`、`raw_response`、Bearer、Authorization、API key 或受限全文。

验证：

```text
python -m pytest tests\test_react_latency_trace.py tests\test_agent_api.py tests\test_react_stream_events.py tests\test_agent_stream_api.py -q
31 passed
```

## Phase 5 发现：GLM 可跑通，但 Jina 当前缺本地真实配置

已新增 `scripts/evaluate_stage33_embedding_migration.py` 和 `tests/test_stage33_embedding_validation.py`。

脚本边界：

- 默认 dry-run，不触发真实 provider。
- 显式 `--execute-real` 才调用真实 provider。
- Jina baseline 固定为 `jina/jina-embeddings-v3/dim=1024`。
- GLM candidate 固定为 `paratera/GLM-Embedding-3/dim=2048`。
- 缺少 API key/base URL 时写 `skipped_missing_real_config`，不伪造成 pass。

本地运行结果：

```text
python -m pytest tests\test_stage33_embedding_validation.py -q
2 passed

python scripts\evaluate_stage33_embedding_migration.py --execute-real
glm_candidate: status=completed p@5=0.867 coverage=0.637 latency=1469.98ms decision=review_for_silent_regression
jina_baseline: status=skipped p@5=0.000 coverage=0.000 latency=0.00ms decision=skipped_missing_real_config
```

解读：GLM-Embedding-3 2048 维真实 query 侧可以跑通，但当前机器没有 Jina query provider 配置，所以阶段 33 不能声称已经完成真实 GLM vs Jina 同环境对照。可用对照只能是旧阶段 29/30 Jina 历史结果和当前 GLM 结果，人工核验时应重点查看 `data/evaluation/stage33_embedding_migration_results.csv` 中 GLM 失败或低覆盖 query。

## Phase 6 发现：MIMO 可测，DeepSeek 当前只是未配置候选

已新增 `scripts/benchmark_stage33_chat_providers.py` 和 `tests/test_stage33_provider_benchmark.py`。

脚本边界：

- 默认 dry-run，不调用真实 provider。
- `--execute-real` 才调用本地 MIMO/DeepSeek 配置。
- DeepSeek 缺 key/base URL 时写 `skipped`，不改默认 provider。
- 输出字段只包含耗时、token_count、tokens_per_second、citation/refusal 一致性和 `reasoning_content_leak_risk`。
- 不保存 raw provider response。

本地真实 benchmark：

```text
python scripts\benchmark_stage33_chat_providers.py --execute-real
mimo_baseline/citation_case: status=completed ttft=6265.58ms total=6952.99ms tokens_per_second=1.58 leak=false
mimo_baseline/refusal_case: status=completed ttft=2909.34ms total=6800.78ms tokens_per_second=9.26 leak=false
deepseek_candidate/citation_case: status=skipped
deepseek_candidate/refusal_case: status=skipped
```

解读：MIMO baseline 在两个小样例上可流式响应；DeepSeek 当前没有本地配置，所以阶段 33 不能给出 DeepSeek 优劣结论，只能保留候选 benchmark 入口。默认 provider 不应切换。

## Phase 7 发现：阶段 33 可以进入人工核验，但不能替代人工判断

收尾已完成：

- `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD` 已同步阶段 33 最新状态。
- 新增 `docs/phase_reviews/phase-33.md`，把范围、验证、skipped 项和人工核验重点写清。
- Obsidian 已新增阶段页与阶段汇报索引，并更新首页、阶段索引、阶段汇报索引。

最终验证结果：

```text
阶段 33 聚焦测试：16 passed
全量 pytest：643 passed
阶段 30 评分：overall=83.17 grade=B release_decision=review_required
browser desktop：Agent 查询、折叠思考过程、最终答案、无横向溢出、console errors=0
browser 390x844 mobile：Agent 查询、折叠思考过程、最终答案、无横向溢出、console errors=0
```

关键判断：

- 阶段 33 的工程改动已能进入人工核验。
- GLM-Embedding-3 真实 query 侧已跑通，但 Jina 同环境 baseline skipped，因此不能声称 GLM 已经证明优于或完全等价于 Jina。
- DeepSeek 当前 skipped，因此不能声称 DeepSeek 优于 MIMO，也不能切默认 provider。
- 当前工作区必须继续停在用户人工核验前，不执行 `git add`、commit、tag、push 或 PR。

## 新词解释

- FAISS-only 冷启动：是什么 -> 启动向量检索缓存时只加载 FAISS index 和必要映射；在本项目哪里出现 -> `VectorIndexCache`；作用 -> 避免有 FAISS 时还构建无用 numpy matrix；面试怎么说 -> “我把精确向量索引路径和 fallback 路径拆开，FAISS 完整时不再加载全量 embedding matrix。”
- query embedding cache：是什么 -> 缓存用户问题对应的向量；在本项目哪里出现 -> vector/hybrid search 的 query embedding 层；作用 -> 同一问题重复查询时减少真实 provider 调用；面试怎么说 -> “文档 embedding 不变，只缓存 query embedding，并把 provider/model/dimension 放进 key 防止串模型。”
- latency trace：是什么 -> 对链路各段耗时做结构化记录；在本项目哪里出现 -> `/agent/query`、`/agent/query/stream`、ReAct 工具调用；作用 -> 判断慢在检索、rerank、planner 还是答案生成；面试怎么说 -> “我没有凭感觉换模型，而是先把端到端延迟拆成可观测指标。”
- benchmark provider：是什么 -> 用同一批问题对比候选模型供应商；在本项目哪里出现 -> Phase 33 的 MIMO vs DeepSeek 脚本；作用 -> 数据驱动判断是否值得切换；面试怎么说 -> “MIMO 是 baseline，DeepSeek 是 candidate，先 benchmark 再决策。”

## 面试表达准备

阶段 33 可以这样讲：

```text
阶段 33 我没有继续堆 Agent 功能，而是回到 RAG core 做性能和迁移验证。阶段 32 后真实 ReAct 查询出现 33-44 秒延迟，我先拆链路，发现 FAISS 可用时 VectorIndexCache 仍把 12,731 条 2048 维向量从 SQLite 反序列化成约 208MB 的 numpy matrix，但实际搜索走 FAISS，这就是确定浪费。

所以我把向量缓存拆成 FAISS-only 主路径和 numpy fallback 路径：完整 FAISS 存在时只加载 index 和 ids 映射，索引缺失或不匹配时再回退 SQLite/numpy。然后加 query embedding cache 和 latency trace，把 embedding、FAISS、rerank、planner、answer、首 token 等耗时拆开。最后用阶段 29/30 题集对比 Jina 1024 维和 GLM-Embedding-3 2048 维，确认迁移没有静默退化；DeepSeek 只作为 benchmark candidate，不直接替换默认 MIMO。
```

# 阶段 33：RAG 链路性能优化与 Embedding 迁移验证

## 目标

阶段 33 聚焦真实 RAG/ReAct 链路的性能优化，并诚实验证 GLM-Embedding-3 迁移后的检索质量。阶段 32 已完成 `react_agent` 决策升级和工具调用实时可视化，本阶段不继续扩大 Agent 能力，而是回到 RAG core：先拆出耗时，再优化确定浪费，最后用对照评测确认新旧 embedding 和 chat provider 的风险。

核心目标：

- FAISS 完整可用时，`VectorIndexCache` 不再构建无用 numpy matrix。
- FAISS 不可用、不完整、损坏或 provider/model/dimension 不匹配时，SQLite/numpy fallback 仍正常。
- 同一 query 的 embedding 可缓存，重复查询不重复调用真实 embedding provider。
- RAG/ReAct 链路输出安全 latency trace。
- GLM-Embedding-3 2048 维索引和旧 Jina 1024 维索引有同题集质量对照。
- DeepSeek 只作为 chat provider benchmark candidate，不直接替换默认 MIMO。

## 不做事项

- 不删除旧 Jina 向量或 FAISS 索引。
- 不直接切换默认 MIMO provider。
- 不新增外部数据源。
- 不新增写入型 Agent 工具。
- 不做部署、运维、监控平台化改造。
- 不扩大成完整质量闭环或新一轮语料治理阶段。
- 不让真实 API 成为 CI 或本地全量测试前提。

## 性能指标

阶段 33 的性能判断必须来自分段指标，而不是单次体感。

必备指标：

- `cold_start_ms`
- `first_query_ms`
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
- `token_count`
- `tokens_per_second`

这些指标只记录安全数值、计数和脱敏状态，不记录 prompt、hidden thought、provider raw response 或受限全文。

## FAISS-only 加载策略

阶段 31 的 `VectorIndexCache` 已支持 FAISS，但旧路径会先从 SQLite 读取全部 `chunk_embeddings`，反序列化 embedding JSON，构建 numpy matrix，然后再加载 FAISS。GLM-Embedding-3 是 2048 维，不是 2028 维；在 12K 级别 chunk 下，冗余 matrix 会带来明显冷启动和内存成本。

阶段 33 的主路径：

```text
VectorIndexCache.search()
-> 尝试加载 provider/model/dimension 匹配的完整 FAISS index
-> 验证 ids metadata 完整且 chunk_id 均能映射到当前有效 chunk
-> 只加载 FAISS index + 必要 chunk metadata
-> FAISS search
```

只有以下情况进入 fallback：

- `.index` 或 `_ids.json` 缺失。
- FAISS 文件损坏或无法加载。
- metadata 中 provider、model、dimension 不匹配。
- `complete=false`。
- FAISS row count 与 ids 数量不一致。
- ids 缺失、重复或无法映射到有效 chunk。
- 当前 chunk content hash 与 embedding content hash 不一致。

fallback 路径继续使用 SQLite -> numpy matrix，保证 deterministic 测试和无 FAISS 环境可运行。

## Query Embedding Cache

新增 query embedding cache 只缓存用户问题对应的 query embedding，不缓存文档写入型 embedding，也不改变 `chunk_embeddings`。

cache key 至少包含：

```text
provider
model
dimension
normalized query text
```

缓存必须有容量上限或 TTL。缓存命中只减少 query embedding provider 调用，不改变检索排序语义。测试应能证明同一 query 重复检索不会重复调用真实或 fake embedding provider。

## Latency Trace

latency trace 覆盖 `/agent/query`、`/agent/query/stream` 和 `react_agent` 关键路径，并尽量兼容 default 与旧 `agentic` 对照。metadata 中可携带摘要级 timing，前端可暂不做复杂 UI。

允许记录：

- 耗时数值。
- 工具名。
- 安全状态。
- iteration/tool call 计数。
- 是否 cache hit。

禁止记录：

- hidden thought。
- `reasoning_content`。
- provider raw response。
- API key。
- Bearer token。
- Authorization header。
- 受限全文。
- 完整 prompt 或未经脱敏的上下文。

SSE 向后兼容：继续保留 `token`、`metadata`、`done`、`error`，并保留阶段 32 的 `agent_step`、`tool_call_start`、`tool_call_result`。

## Embedding 迁移验证

GLM-Embedding-3 维度固定为 2048。旧 Jina 索引用作回滚保险和质量对照，不删除：

```text
data/faiss/jina_jina-embeddings-v3_dim1024.index
data/faiss/jina_jina-embeddings-v3_dim1024_ids.json
```

GLM-Embedding-3 新链路保留：

```text
data/faiss/paratera_GLM-Embedding-3_dim2048.index
data/faiss/paratera_GLM-Embedding-3_dim2048_ids.json
```

迁移验证使用阶段 29/30 题集或 deterministic fixture，对比：

- `precision@k`
- `hit@k`
- source/citation 覆盖
- unsupported/refusal 边界
- 查询耗时

目标是确认没有静默退化，不是强行证明 GLM 更好。真实 index 或 provider 缺失时，应输出 `skipped` 或 `error`，不能伪造成 pass。

## Chat Provider Benchmark

MIMO 是 baseline，DeepSeek 是 benchmark candidate。阶段 33 不直接替换默认 MIMO。

对比指标：

- `time_to_first_token`
- `time_to_final`
- `planner_latency`
- `answer_latency`
- `token_count`
- `tokens_per_second`
- citation 稳定性
- refusal 一致性
- `reasoning_content` 泄露风险

DeepSeek reasoner 如参与 smoke，只能作为显式手动候选，并必须确保 `reasoning_content` 不进入前端、日志、CSV、文档、测试或 Obsidian。

## 完成标准

- FAISS 完整可用时，`VectorIndexCache` 使用 `faiss_only` 路径。
- FAISS 不可用或不匹配时，`numpy_fallback` 路径仍正常。
- query embedding cache key 包含 provider、model、dimension、normalized query text，且有容量或 TTL。
- RAG/ReAct metadata 输出安全 latency trace。
- GLM-Embedding-3 vs Jina 有对照 CSV 和摘要结论。
- DeepSeek benchmark 有 dry-run 和报告，不改默认 provider。
- `default`、`agentic`、`react_agent`、`/chat` 和 SSE 兼容性不破坏。
- 全量 pytest 通过。
- `scripts/score_stage30_quality.py` overall score 保持 `>= 83.17`。
- 浏览器 smoke 通过：Agent 查询、折叠思考过程、最终答案、无横向溢出、console errors=0。
- 最终停在用户人工核验前，不 `git add`、不 commit、不创建 `phase-33-complete` tag、不 push、不创建 PR。

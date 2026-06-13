# 阶段 33 验收草稿：RAG 链路性能优化与 Embedding 迁移验证

状态：开发与自动验证已完成，等待用户人工核验。

分支：`codex/phase-33-rag-performance-embedding-validation`

基线：`main -> 608a6e9 Merge phase 32 react agent observability`，`phase-32-complete -> f259f97 Complete phase 32 react agent observability` 已合并到 `main`。

提交边界：尚未 `git add`、`git commit`、`git tag`、`git push`，未创建 PR，未创建 `phase-33-complete` tag。

## 验收结论

阶段 33 的代码、脚本、测试和文档已达到“进入人工核验前”的状态。当前不能判定为最终 PASS，因为用户仍需人工抽样确认 FAISS-only 行为、latency trace 安全字段、GLM-Embedding-3 与 Jina 的同环境质量对照是否需要补跑，以及 DeepSeek 未配置时是否接受 skipped 结果。

## 范围核对

- P0 `VectorIndexCache` 已支持完整 FAISS 可用时 `faiss_only` 加载，跳过 SQLite embedding JSON 反序列化和 numpy matrix 构建。
- P0 fallback 已覆盖 FAISS 缺失、不完整、provider/model/dimension 不匹配和 ids 不完整。
- P1 query embedding cache 已接入 `VectorSearchService`，key 包含 provider、model、dimension、normalized query text，并带 TTL 与容量上限。
- P2 latency trace 已接入 vector search、FAISS/numpy search、hybrid rerank、ReAct planner/tool/answer 和 SSE metadata。
- P3 GLM-Embedding-3 迁移验证脚本已新增，正确使用 2048 维；Jina 同环境 baseline 因缺少本机真实配置被显式 skipped。
- P4 DeepSeek 仅作为 benchmark candidate；当前本机未配置 DeepSeek，脚本显式 skipped，未替换默认 MIMO。

## 测试与评测证据

已完成的阶段内聚焦验证：

```text
tests/test_stage33_design.py: 2 passed
tests/test_vector_cache_faiss.py + cache/search regression: 13 passed
tests/test_query_embedding_cache.py + vector/search embedding regression: 28 passed
react latency trace/API/SSE regression: 31 passed
tests/test_stage33_embedding_validation.py: 2 passed
tests/test_stage33_provider_benchmark.py: 2 passed
阶段 33 最终聚焦测试: 16 passed
全量 pytest: 643 passed
stage30 quality score: overall=83.17 grade=B release_decision=review_required
browser desktop/mobile: final answer present, collapsible thought panel present, horizontal overflow=false, console errors=0
```

评测产物：

```text
data/evaluation/stage33_rag_latency_benchmark.csv
data/evaluation/stage33_embedding_migration_results.csv
data/evaluation/stage33_embedding_migration_summary.csv
data/evaluation/stage33_chat_provider_benchmark.csv
```

当前真实观察：

```text
GLM-Embedding-3 2048 维真实 query 侧 completed，precision@5=0.867，coverage=0.637，decision=review_for_silent_regression
Jina baseline 因本机缺少真实 provider 配置 skipped_missing_real_config
MIMO baseline completed，reasoning_content_leak_risk=false
DeepSeek candidate 因未配置 skipped
```

## 安全与合规核对

- 阶段 33 未新增外部资料来源、爬虫或受限全文。
- 旧 Jina FAISS 索引与 ids 文件保留为回滚保险和质量对照。
- GLM-Embedding-3 维度在文档、脚本和测试中统一为 2048。
- latency trace 不记录 hidden thought、reasoning_content、raw provider response、API key、Bearer token、Authorization header 或受限全文。
- benchmark/evaluation CSV 只记录脱敏指标、状态、延迟、provider/model 名称和错误摘要。
- 默认测试和 dry-run 不要求真实 API。

## 人工核验重点

1. 抽样确认完整 FAISS index 与 ids metadata 可用时，运行时确实为 `load_mode="faiss_only"`，且 `_normalized_matrix` 为空。
2. 故意移走或破坏 FAISS ids metadata，确认 `load_mode="numpy_fallback"` 仍能返回检索结果。
3. 复查同步 `/agent/query` 与 `/agent/query/stream` metadata 中的 `latency_trace`，确认只包含安全耗时字段。
4. 决定是否补配 Jina 真实 query provider 后重跑 `scripts/evaluate_stage33_embedding_migration.py --execute-real`，形成同环境 GLM vs Jina 对照。
5. 决定是否补配 DeepSeek 后重跑 `scripts/benchmark_stage33_chat_providers.py --execute-real`，但不要直接替换默认 MIMO。

## 后续提交建议

人工核验通过后，再执行阶段 33 最终提交、创建 `phase-33-complete` tag，并按项目流程推送分支、main 和 tag。tag 必须指向阶段 33 最终功能提交，不要移动已有阶段 tag。

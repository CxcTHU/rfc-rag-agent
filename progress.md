# 阶段 26 进度日志：检索性能优化 + Cross-Encoder 重排序

## 当前状态

- 当前阶段：阶段 26「检索性能优化 + Cross-Encoder 重排序」。
- 当前分支：`codex/phase-26-retrieval-performance-reranking`。
- 前置条件：阶段 25 已完成提交、合并到 main 并创建 `phase-25-complete` tag。
- 阶段 26 状态：Phase 0-7 已完成，当前停在用户人工核验前状态。
- 提交状态：尚未 `git add`、尚未提交、尚未创建 `phase-26-complete` tag、尚未推送。

## Phase 0 日志：启动校准与文件计划

本 Phase 解决阶段 26 的正确起点问题；它位于 RAG 开发链路之前，负责确认阶段 25 的提交、tag、main 合并状态和阶段 26 分支，避免从错误基线继续开发。

校准结果：

- 已阅读项目入口规则、README、进度、架构、数据来源、阶段 25 设计文档，以及根目录 `task_plan.md`、`findings.md`、`progress.md`。
- `git status -sb`：启动时位于 `main...origin/main`，工作区干净。
- `git log --oneline -5 --decorate`：
  - `56f5d4 (HEAD -> main, origin/main, origin/HEAD) Merge phase 25 chitchat and SSE streaming`
  - `0a89d55 (tag: phase-25-complete, origin/codex/phase-25-chitchat-and-sse-streaming, codex/phase-25-chitchat-and-sse-streaming) Complete phase 25 chitchat and SSE streaming`
  - `c4eda98 Merge phase 24 multi-turn conversation`
  - `64069ba (tag: phase-24-complete, origin/codex/phase-24-multi-turn-conversation, codex/phase-24-multi-turn-conversation) Complete phase 24 multi-turn conversation`
  - `8fc1cfa Merge phase 23 agentic eval and auto routing`
- `phase-25-complete` 指向 `0a89d55`，未移动任何既有阶段 tag。
- `git merge-base --is-ancestor phase-25-complete main` 通过，确认阶段 25 已合并到 `main`。
- 已从 `56f5d4` 创建并切换到 `codex/phase-26-retrieval-performance-reranking`。
- Planning with Files 的 session catchup 脚本在 `.claude` 路径不存在；已记录并继续使用项目根目录三份计划文件。

## Phase 1 日志：阶段 26 设计文档

本 Phase 解决“优化方案先有可审查合同”的问题；它横跨向量检索、hybrid 检索、Provider 层和 Brain/Agent 上下文入口。现在做，是为了避免后续直接改代码时混淆性能优化、重排序质量提升和真实 API 安全边界。

完成内容：

- 新增 `docs/stage26_retrieval_performance_reranking.md`。
- 文档明确当前瓶颈：`VectorSearchService._list_indexed_chunks()` 每次全表加载、JSON 反序列化、纯 Python 余弦循环。
- 文档明确 `VectorIndexCache` 方案：进程内缓存 embedding 矩阵，查询时用 numpy 矩阵乘法。
- 文档明确 hybrid 并行方案：keyword/BM25 与 vector search 用 `ThreadPoolExecutor` 并行，但 SQLAlchemy `Session` 不跨线程共享。
- 文档明确 `ReRankingProvider` 协议：deterministic provider 负责测试，OpenAI-compatible provider 作为可配置真实运行能力。
- 文档明确 Cross-Encoder 集成点：hybrid 召回 top-20~30 后精排 top-5，再送 Brain/Chat/Agent。
- 文档明确安全边界：不引入 `torch`/`sentence-transformers`，不让真实 API 成为 CI 前提，不写入凭据或供应商原始敏感响应。

## Phase 2 日志：Profiling 与基线基准

本 Phase 解决“优化前哪里慢、慢多少”的问题；它位于 RAG 的 embedding、vector、keyword、hybrid 和 Agent 端到端链路。现在做，是为了给后续 numpy、缓存、并行和 rerank 建立可量化对照。

完成内容：

- 新增 `scripts/benchmark_retrieval.py`。
- 脚本默认 provider 改为 `deterministic`，避免默认读取 `.env` 后误触发真实 API；真实 provider 只允许显式 `--provider` 运行。
- 脚本输出 Markdown 表格，字段包括 query、chunk/embedding 数量、provider、operation、runs、min/mean/median/max ms。
- 支持 `--profile` 输出单次 hybrid search 的 cProfile 摘要。
- 新增 `tests/test_benchmark_retrieval.py`。

基线结果：

```text
.\.venv\Scripts\python.exe scripts\benchmark_retrieval.py --runs 1 --top-k 5 --query "What affects filling capacity in rock-filled concrete?"

chunks=8918, embeddings=8918, provider=deterministic/hash-token-v1/dim=64
query_embedding=0.07 ms
keyword_search=733.06 ms
vector_search=1456.82 ms
hybrid_search=2199.56 ms
agent_query=2174.16 ms
```

cProfile 发现：

```text
HybridSearchService.search(): ~3.69s cumulative
VectorSearchService.search(): ~2.63s cumulative
rank_vector_results(): ~1.95s cumulative
topic_anchor_score(): ~1.94s cumulative
normalize_text(): ~1.84s cumulative
cosine_similarity(): ~0.26s cumulative
_list_indexed_chunks(): ~0.19s cumulative
deserialize_embedding(): ~0.15s cumulative
```

测试结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_benchmark_retrieval.py -q
3 passed in 0.46s
```

遇到的问题与处理：

- 初版脚本默认沿用 `.env` 的真实 Jina provider，普通基准运行可能触发真实 API；已改为默认 deterministic。
- `time_operation()` 初版只在外层校验 `runs`，直接调用时错误信息不清晰；已在函数内部补充 `runs > 0` 校验，并用测试覆盖。

## Phase 3 日志：numpy 向量化 + 内存索引缓存

本 Phase 解决向量检索重复全表加载和纯 Python 逐条计算的问题；它位于 query embedding 之后、向量召回结果排序之前。现在做，是因为 Phase 2 已证明 vector search 是 hybrid 延迟的重要组成。

完成内容：

- `pyproject.toml` 新增 `numpy>=2.0.0`。
- 新增 `app/services/retrieval/vector_cache.py`：
  - `VectorIndexCache`
  - `VectorIndexEntry`
  - `VectorIndexMatch`
  - `get_vector_index_cache()`
  - `invalidate_vector_index_cache()`
- `VectorSearchService.search()` 改为使用 `VectorIndexCache.search()`，查询时执行 numpy 矩阵乘法。
- 保留 `cosine_similarity()` 纯 Python 实现，用于测试误差对照。
- `VectorIndexService.build_index()` 在新增或更新 embedding 后自动 invalidate cache。
- `rank_vector_results()` 避免每个结果重复 `expand_query_terms(query)`。

测试结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_vector_cache.py tests\test_vector_search.py tests\test_vector_index_service.py tests\test_vector_search_api.py -q
17 passed in 4.11s
```

优化后基准：

```text
chunks=8918, embeddings=8918, provider=deterministic/hash-token-v1/dim=64
query_embedding=0.06 ms
keyword_search=725.64 ms
vector_search=335.32 ms
hybrid_search=710.26 ms
agent_query=685.49 ms
```

对比 Phase 2：

```text
vector_search: 1456.82 ms -> 335.32 ms
hybrid_search: 2199.56 ms -> 710.26 ms
agent_query: 2174.16 ms -> 685.49 ms
```

新发现：

- cache 热状态下 `VectorSearchService.search()` 在 cProfile 中约 0.007s，主热点已转移到 `KeywordSearchService.search()`。
- 这说明 Phase 4 并行对冷启动或真实 provider 场景仍有价值，但在 deterministic/cache 热状态下 hybrid 已接近 keyword search 单路耗时。

## Phase 4 日志：BM25 与向量检索并行执行

本 Phase 解决 hybrid search 两路召回串行等待的问题；它位于 keyword/BM25 与 vector 两路候选召回阶段。现在做，是因为 Phase 3 后 vector 已加速，hybrid 应避免继续把两路耗时相加。

完成内容：

- `HybridSearchService` 新增默认并行执行路径。
- 使用 `ThreadPoolExecutor(max_workers=2)` 同时运行 keyword 与 vector search。
- 每个 worker 创建独立 SQLAlchemy `Session`，不跨线程共享主请求 Session。
- 保留 `parallel=False` 串行路径，用于对照测试和排障。

测试结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_hybrid_search.py tests\test_vector_search_api.py tests\test_agent_tools.py -q
15 passed in 4.21s
```

基准结果：

```text
chunks=8918, embeddings=8918, provider=deterministic/hash-token-v1/dim=64
keyword_search=740.07 ms
vector_search=357.60 ms
hybrid_search=745.90 ms
agent_query=690.14 ms
```

结论：

- 当前 hybrid search 已接近 `max(keyword, vector)`，而非 keyword + vector。
- cache 热状态下 keyword search 是主导耗时；后续优化重点应放在 rerank 质量和必要时 keyword 归一化热点。

## Phase 5 日志：Cross-Encoder 重排序层

本 Phase 解决粗召回缺少语义精排的问题；它位于 hybrid search 召回之后、Brain/Chat/Agent 组装上下文之前。现在做，是因为 Phase 3-4 已把检索延迟压低，可以在预算内加入可配置 rerank。

完成内容：

- 新增 `app/services/retrieval/reranking.py`。
- 新增 `ReRankingProvider` Protocol 和 `ReRankResult`。
- 新增 `DeterministicReRankingProvider`，用于本地测试和 CI。
- 新增 `OpenAICompatibleReRankingProvider`，用于可选真实 rerank API。
- 新增 `create_reranking_provider()` 工厂函数。
- `HybridSearchService` 默认启用 deterministic rerank，召回扩大到 top-20~30 后精排 top-k。
- `app/core/config.py` 新增 reranking 相关配置。
- `scripts/benchmark_retrieval.py` 新增 `rerank_only` 计时指标。

测试结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_reranking.py tests\test_hybrid_search.py tests\test_vector_search_api.py tests\test_answer_service.py tests\test_agent_tools.py -q
30 passed in 7.38s

.\.venv\Scripts\python.exe -m pytest tests\test_benchmark_retrieval.py tests\test_reranking.py -q
7 passed in 0.52s
```

基准结果：

```text
chunks=8918, embeddings=8918, provider=deterministic/hash-token-v1/dim=64
keyword_search=745.35 ms
vector_search=333.17 ms
hybrid_search=733.75 ms
rerank_only=1.50 ms
agent_query=721.61 ms
```

边界说明：

- 默认 rerank 使用 deterministic provider，不依赖真实 API。
- OpenAI-compatible rerank provider 只作为运行时可选能力；API key 仍只允许在 `.env` 或环境变量里出现，不写入 Git、CSV、文档、测试或 Obsidian。

## Phase 6 日志：端到端基准测试与回归验证

本 Phase 解决优化后全链路是否更快、旧接口是否被破坏的问题；它位于代码开发完成后的全链路验收阶段。现在做，是因为必须先证明检索、问答、Agent、SSE 和 quality report 都稳定，再进入文档收尾。

基准结果：

```text
英文 query:
query_embedding=0.07 ms
keyword_search=743.59 ms
vector_search=349.45 ms
hybrid_search=720.30 ms
rerank_only=1.53 ms
agent_query=735.48 ms

中文 query:
query_embedding=0.05 ms
keyword_search=655.07 ms
vector_search=1.93 ms
hybrid_search=706.65 ms
rerank_only=0.88 ms
agent_query=696.88 ms
```

对比 Phase 2 英文基线：

```text
vector_search: 1456.82 ms -> 349.45 ms
hybrid_search: 2199.56 ms -> 720.30 ms
agent_query: 2174.16 ms -> 735.48 ms
```

测试结果：

```text
focused:
82 passed in 20.36s

full:
.\.venv\Scripts\python.exe -m pytest -q
511 passed in 50.49s
```

浏览器/API 验证：

```text
8001 current service:
GET /health -> 200
POST /agent/query/stream {"question":"thanks","top_k":2} -> token / metadata / done
POST /search/hybrid -> 200
GET /quality-report -> 200
Browser desktop 1280x720 -> RFC RAG 工作台
Browser mobile 390x844 -> RFC RAG 工作台
```

备注：

- 8000 端口已有旧服务占用，`/agent/query/stream` 返回 404；当前阶段代码验证改用 8001，并在验证后停止 8001 临时服务。

## 阶段 26 目标概述

从阶段 25 完成后的 main 出发，实现检索性能优化 + Cross-Encoder 重排序：

1. **Profiling 与基线基准**：用 cProfile 和 perf_counter 量化当前检索管线每层耗时，建立优化前基线。
2. **numpy 向量化加速**：向量搜索从纯 Python 逐条余弦改为 numpy 矩阵运算，引入内存向量索引缓存。
3. **BM25 与向量检索并行**：hybrid search 中两路检索从串行改为 ThreadPoolExecutor 并行。
4. **Cross-Encoder 重排序**：新增 `ReRankingProvider` Protocol，hybrid search 召回 top-20~30 后 cross-encoder 精排取 top-5。
5. **端到端基准对比**：量化优化前后各层耗时和总响应时间改善。

## 阶段 25 验收基线

- 阶段 25 验收结论：已完成、已提交、已创建 `phase-25-complete` tag，并已合并到 `main`。
- 阶段 25 最终功能提交：`0a89d55 Complete phase 25 chitchat and SSE streaming`。
- 阶段 25 合并点：`56f5d4 Merge phase 25 chitchat and SSE streaming`。
- 测试基线：497 passed。
- 关键交付：闲聊短路、SSE 流式输出、ChatModelProvider stream_generate、/agent/query/stream 端点。

## 已知性能瓶颈

来自 `docs/progress.md` 阶段 25 遗留风险：
- 真实本地大库上普通 RAG 问题 `What affects filling capacity in rock-filled concrete?` 在同步和流式端点都超过 20 秒。
- 初步判断瓶颈在 `VectorSearchService._list_indexed_chunks()`：每次查询从数据库加载全部 ChunkEmbedding 行到 Python 内存，然后用纯 Python 循环逐条计算 `cosine_similarity()`。
- keyword search（BM25）和 vector search 串行执行，hybrid search 总耗时为两者之和。
- 缺少重排序层，召回质量仅靠 BM25 + 余弦的简单加权。

## 遗留风险

- 阶段 26 当前尚未经过用户人工核验，因此不能提交、不能创建 `phase-26-complete` tag、不能推送或创建 PR。
- 真实 `OpenAICompatibleReRankingProvider` 会增加网络延迟，当前只作为可配置运行时能力；全量测试和默认 benchmark 不依赖真实 API。
- keyword search 仍是当前 deterministic/cache 热状态下的主要耗时来源，可作为后续阶段的优化候选。
- 若未来 chunk 数量增长到更大规模，numpy 暴力矩阵乘法之后可再评估 FAISS 等 ANN 索引；当前阶段先保持轻量依赖。

## Phase 7 日志：文档同步、Obsidian 收尾与人工核验待提交状态

本 Phase 解决阶段 26 的交付边界和知识沉淀问题；它位于 RAG 运行链路之外，但决定后续人工核验、提交、tag 和交接是否清晰。现在做，是因为代码、测试和基准均已完成，文档可以准确描述最终行为。

完成内容：

- 已同步 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 已新增/更新 Obsidian 阶段 26 阶段页、Phase 0-7 汇报、阶段 26 Phase 汇报索引、首页、阶段索引和阶段汇报索引。
- 已在 `task_plan.md`、`findings.md`、`progress.md` 记录阶段 26 全部 Phase 完成、测试结果、基准对比和待人工核验状态。
- 当前未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

最终待核验状态：

```text
branch: codex/phase-26-retrieval-performance-reranking
phase-26-complete tag: not created
staged changes: none expected
commit/push/pr: not performed
```

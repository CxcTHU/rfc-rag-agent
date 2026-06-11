# 阶段 26 发现与关键决策

## 性能瓶颈分析

### 向量搜索全表扫描（核心瓶颈）

位置：`app/services/retrieval/vector_search.py` → `VectorSearchService._list_indexed_chunks()`

当前实现：
- 每次查询执行 `SELECT ChunkEmbedding JOIN Chunk JOIN Document`，加载全部 embedding 行到 Python 内存。
- 对每条记录调用 `deserialize_embedding()` 反序列化 JSON → Python list[float]。
- 对每条记录调用纯 Python `cosine_similarity()` 计算内积、模长、除法。
- 纯 Python 循环 + JSON 反序列化是 O(N) 中最慢的操作。

决策：
- 引入 numpy，将全部 embedding 加载为 `numpy.ndarray` 矩阵，预归一化。
- 查询时用 `normalized_matrix @ query_vector` 一次矩阵乘法完成所有余弦相似度计算。
- 新增 `VectorIndexCache` 在进程内缓存 embedding 矩阵，避免每次查询重复加载。

### 混合检索串行执行

位置：`app/services/retrieval/hybrid_search.py` → `HybridSearchService.search()`

当前实现：
- 先执行 `KeywordSearchService.search()`，再执行 `VectorSearchService.search()`。
- 两者无数据依赖，但串行执行导致 hybrid search 耗时 = keyword + vector。

决策：
- 使用 `concurrent.futures.ThreadPoolExecutor` 并行执行两路检索。
- SQLAlchemy Session 不能跨线程共享；需要在主线程查询后传递纯数据到子线程，或使用 `sessionmaker` 为子线程创建独立 Session。
- 并行后 hybrid search 耗时 ≈ max(keyword, vector)。

### 缺少重排序层

位置：hybrid search 之后、Brain/AgentService 组装 prompt 之前。

当前实现：
- 召回结果仅靠 BM25 分数 + 余弦相似度 + topic_anchor_score 加权排序。
- 没有 Cross-Encoder 语义精排，召回质量受限于 bi-encoder 粗排能力。

决策：
- 新增 `ReRankingProvider` Protocol，遵循项目现有 Provider 三件套模式（Protocol + Deterministic + OpenAI-compatible）。
- hybrid search 召回 top-20~30 → Cross-Encoder rerank → 返回 top-5 送 LLM。
- Cross-Encoder 本质上是把 (query, document) 对送入一个模型打分，比 bi-encoder 的独立编码更精确。
- 不引入 `torch` / `sentence-transformers`；通过 HTTP API 调用外部 re-rank 服务（Cohere、Jina、国产兼容），与现有 embedding/chat provider 一致。

## 依赖决策

### 新增 numpy

- numpy 是 Python 科学计算基础库，广泛使用，体积适中（~20MB）。
- 替代方案（不用 numpy）：保持纯 Python 但引入 `array` 模块或 `struct.pack`；速度提升有限，不值得。
- 替代方案（用 FAISS）：`faiss-cpu` 支持 ANN 近似搜索，但当前 chunk 数量（千级）未到 FAISS 必要规模；numpy 暴力矩阵乘法在千级向量上已经足够快（< 10ms），预留后续升级空间即可。
- 决策：先用 numpy 矩阵运算；如果后续 chunk 数量增长到万级以上，再考虑 FAISS。

### 不引入 torch / sentence-transformers

- Cross-Encoder 本地模型需要 torch（~2GB）+ sentence-transformers，对于轻量项目过重。
- 通过 HTTP API 调用 re-rank 服务，与现有 OpenAI-compatible 模式一致，零额外依赖。
- `DeterministicReRankingProvider` 用 keyword overlap 评分，保证测试不依赖真实 API。

## ReRankingProvider 协议设计

```python
class ReRankingProvider(Protocol):
    provider_name: str
    model_name: str

    def rerank(
        self,
        query: str,
        candidates: Sequence[str],
        top_k: int = 5,
    ) -> list[ReRankResult]:
        """Score and re-order candidates by relevance to query."""
```

- `ReRankResult` 包含 `index`（原始候选位置）、`score`（相关度评分）、`content`（文本内容）。
- `DeterministicReRankingProvider`：基于 query term 在 candidate 中的命中次数评分，可预测、可测试。
- `OpenAICompatibleReRankingProvider`：调用 `/rerank` API 端点，解析标准 rerank 响应格式。

## 基准测试方法论

- 使用 `time.perf_counter()` 测量各层耗时（比 `time.time()` 精度高）。
- 使用 deterministic provider 确保可重复性。
- 指标：embedding 时间、vector search 时间、keyword search 时间、hybrid search 时间、rerank 时间、全链路端到端时间。
- 优化前后对比表记录在本文件的"基准对比"节。

## Phase 0 启动校准发现

- 当前工作区从 `main` 启动，`git status -sb` 显示工作区干净。
- `phase-25-complete` 指向 `0a89d55 Complete phase 25 chitchat and SSE streaming`，这是阶段 25 最终功能提交。
- `main` 当前指向 `56f5d4 Merge phase 25 chitchat and SSE streaming`，`phase-25-complete` 是 `main` 的祖先提交，说明阶段 25 已合并到 `main`。
- 已从 `main` 创建并切换到 `codex/phase-26-retrieval-performance-reranking`。
- Planning with Files 的 `session-catchup.py` 在本机 `.claude` 路径不存在；已改为以项目根目录 `task_plan.md`、`findings.md`、`progress.md` 为准继续推进。

## Phase 1 设计文档发现

- `VectorSearchService.search()` 当前每次查询都会调用 `_list_indexed_chunks()`，从数据库 join `ChunkEmbedding`、`Chunk`、`Document`，再逐条 JSON 反序列化并调用纯 Python `cosine_similarity()`。
- `HybridSearchService.search()` 当前先执行 `KeywordSearchService.search()`，再执行 `VectorSearchService.search()`，两路召回串行且无数据依赖。
- `BrainService` 已存在 `optional_rerank` step，但它当前只按 `rerank_top_n` 截断结果，不是 Cross-Encoder 语义精排；阶段 26 需要新增独立 `ReRankingProvider`。
- 阶段 26 设计文档已新增：`docs/stage26_retrieval_performance_reranking.md`。
- 新词已沉淀到设计文档：Profiling、VectorIndexCache、numpy 向量化、ThreadPoolExecutor、Cross-Encoder、ReRankingProvider。

## Phase 2 Profiling 与基线基准

新增脚本：

- `scripts/benchmark_retrieval.py`
- 默认使用 `--provider deterministic`，避免普通基准运行或测试误触发真实 API；如需真实 provider，必须显式传参。

新增测试：

- `tests/test_benchmark_retrieval.py`
- 聚焦验证 `benchmark_query()`、`time_operation()` 和 Markdown 输出转义。

### deterministic 本地基线

命令：

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_retrieval.py --runs 1 --top-k 5 --query "What affects filling capacity in rock-filled concrete?"
```

结果：

| query | chunks | embeddings | provider | operation | runs | min_ms | mean_ms | median_ms | max_ms |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| What affects filling capacity in rock-filled concrete? | 8918 | 8918 | deterministic/hash-token-v1/dim=64 | query_embedding | 1 | 0.07 | 0.07 | 0.07 | 0.07 |
| What affects filling capacity in rock-filled concrete? | 8918 | 8918 | deterministic/hash-token-v1/dim=64 | keyword_search | 1 | 733.06 | 733.06 | 733.06 | 733.06 |
| What affects filling capacity in rock-filled concrete? | 8918 | 8918 | deterministic/hash-token-v1/dim=64 | vector_search | 1 | 1456.82 | 1456.82 | 1456.82 | 1456.82 |
| What affects filling capacity in rock-filled concrete? | 8918 | 8918 | deterministic/hash-token-v1/dim=64 | hybrid_search | 1 | 2199.56 | 2199.56 | 2199.56 | 2199.56 |
| What affects filling capacity in rock-filled concrete? | 8918 | 8918 | deterministic/hash-token-v1/dim=64 | agent_query | 1 | 2174.16 | 2174.16 | 2174.16 | 2174.16 |

结论：

- deterministic query embedding 几乎可以忽略，主要耗时在 keyword search、vector search 和 hybrid search。
- 当前 hybrid search 约等于 keyword + vector 串行相加，Phase 4 并行化有明确收益空间。
- 8918 条 deterministic embedding 下，纯 Python vector search 已达到约 1.4s；真实 1024 维 Jina 向量会更慢。

### cProfile 热点

命令：

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_retrieval.py --runs 1 --top-k 5 --query "What affects filling capacity in rock-filled concrete?" --profile
```

主要热点：

- `HybridSearchService.search()`：约 3.69s cumulative。
- `VectorSearchService.search()`：约 2.63s cumulative。
- `rank_vector_results()`：约 1.95s cumulative。
- `topic_anchor_score()`：6023 次调用，约 1.94s cumulative。
- `normalize_text()`：868445 次调用，约 1.84s cumulative。
- `cosine_similarity()`：8918 次调用，约 0.26s cumulative。
- `_list_indexed_chunks()`：约 0.19s cumulative。
- `deserialize_embedding()`：8918 次调用，约 0.15s cumulative。

关键发现：

- 原先预判的全表加载与纯 Python 余弦确实存在，但当前 profile 还暴露出 `topic_anchor_score()` 重复计算 query expansion 和 normalize 的后处理热点。
- Phase 3 仍先按计划做 `VectorIndexCache` + numpy；同时应顺手减少 `rank_vector_results()` 中每个结果重复 `expand_query_terms(query)` 的开销，否则矩阵运算加速后排序后处理会成为更明显瓶颈。

### 真实 provider 误触发记录

首次运行脚本时默认沿用 `.env` 的 OpenAI-compatible Jina provider，命令超时但已输出部分结果；该结果只作为本地观察，不作为 CI 前提，也未写入文件：

- provider：`openai-compatible/jina-embeddings-v3/dim=1024`
- chunks/embeddings：8918 / 8918
- 英文 query：query_embedding 约 5.98s，vector_search 约 10.20s，hybrid_search 约 11.86s，agent_query 约 7.77s。
- 中文 query：query_embedding 约 2.93s，vector_search 约 7.34s，hybrid_search 约 6.17s，agent_query 约 6.89s。

决策：脚本默认已改为 deterministic；真实 provider 必须显式通过 `--provider` 启用。

## Phase 3 numpy 向量化 + VectorIndexCache

新增/修改：

- `pyproject.toml` 新增 `numpy>=2.0.0`。
- 新增 `app/services/retrieval/vector_cache.py`。
- `VectorSearchService.search()` 改为使用 `VectorIndexCache.search()`。
- `VectorIndexService.build_index()` 在新增或更新 embedding 后调用 `invalidate_vector_index_cache()`。
- `rank_vector_results()` 现在每次查询只展开一次 query terms，避免每个结果重复调用 `expand_query_terms(query)`。

实现决策：

- `VectorIndexCache` 缓存 plain dataclass 元数据和 numpy 矩阵，不缓存 ORM 对象，避免 Session 生命周期污染结果。
- 全局 cache key 使用 `database_url + provider + model_name + dimension`，保证测试临时库和不同 provider/model 互不污染。
- 全局 cache 复用时更新当前 `Session` 引用；如果缓存已加载则查询不依赖 Session，如果失效后重载则使用当前请求的 Session。
- numpy 使用 `float64`，与纯 Python `cosine_similarity()` 保持 `< 1e-6` 误差。

测试：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_vector_cache.py tests\test_vector_search.py tests\test_vector_index_service.py tests\test_vector_search_api.py -q
17 passed in 4.11s
```

优化后 deterministic 基准：

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_retrieval.py --runs 1 --top-k 5 --query "What affects filling capacity in rock-filled concrete?" --profile
```

| operation | Phase 2 baseline ms | Phase 3 optimized ms | delta |
| --- | ---: | ---: | ---: |
| query_embedding | 0.07 | 0.06 | -0.01 |
| keyword_search | 733.06 | 725.64 | -7.42 |
| vector_search | 1456.82 | 335.32 | -1121.50 |
| hybrid_search | 2199.56 | 710.26 | -1489.30 |
| agent_query | 2174.16 | 685.49 | -1488.67 |

cProfile 新状态：

- `HybridSearchService.search()`：约 1.05s cumulative。
- `KeywordSearchService.search()`：约 1.03s cumulative，成为当前主热点。
- `VectorSearchService.search()`：约 0.007s cumulative（cache 已加载后）。
- `rank_vector_results()`：约 0.006s cumulative。

结论：

- numpy 矩阵化 + cache 已解决向量检索主要瓶颈。
- 后续 Phase 4 并行后，真实收益取决于 keyword 与 vector 的相对耗时；当前 cache 热状态下 vector 很快，hybrid 已接近 keyword 耗时。
- keyword search 的 `normalize_text()` / `score_match()` 已成为新热点，但不属于阶段 26 的明确核心链路，可作为后续优化候选。

## Phase 4 BM25/keyword 与 vector 并行

新增/修改：

- `HybridSearchService` 新增 `parallel: bool = True` 参数，默认并行执行。
- 并行实现使用 `ThreadPoolExecutor(max_workers=2)`。
- 每个 worker 基于当前 `db.get_bind()` 创建独立 `Session`，避免 SQLAlchemy Session 跨线程共享。
- 保留 `parallel=False` 串行路径，便于测试和排障。

测试：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_hybrid_search.py tests\test_vector_search_api.py tests\test_agent_tools.py -q
15 passed in 4.21s
```

优化后 deterministic 基准：

```text
query_embedding=0.07 ms
keyword_search=740.07 ms
vector_search=357.60 ms
hybrid_search=745.90 ms
agent_query=690.14 ms
```

对比：

| operation | Phase 3 ms | Phase 4 ms | 说明 |
| --- | ---: | ---: | --- |
| keyword_search | 725.64 | 740.07 | 正常波动 |
| vector_search | 335.32 | 357.60 | 正常波动 |
| hybrid_search | 710.26 | 745.90 | 约等于 max(keyword, vector)，不再等于 sum |
| agent_query | 685.49 | 690.14 | 保持稳定 |

结论：

- 在 cache 热状态下，vector search 已很快，hybrid 耗时被 keyword search 主导。
- 并行化仍满足阶段 26 目标：hybrid 总耗时接近较慢通道，而非两路相加。
- 后续如果真实 provider query embedding 或 cold vector cache 变慢，并行结构能避免 keyword 与 vector 继续串行叠加。

## Phase 5 Cross-Encoder 重排序层

新增/修改：

- 新增 `app/services/retrieval/reranking.py`：
  - `ReRankingProvider` Protocol
  - `ReRankResult`
  - `DeterministicReRankingProvider`
  - `OpenAICompatibleReRankingProvider`
  - `create_reranking_provider()`
- `app/core/config.py` 新增 reranking 配置：
  - `reranking_enabled`
  - `reranking_provider`
  - `reranking_model_name`
  - `reranking_api_key`
  - `reranking_base_url`
  - `reranking_timeout_seconds`
  - `reranking_recall_k`
- `HybridSearchService` 默认启用 deterministic reranking；召回 `max(top_k * 5, reranking_recall_k)` 后 rerank，再返回 top-k。
- `scripts/benchmark_retrieval.py` 新增 `rerank_only` 指标。

测试：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_reranking.py tests\test_hybrid_search.py tests\test_vector_search_api.py tests\test_answer_service.py tests\test_agent_tools.py -q
30 passed in 7.38s

.\.venv\Scripts\python.exe -m pytest tests\test_benchmark_retrieval.py tests\test_reranking.py -q
7 passed in 0.52s
```

Phase 5 基准：

```text
query_embedding=0.07 ms
keyword_search=745.35 ms
vector_search=333.17 ms
hybrid_search=733.75 ms
rerank_only=1.50 ms
agent_query=721.61 ms
```

结论：

- deterministic rerank 在 25 个左右候选上耗时约 1.5ms，对当前端到端耗时影响很小。
- hybrid search 默认启用 rerank 后仍主要由 keyword search 耗时主导。
- 真实 `OpenAICompatibleReRankingProvider` 已具备协议和解析能力，但不进入自动测试前提。
- 当前 `HybridSearchResult.score` 仍保留原 hybrid score，rerank 只改变顺序；这是为了保持 API schema 与旧测试兼容。后续如需展示 rerank score，可单独扩展响应字段和文档。

## Phase 6 端到端基准与回归验证

聚焦回归：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_vector_cache.py tests\test_vector_search.py tests\test_vector_index_service.py tests\test_hybrid_search.py tests\test_reranking.py tests\test_benchmark_retrieval.py tests\test_vector_search_api.py tests\test_answer_service.py tests\test_agent_api.py tests\test_agent_stream_api.py tests\test_chat_api.py tests\test_search_api.py tests\test_frontend_app.py tests\test_stage20_quality_report.py -q
82 passed in 20.36s
```

全量测试：

```text
.\.venv\Scripts\python.exe -m pytest -q
511 passed in 50.49s
```

最终基准：

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_retrieval.py --runs 1 --top-k 5 --query "What affects filling capacity in rock-filled concrete?" --query "堆石混凝土施工质量控制有哪些要点？"
```

| query | operation | Phase 2 baseline ms | Phase 6 final ms | delta |
| --- | --- | ---: | ---: | ---: |
| What affects filling capacity in rock-filled concrete? | query_embedding | 0.07 | 0.07 | 0.00 |
| What affects filling capacity in rock-filled concrete? | keyword_search | 733.06 | 743.59 | +10.53 |
| What affects filling capacity in rock-filled concrete? | vector_search | 1456.82 | 349.45 | -1107.37 |
| What affects filling capacity in rock-filled concrete? | hybrid_search | 2199.56 | 720.30 | -1479.26 |
| What affects filling capacity in rock-filled concrete? | rerank_only | n/a | 1.53 | n/a |
| What affects filling capacity in rock-filled concrete? | agent_query | 2174.16 | 735.48 | -1438.68 |
| 堆石混凝土施工质量控制有哪些要点？ | query_embedding | n/a | 0.05 | n/a |
| 堆石混凝土施工质量控制有哪些要点？ | keyword_search | n/a | 655.07 | n/a |
| 堆石混凝土施工质量控制有哪些要点？ | vector_search | n/a | 1.93 | n/a |
| 堆石混凝土施工质量控制有哪些要点？ | hybrid_search | n/a | 706.65 | n/a |
| 堆石混凝土施工质量控制有哪些要点？ | rerank_only | n/a | 0.88 | n/a |
| 堆石混凝土施工质量控制有哪些要点？ | agent_query | n/a | 696.88 | n/a |

浏览器/API 验证：

- 8000 端口已有旧服务占用，`/health` 可用但 `/agent/query/stream` 返回 404，判断为旧进程或未加载当前阶段代码。
- 启动当前工作区服务到 8001：`http://127.0.0.1:8001`。
- `GET /health`：200。
- `POST /agent/query/stream`，body `{"question":"thanks","top_k":2}`：返回 `token -> metadata -> done`，metadata 显示闲聊短路，不调用检索或模型。
- `POST /search/hybrid`：200。
- `GET /quality-report`：200。
- Browser desktop 1280x720：`GET /` 页面标题 `RFC RAG 工作台`。
- Browser mobile 390x844：`GET /` 页面标题 `RFC RAG 工作台`。
- 临时 8001 服务已停止。

## 数据安全边界

- numpy 向量运算仅在进程内存中进行，不写入 Git 或外部存储。
- `VectorIndexCache` 缓存的 embedding 矩阵来自已有 `ChunkEmbedding` 表，不含 API key 或敏感信息。
- `ReRankingProvider` 的 API key 和 base_url 通过环境变量配置，不硬编码、不写入 Git。
- rerank API 请求只发送 query 文本和 chunk 内容，不发送 API key 以外的凭据。

## Phase 7 文档与 Obsidian 收尾发现

已同步普通文档：
- `README.md`：补充阶段 26 当前状态、起点、关键交付、基准对比、验证结果和待核验约束。
- `docs/progress.md`：补充阶段 26 最新进展、Git/tag/main 状态、测试结果、浏览器/API 验证和下一步。
- `docs/architecture.md`：补充 `VectorIndexCache`、并行 hybrid search、`ReRankingProvider` 与 rerank 集成位置。
- `docs/data_sources.md`：补充阶段 26 不新增数据源、不写入敏感数据、benchmark 与 rerank 的数据边界。
- `AGENT.MD`：补充阶段 26 分支、缓存失效、rerank provider、benchmark 默认 deterministic、人工核验前禁止提交/tag/push 等协作规则。

已同步 Obsidian：
- 新增 `阶段 26 - 检索性能优化与重排序` 阶段页。
- 新增阶段 26 Phase 0-7 小汇报和阶段 26 Phase 汇报索引。
- 更新 `首页.md`、`阶段索引.md`、`阶段汇报索引.md`，把阶段 26 标记为等待人工核验。

最终交班边界：
- 当前阶段 26 改动尚未暂存、尚未提交、尚未创建 `phase-26-complete` tag、尚未推送。
- `phase-25-complete` tag 未移动；阶段 25 已并入 `main`，阶段 26 从该合并后的 `main` 创建分支。

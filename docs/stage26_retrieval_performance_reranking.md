# 阶段 26：检索性能优化 + Cross-Encoder 重排序

## 目标

阶段 25 已完成闲聊短路和 `/agent/query/stream` SSE 流式输出。阶段 26 聚焦阶段 25 暴露的真实大库性能风险：普通 RAG 问题在同步和流式 Agent 入口都可能超过 20 秒。判断瓶颈不在 SSE parser，而在检索管线本身。

阶段 26 的目标链路：

```text
真实大库 20s+ 响应瓶颈
-> cProfile / perf_counter 量化各层耗时
-> numpy 向量化余弦相似度
-> VectorIndexCache 进程内缓存 embedding 矩阵
-> BM25 / keyword 与 vector search 并行
-> hybrid 召回 top-20~30
-> Cross-Encoder rerank 精排
-> top-5 送 Brain / Chat / Agent
-> 端到端基准对比
```

本阶段不改变资料来源边界，不新增爬虫，不引入登录系统，不引入前端框架或 Node 构建链，不引入 `torch` / `sentence-transformers`，不让真实 API 成为 CI 或本地全量测试前提。

## 当前瓶颈

### 向量搜索全表加载

当前位置：

```text
app/services/retrieval/vector_search.py
VectorSearchService.search()
-> _list_indexed_chunks()
-> deserialize_embedding()
-> cosine_similarity()
```

当前实现每次查询都会：

- 从数据库读取所有匹配 provider/model/dimension 的 `ChunkEmbedding`。
- join `chunks` 和 `documents`，把所有候选行加载到 Python。
- 将 `embedding_json` 反序列化为 `list[float]`。
- 用纯 Python 循环逐条计算余弦相似度。

这会让每次查询重复支付数据库读取、JSON 解析和 Python 循环成本。真实大库 chunk 数量达到千级或万级后，响应时间会被 O(N) 纯 Python 扫描拖慢。

### hybrid 检索串行等待

当前位置：

```text
app/services/retrieval/hybrid_search.py
HybridSearchService.search()
-> KeywordSearchService.search()
-> VectorSearchService.search()
-> merge / normalize / rank
```

keyword/BM25 与 vector search 没有数据依赖，但当前串行执行，hybrid search 总耗时接近两者之和。本阶段会让两路召回并行执行，使总耗时更接近 `max(keyword, vector)`。

### 缺少 Cross-Encoder 精排

当前 hybrid search 主要依赖 keyword score、vector score 和 `both_match_bonus` 排序。它属于粗排：召回覆盖够用，但对候选片段和问题之间的细粒度语义匹配能力有限。

阶段 26 引入可配置重排序层：

```text
hybrid recall top-20~30
-> ReRankingProvider.rerank(query, candidates, top_k=5)
-> top-5 results
-> Brain / Chat / Agent 组装上下文
```

## numpy 向量化方案

新增依赖：

```text
numpy
```

核心替换：

```text
纯 Python:
for each embedding:
    score = cosine_similarity(query_embedding, stored_embedding)

numpy:
normalized_matrix = embeddings / norms
normalized_query = query_embedding / query_norm
scores = normalized_matrix @ normalized_query
```

向量矩阵使用 `float64`，以保证与现有纯 Python `cosine_similarity()` 的结果误差小于 `1e-6`。测试会保留纯 Python 版本作为对照基线。

## VectorIndexCache

新增模块：

```text
app/services/retrieval/vector_cache.py
```

`VectorIndexCache` 是进程内向量索引缓存。它的职责是把数据库中的 chunk embedding 一次性加载为 numpy 矩阵，并保留每一行对应的 chunk/document 元数据。

缓存内容：

- provider / model / dimension。
- `chunk_id`、`document_id`、`chunk_index`。
- chunk content、heading、document title、source type、source path、file name。
- 原始 embedding 矩阵。
- 预归一化 embedding 矩阵。

查询流程：

```text
VectorSearchService.search(query)
-> embedding_provider.embed_query(query)
-> VectorIndexCache.search(query_embedding, fetch_k)
-> 转为 VectorSearchResult
-> 继续执行 topic_anchor rank
```

缓存失效：

- `VectorIndexService` 新增或更新 embedding 后，可以调用 `invalidate()`。
- 缓存懒加载：首次查询或失效后下一次查询重新从数据库加载。
- 当前阶段先做进程内缓存，不做跨进程共享缓存；后续如部署多 worker，再单独设计启动预热和多进程一致性。

## 并行 hybrid 检索

`HybridSearchService.search()` 改为用 `ThreadPoolExecutor` 并行执行两路召回：

```text
future_keyword = executor.submit(keyword_search)
future_vector = executor.submit(vector_search)
keyword_results = future_keyword.result()
vector_results = future_vector.result()
```

线程安全边界：

- SQLAlchemy `Session` 不跨线程共享。
- 方案优先使用 `sessionmaker` 为子线程创建独立 Session；若只在主线程读取纯数据，则传入子线程的数据必须是普通 Python 对象。
- 每个 future 内部异常必须原样抛回主线程，API 行为保持可诊断。

并行只改变耗时，不改变合并算法：

```text
add keyword candidates
add vector candidates
normalize each channel by max score
keyword_weight + vector_weight + both_match_bonus
stable sort
```

## ReRankingProvider 协议

新增模块：

```text
app/services/retrieval/reranking.py
```

协议：

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
        ...
```

结果结构：

```python
@dataclass(frozen=True)
class ReRankResult:
    index: int
    score: float
    content: str
```

实现：

- `DeterministicReRankingProvider`：基于 query term overlap、标题/正文词命中等规则打分，用于本地测试和 CI。
- `OpenAICompatibleReRankingProvider`：通过 HTTP 调用兼容 rerank API，例如 Jina/Cohere/国产兼容服务。它只在用户本地配置 API key 时使用，不进入全量测试前提。
- `create_reranking_provider()`：按配置创建 provider，和现有 chat/embedding provider 的工厂函数风格一致。

真实 provider 安全要求：

- API key 只从环境变量或 `.env` 读取。
- 不把 Authorization header、Bearer token、供应商原始敏感响应写入日志、CSV、文档、测试或 Obsidian。
- 错误消息只保留 HTTP 状态和脱敏摘要。

## 集成点

默认集成到 hybrid search：

```text
HybridSearchService.search(query, top_k=5)
-> recall_k = max(top_k * 5, 20)
-> keyword + vector parallel recall
-> merge candidates
-> pre-rerank sorted candidates
-> ReRankingProvider.rerank(query, candidate.content, top_k=top_k)
-> final top_k HybridSearchResult
```

配置项建议：

```text
RERANKING_PROVIDER=deterministic | openai-compatible | none
RERANKING_MODEL=...
RERANKING_API_KEY=...
RERANKING_BASE_URL=...
RERANKING_TIMEOUT_SECONDS=30
RERANKING_ENABLED=true
RERANKING_RECALL_K=25
```

默认行为：

- 阶段 26 默认启用 deterministic reranking，保证不依赖真实 API。
- 可通过配置关闭 rerank，用于基准对比和人工排查。
- `POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`POST /agent/query/stream` 复用同一 hybrid search 行为。

## 基准脚本

新增脚本：

```text
scripts/benchmark_retrieval.py
```

测量方式：

- `time.perf_counter()`：记录关键步骤 wall-clock 时间。
- `cProfile`：生成可选函数级耗时摘要。
- deterministic provider：默认基准，不依赖真实 API。

指标：

- chunk 数量、embedding 数量、provider/model/dimension。
- query embedding 时间。
- vector search 时间。
- keyword/BM25 search 时间。
- hybrid search 时间。
- rerank 时间。
- `/agent/query` 端到端时间。

输出：

```text
baseline / optimized
query
chunk_count
vector_ms
keyword_ms
hybrid_ms
rerank_ms
agent_total_ms
notes
```

脚本可以打印 Markdown 表格，便于复制到 `findings.md` 和阶段文档。

## 测试方案

新增或更新测试：

```text
tests/test_vector_cache.py
tests/test_vector_search.py
tests/test_hybrid_search.py
tests/test_reranking.py
tests/test_benchmark_retrieval.py
```

重点断言：

- numpy 向量化得分与纯 Python `cosine_similarity()` 误差 `< 1e-6`。
- `VectorIndexCache` 首次查询加载矩阵，后续查询复用缓存。
- stale content hash 的 embedding 不进入结果。
- cache invalidate 后能重新加载新增或更新的 embedding。
- hybrid search 并行执行时结果与串行逻辑语义一致。
- deterministic reranking 可预测，并能改变候选顺序。
- `OpenAICompatibleReRankingProvider` 能解析常见 rerank 响应，不泄露 key。
- `/search`、`/search/vector`、`/search/hybrid`、`/chat`、`/agent/query`、`/agent/query/stream`、`/quality-report` 回归不破坏。

全量验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

阶段 25 基线为 `497 passed`，阶段 26 完成后测试数量应不低于该基线。

## 安全与合规边界

- 阶段 26 不新增资料来源，不新增爬虫，不公开分发受限全文。
- numpy 缓存只来自已有 `chunk_embeddings`，属于可重建索引数据。
- rerank 请求只发送 query 和候选 chunk 文本；不发送额外凭据或供应商原始响应到项目文件。
- 真实 rerank API 只作为运行时可选能力；deterministic provider 承担 CI 和本地全量测试。
- 不写入 API key、Bearer token、Authorization header、供应商原始敏感响应、受限全文到 Git、CSV、文档、测试或 Obsidian。

## 完成标准

- `docs/stage26_retrieval_performance_reranking.md` 就位。
- `scripts/benchmark_retrieval.py` 就位，并能输出优化前后基准对比。
- `pyproject.toml` 新增 `numpy`。
- `VectorIndexCache` 缓存 embedding 矩阵，避免每次查询全表加载。
- vector search 使用 numpy 矩阵运算，结果与纯 Python 版本一致，误差 `< 1e-6`。
- hybrid search 并行执行 keyword/BM25 与 vector search。
- `ReRankingProvider` Protocol、`DeterministicReRankingProvider`、`OpenAICompatibleReRankingProvider` 就位。
- hybrid search 默认启用可配置 reranking，召回 top-20~30 后精排 top-5。
- 关键 API 回归不破坏。
- 全量测试通过且不依赖真实 API。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、必要的 `AGENT.MD` 和 Obsidian 已同步。
- 最终不提交、不创建 `phase-26-complete` tag、不推送、不创建 PR，停在用户人工核验前。

## 新词解释与面试表达

- **Profiling**：性能剖析。它不是猜哪里慢，而是用 `perf_counter` 或 `cProfile` 量化每一层耗时。本项目用它定位 vector search、keyword search、hybrid merge 和 Agent 端到端耗时。
- **VectorIndexCache**：向量索引缓存。它把数据库中的 embedding 预加载为 numpy 矩阵，查询时直接矩阵乘法，不再每次从数据库全表读取和 JSON 反序列化。
- **numpy 向量化**：把 Python for 循环改成底层 C/BLAS 执行的矩阵运算。在本项目里就是用 `matrix @ query_vector` 一次算完全部 chunk 的余弦相似度。
- **ThreadPoolExecutor**：Python 标准库的线程池。本项目用它并行跑 keyword/BM25 与 vector search，减少 hybrid search 串行等待。
- **Cross-Encoder**：把 `(query, candidate)` 成对输入模型打分的重排序方法。它比 bi-encoder 向量相似度更细，但更慢，所以先粗召回 top-20~30，再精排 top-5。
- **ReRankingProvider**：重排序模型适配层。它让业务代码不绑定某一家 rerank 服务；测试用 deterministic provider，真实运行可切到 OpenAI-compatible provider。

面试表达：

```text
阶段 26 我先用 profiling 量化真实大库 20 秒响应的瓶颈，而不是凭感觉优化。定位到向量检索每次查询都会从 SQLite 读取全部 embedding，并用 Python 循环逐条算余弦，所以我引入 numpy 和 VectorIndexCache，把 embedding 常驻为归一化矩阵，查询时一次矩阵乘法得到所有相似度。随后把 hybrid search 的 keyword/BM25 与 vector search 改为并行，让总耗时接近两路较慢者，而不是两者相加。

在质量上，我没有把 top-5 直接交给 LLM，而是新增 ReRankingProvider 协议：hybrid 先召回 top-20 到 top-30，Cross-Encoder 再成对评估 query 和候选片段，精排出 top-5。测试用 deterministic reranker 保证 CI 稳定，真实 rerank API 只是可配置运行时能力，不把 API key 或供应商原始响应写入仓库。
```

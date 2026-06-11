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

## 数据安全边界

- numpy 向量运算仅在进程内存中进行，不写入 Git 或外部存储。
- `VectorIndexCache` 缓存的 embedding 矩阵来自已有 `ChunkEmbedding` 表，不含 API key 或敏感信息。
- `ReRankingProvider` 的 API key 和 base_url 通过环境变量配置，不硬编码、不写入 Git。
- rerank API 请求只发送 query 文本和 chunk 内容，不发送 API key 以外的凭据。

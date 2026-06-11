# 阶段 26 验收报告：检索性能优化 + Cross-Encoder 重排序

## 验收结论

PASS。

阶段 26 的开发范围与任务目标一致：已完成检索 profiling、`numpy` 向量化、`VectorIndexCache` 内存索引缓存、BM25/keyword 与 vector search 并行召回、`ReRankingProvider` 重排序协议、deterministic 与 OpenAI-compatible rerank provider、基准脚本、测试补充和普通文档/Obsidian 草稿收尾。验收中未发现阻断提交的问题。

本次用户已明确要求验收并提交阶段整体开发工作，因此允许进入 `git add`、commit、创建 `phase-26-complete` tag、合并到 `main` 和推送 GitHub 流程。

## 逐项核对

### 1. 范围对齐

阶段目标核对：

- 新增 `docs/stage26_retrieval_performance_reranking.md`：已完成。
- 新增 `scripts/benchmark_retrieval.py`：已完成，默认 deterministic provider，不显式传参时不触发真实 API。
- `pyproject.toml` 新增 `numpy>=2.0.0`：已完成。
- `VectorIndexCache` 缓存 embedding 矩阵：已完成，位于 `app/services/retrieval/vector_cache.py`。
- numpy 矩阵运算替代纯 Python 逐条余弦：已完成，`VectorSearchService` 默认使用缓存矩阵检索。
- BM25/keyword 与 vector search 并行：已完成，`HybridSearchService` 默认使用 `ThreadPoolExecutor`，worker 使用独立 SQLAlchemy Session。
- `ReRankingProvider` Protocol：已完成，包含 `DeterministicReRankingProvider` 和 `OpenAICompatibleReRankingProvider`。
- hybrid search 默认启用 rerank：已完成，可通过配置或构造参数关闭。
- 保持 `/search`、`/search/vector`、`/search/hybrid`、`/chat`、`/agent/query`、`/agent/query/stream`、`/quality-report` 兼容：已通过聚焦测试和 HTTP 验证。

范围边界核对：

- 未做登录系统。
- 未做部署优化。
- 未引入 `torch` / `sentence-transformers`。
- 未引入前端框架或 Node 构建链。
- 未让真实 API 成为测试或基准默认前提。

### 2. 性能与基准

阶段 26 开发记录中的主要基准对比：

```text
English query: What affects filling capacity in rock-filled concrete?
vector_search: 1456.82 ms -> 349.45 ms
hybrid_search: 2199.56 ms -> 720.30 ms
agent_query: 2174.16 ms -> 735.48 ms
rerank_only: 1.53 ms
```

本次验收复跑基准：

```text
.\.venv\Scripts\python.exe scripts\benchmark_retrieval.py --runs 1 --top-k 5 --query "What affects filling capacity in rock-filled concrete?"

query_embedding: 0.07 ms
keyword_search: 868.78 ms
vector_search: 391.29 ms
hybrid_search: 830.75 ms
rerank_only: 1.89 ms
agent_query: 778.36 ms
```

验收判断：

- `vector_search` 相比优化前仍保持约 3-4 倍改善。
- `hybrid_search` 仍接近当前较慢的 keyword 通道，而不是 keyword + vector 串行相加。
- deterministic rerank 成本约 1-2ms，不构成当前端到端瓶颈。
- 当前主要剩余耗时在 keyword/BM25 通道，适合作为后续优化候选。

### 3. 测试证据

阶段开发期间记录的全量测试：

```text
.\.venv\Scripts\python.exe -m pytest -q
511 passed in 50.49s
```

本次验收聚焦回归：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_vector_cache.py tests\test_reranking.py tests\test_hybrid_search.py tests\test_agent_stream_api.py tests\test_chat_model_provider.py -q
40 passed in 7.06s
```

最终提交前全量测试：

```text
.\.venv\Scripts\python.exe -m pytest -q
511 passed in 58.33s
```

### 4. SSE 流式输出复查

用户验收前反馈“流式输出没有了，又变成生成完整后一次性回答”。本次验收做了单独复查。

过程与结论：

- 发现 8000 端口曾有旧 uvicorn 进程残留；已停止旧进程，并从当前阶段 26 工作区重新启动服务。
- 当前只保留一个监听 8000 的服务实例，`GET /health` 返回正常。
- 使用正确 UTF-8/Unicode 转义请求 `POST /agent/query/stream`：

```text
question=谢谢
first_elapsed_ms=19.61
first_event=event: token | data: {"text":"不客气。"}
has_metadata=True
has_done=True

question=thanks
first_elapsed_ms=2.91
first_event=event: token | data: {"text":"不客气。"}
has_metadata=True
has_done=True
```

验收判断：

- 当前代码中的 SSE 服务端流式能力未丢失。
- 闲聊短路路径会先发 `token`，再发 `metadata` 和 `done`。
- 之前异常现象更可能来自旧服务进程或命令行中文编码损坏，不是阶段 26 代码破坏 `/agent/query/stream`。

### 5. 安全合规

核对结果：

- `scripts/benchmark_retrieval.py` 默认 deterministic provider，真实 provider 需要显式传参。
- 新增 rerank provider 不在测试中调用真实 API。
- 代码和文档未写入 API key、Bearer token、Authorization header 或供应商原始敏感响应。
- `VectorIndexCache` 仅缓存已有 `chunk_embeddings` 数据的内存矩阵，不新增外部持久化副本。
- OpenAI-compatible rerank 和 chat provider 的错误处理不应向前端暴露凭据。

### 6. 文档同步

已同步：

- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage26_retrieval_performance_reranking.md`
- `AGENT.MD`
- 根目录 `task_plan.md`、`findings.md`、`progress.md`
- 本地 Obsidian 阶段 26 草稿和 Phase 0-7 汇报

本次验收新增：

- `docs/phase_reviews/phase-26.md`

### 7. 提交边界

提交前状态：

- 分支：`codex/phase-26-retrieval-performance-reranking`
- 起点：`main -> 56f5d4 Merge phase 25 chitchat and SSE streaming`
- `phase-25-complete -> 0a89d55 Complete phase 25 chitchat and SSE streaming`
- `phase-26-complete`：提交前不存在
- 用户已明确要求验收、提交、上传并 merge 至 GitHub

允许动作：

- stage 阶段 26 相关代码、测试、普通文档和验收报告。
- 创建阶段最终功能提交。
- 创建 `phase-26-complete` tag，指向阶段 26 最终功能提交。
- 推送阶段分支和 tag。
- 合并到 `main` 并推送 GitHub。

不提交内容：

- `obsidian-vault/` 本地知识库文件仍按项目规则保持本地 only。
- `.claude/`、`.codex/`、临时浏览器缓存、运行日志等本地工具文件不进入 Git。

## 改进建议

1. 后续阶段可以优化 keyword/BM25 通道。阶段 26 后 vector search 已显著变快，当前 deterministic/cache 热状态下主要耗时转移到 keyword search。
2. 若未来 chunk 数量增长到数万级，可再评估 FAISS、HNSW、Qdrant 或 PGVector。当前千级/万级以内用 numpy 矩阵乘法更轻量。
3. 如果真实 rerank API 接入生产路径，需要补充网络超时、降级策略、成本记录和质量评测，不应直接替换 deterministic 默认测试链路。
4. 前端如继续反馈“看起来没有流式”，应优先确认浏览器连接的是当前 8000 服务，并检查是否存在代理、旧 uvicorn 进程或浏览器缓存。

## 面试表达

阶段 26 我先用 profiling 定位真实瓶颈，再做低风险优化。原来 vector search 每次都从 SQLite 全表读取 embedding，并用 Python 循环逐条计算余弦；我引入 `VectorIndexCache` 和 numpy，把 embedding 预加载成归一化矩阵，查询时一次矩阵乘法得到全部相似度。随后把 hybrid search 的 keyword/BM25 和 vector 两路召回改成线程池并行，让耗时接近较慢通道而不是两者相加。最后新增 `ReRankingProvider` 协议，把 rerank 作为召回后的精排层，默认 deterministic 可测，真实 OpenAI-compatible rerank 作为运行时可选能力。整个阶段保持旧 API 兼容、SSE 不回归、真实 API 不进入 CI 前提。

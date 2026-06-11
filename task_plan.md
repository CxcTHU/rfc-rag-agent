# 阶段 26 任务计划：检索性能优化 + Cross-Encoder 重排序

## 目标

在阶段 25「闲聊短路 + SSE 流式输出」已完成并合并到 `main` 的基础上，完成阶段 26「检索性能优化 + Cross-Encoder 重排序」：诊断并修复当前真实大库 20 秒以上响应时间的性能瓶颈，引入 numpy 向量化加速余弦相似度计算、内存向量索引缓存、BM25 与向量检索并行执行，以及 Cross-Encoder 重排序层（召回 top-20→精排 top-5）。阶段完成后停在用户人工核验前，不提交、不打 tag、不推送。

## 硬约束

- 阶段 26 开发完成前后均不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
- 不移动任何已有阶段 tag，尤其是 `phase-25-complete`。
- 保留用户或其他 session 的已有改动，不重置 Git，不覆盖无关文件。
- 不做用户认证/登录系统。
- 不引入前端框架（React/Vue）或 Node 构建链。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`POST /agent/query/stream`、`GET /quality-report` 不被破坏。
- `ReRankingProvider` 必须同时提供 `DeterministicReRankingProvider`（测试）和 `OpenAICompatibleReRankingProvider`（真实 API），真实 API 不进入 CI 前提。
- 新增 `numpy` 依赖可接受；不引入 `torch` / `sentence-transformers` 等重量级依赖。

## Phase 顺序

### Phase 0：启动校准与文件计划

**状态：已完成**

**解决的问题**：确认阶段 25 的最终状态、tag、main 起点和阶段 26 分支，避免在错误基线上继续开发。

**RAG 链路位置**：阶段起点校准，不改运行链路。

**为什么现在做**：阶段 26 依赖阶段 25 的 SSE 流式输出和闲聊短路，必须先确认已进入 `main`。

**任务**
- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读阶段 25 设计文档、phase review，以及根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 核对 `phase-25-complete` tag 指向阶段 25 最终功能提交，不要移动任何已有阶段 tag。必须核对阶段 25 是否已合并到 main。
- 从阶段 25 完成并合并后的 main 状态出发，创建或切换到 `codex/phase-26-retrieval-performance-reranking`。
- 将根目录三份 Planning with Files 文件校准为阶段 26。

**验证方式**
- `git status -sb`
- `git log --oneline -5`
- `git merge-base --is-ancestor phase-25-complete main`

**完成标准**
- 当前分支为 `codex/phase-26-retrieval-performance-reranking`。
- `phase-25-complete -> 0a89d55 Complete phase 25 chitchat and SSE streaming`，未移动，且已并入 `main`。
- `main -> 56f5d4 Merge phase 25 chitchat and SSE streaming`，阶段 26 从该合并点创建分支。
- `task_plan.md`、`findings.md`、`progress.md` 已切换并校准为阶段 26。

### Phase 1：阶段 26 设计文档

**状态：已完成**

**解决的问题**：把性能优化和重排序的设计先固化成可审查合同。

**RAG 链路位置**：横跨检索层、向量搜索、混合搜索和 Provider 层。

**为什么现在做**：先明确性能基线测量方法、numpy 迁移范围、重排序 Provider 协议和并行策略，后续代码实现可以对齐。

**任务**
- 新增 `docs/stage26_retrieval_performance_reranking.md`。
- 说明当前瓶颈：`VectorSearchService._list_indexed_chunks()` 加载全表到 Python 内存，纯 Python 逐条计算余弦相似度。
- 说明 numpy 向量化加速方案：用 `numpy.dot` 和矩阵运算替代纯 Python 循环。
- 说明内存向量索引缓存：启动时一次性加载 embedding 矩阵到内存，后续查询直接矩阵乘法。
- 说明 BM25 与向量检索并行执行方案（`concurrent.futures.ThreadPoolExecutor`）。
- 说明 `ReRankingProvider` Protocol 设计：`rerank(query, candidates) -> list[ReRankResult]`。
- 说明 Cross-Encoder 集成点：hybrid search 之后、送 LLM 之前。
- 说明基准测试方法论：profiling 脚本、优化前后对比指标。
- 说明安全边界和完成标准。

**验证方式**
- 人工阅读文档结构是否覆盖阶段 26 验收项。

**完成标准**
- `docs/stage26_retrieval_performance_reranking.md` 已新增，覆盖 profiling、numpy 加速、缓存、并行、重排序、测试、安全与收尾标准。

### Phase 2：Profiling 与基线基准

**状态：已完成**

**解决的问题**：量化当前检索管线每层耗时，建立优化前基线。

**RAG 链路位置**：检索管线全链路（embedding → vector search → keyword search → hybrid merge → LLM 生成）。

**为什么现在做**：优化前必须有可量化的基线，否则无法衡量改进幅度。

**任务**
- 新增 `scripts/benchmark_retrieval.py`，使用 `time.perf_counter` 和 `cProfile` 测量：
  - query embedding 计算时间
  - vector search（全表加载 + 逐条余弦）时间
  - keyword search（BM25）时间
  - hybrid search 总时间
  - 完整 agent query 端到端时间
- 用 deterministic provider 跑基准，记录 chunk 数量和各层耗时。
- 如有真实数据库，额外记录真实大库基线。
- 将基线数据写入 `findings.md`。

**验证方式**
- 基准脚本可运行，输出各层耗时。

**完成标准**
- 新增 `scripts/benchmark_retrieval.py`，默认 deterministic provider，不显式传参时不触发真实 API。
- 新增 `tests/test_benchmark_retrieval.py` 覆盖脚本核心函数。
- 基线数据已记录在 `findings.md`，各层耗时可用于优化后对比。

### Phase 3：numpy 向量化 + 内存索引缓存

**状态：已完成**

**解决的问题**：当前 `VectorSearchService` 用纯 Python 循环逐条计算余弦相似度，且每次查询都从数据库全量加载 embedding，极慢。

**RAG 链路位置**：`app/services/retrieval/vector_search.py`、`app/services/retrieval/embedding.py`。

**为什么现在做**：这是 20s+ 响应时间的最大单一瓶颈。

**任务**
- `pyproject.toml` 新增 `numpy` 依赖。
- 新增 `app/services/retrieval/vector_cache.py`：`VectorIndexCache` 类，启动时从数据库加载全部 embedding 到 numpy 矩阵，提供 `search(query_embedding, top_k) -> list[(chunk_id, score)]`。
- 重构 `VectorSearchService.search()`：不再每次查询调用 `_list_indexed_chunks()`，改用 `VectorIndexCache` 的矩阵运算。
- 余弦相似度改用 numpy 向量化：`scores = normalized_matrix @ query_vector`。
- 缓存支持增量刷新：新增 chunk embedding 后可以 `cache.invalidate()` 触发重新加载。
- 保留 `cosine_similarity()` 纯 Python 版本供单元测试对比。
- 补充测试。

**验证方式**
- 运行基准脚本对比优化前后 vector search 耗时。
- 运行全量 vector search 相关测试。

**完成标准**
- `pyproject.toml` 已新增 `numpy>=2.0.0`。
- 新增 `app/services/retrieval/vector_cache.py`，`VectorIndexCache` 使用 numpy 归一化矩阵缓存 embedding。
- `VectorSearchService.search()` 已改为通过 cache 执行矩阵相似度，并保留纯 Python `cosine_similarity()` 供测试对比。
- `VectorIndexService.build_index()` 在新增或更新 embedding 后自动 invalidate cache。
- vector search 基线从约 1456.82ms 降至约 335.32ms，结果与纯 Python 版本误差 `< 1e-6`。

### Phase 4：BM25 与向量检索并行执行

**状态：已完成**

**解决的问题**：当前 `HybridSearchService.search()` 串行执行 keyword search 和 vector search，总耗时是两者之和。

**RAG 链路位置**：`app/services/retrieval/hybrid_search.py`。

**为什么现在做**：Phase 3 加速了 vector search 后，hybrid search 的串行等待成为新的低垂果实。

**任务**
- 在 `HybridSearchService.search()` 中使用 `concurrent.futures.ThreadPoolExecutor` 并行执行 keyword search 和 vector search。
- 并行策略：两个检索任务独立无状态依赖，可以安全并发。
- SQLAlchemy `Session` 在多线程中需要注意：每个线程使用独立 Session 或在主线程完成 DB 操作后再并发计算。
- 补充测试。

**验证方式**
- 运行基准脚本对比并行前后 hybrid search 耗时。
- 全量 hybrid search 相关测试通过。

**完成标准**
- `HybridSearchService.search()` 默认使用 `ThreadPoolExecutor` 并行执行 keyword 与 vector 两路召回。
- 每个 worker 使用独立 SQLAlchemy Session，不跨线程共享请求 Session。
- hybrid search 耗时约 745.90ms，接近 keyword 740.07ms 与 vector 357.60ms 的较大者。

### Phase 5：Cross-Encoder 重排序层

**状态：已完成**

**解决的问题**：当前召回结果只靠 BM25 和向量相似度打分，缺少语义精排。

**RAG 链路位置**：hybrid search 之后、Brain/AgentService 组装上下文之前。

**为什么现在做**：Phases 3-4 加速了检索管线，为新增重排序步骤腾出了时间预算。

**任务**
- 新增 `app/services/retrieval/reranking.py`：
  - `ReRankingProvider` Protocol：`rerank(query: str, candidates: list[str], top_k: int) -> list[ReRankResult]`。
  - `DeterministicReRankingProvider`：基于 keyword overlap 评分，用于测试。
  - `OpenAICompatibleReRankingProvider`：调用 re-rank API（Cohere/Jina/国产兼容）。
  - `create_reranking_provider()` 工厂函数。
- 新增 `ReRankResult` dataclass：`index`、`score`、`content`。
- 在 `HybridSearchService` 或 Brain workflow 中集成重排序：召回 top-20~30 → re-rank → 返回 top-5。
- 配置项：`RERANKING_PROVIDER`、`RERANKING_MODEL`、`RERANKING_API_KEY`、`RERANKING_BASE_URL`。
- 补充测试（deterministic reranking provider、集成到 hybrid search）。

**验证方式**
- deterministic reranking 测试通过。
- hybrid search + reranking 测试通过。
- 基准脚本显示重排序后端到端质量提升（deterministic 下可验证排序变化）。

**完成标准**
- 新增 `app/services/retrieval/reranking.py`，包含 `ReRankingProvider` Protocol、`ReRankResult`、`DeterministicReRankingProvider`、`OpenAICompatibleReRankingProvider` 和 `create_reranking_provider()`。
- `HybridSearchService` 默认启用 deterministic reranking，可通过 `reranking_enabled=False` 或配置关闭。
- hybrid search 召回扩大到 top-20~30 后执行 rerank，再返回 top-k。
- 真实 rerank API 仅作为可配置运行时能力，不进入 CI 前提。

### Phase 6：端到端基准测试与回归验证

**状态：已完成**

**解决的问题**：需要确认优化后全链路响应时间下降、既有功能未被破坏。

**RAG 链路位置**：全链路回归。

**为什么现在做**：功能开发完成后必须先测试，再进入文档收尾。

**任务**
- 运行基准脚本，对比优化前后各层耗时。
- 运行全量测试，目标 >= 497（阶段 25 基线）。
- 用浏览器桌面/移动视口检查 SSE 流式输出和检索速度改善。
- 记录基准对比表到 `findings.md`。

**验证方式**
- `pytest` 全量测试。
- 基准对比数据完整。
- 浏览器验证。

**完成标准**
- 全量测试通过：`511 passed in 50.49s`，且不依赖真实 API。
- 基准对比表已记录到 `findings.md`。
- 8001 当前代码服务验证 `/agent/query/stream`、`/search/hybrid`、`/quality-report` 可用，桌面/移动页面加载正常。

### Phase 7：文档同步、Obsidian 收尾与人工核验待提交状态

**状态：已完成**

**解决的问题**：把阶段 26 的设计、代码行为同步到项目文档和 Obsidian，并停在可核验状态。

**RAG 链路位置**：项目知识层和阶段交付边界。

**为什么现在做**：测试通过后文档才能准确描述最终行为。

**任务**
- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 必要时更新 `AGENT.MD`。
- 建立或更新 Obsidian 阶段 26 目录、汇报索引和各 Phase 小汇报。
- 确认未创建 `phase-26-complete` tag。
- 汇总主要改动、测试结果、未提交状态和人工核验重点。

**验证方式**
- `git status -sb`
- `git tag --list phase-26-complete`
- 文档无过期表述。

**完成标准**
- 当前分支保持阶段 26 分支。
- 所有阶段 26 改动未提交，等待用户人工核验。
- `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD` 已同步阶段 26 行为和约束。
- Obsidian 已新增阶段 26 阶段页、Phase 0-7 小汇报和阶段汇报索引，并更新首页/阶段索引/阶段汇报索引。
- 已确认未创建 `phase-26-complete` tag，且未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

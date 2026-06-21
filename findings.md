# 阶段 50 Findings：LangGraph Agent 编排与 Redis 全栈缓存层

## 阶段 49 基线确认

- Git 基线: `main` / `origin/main` = `0671a31b Merge pull request #14 from CxcTHU/codex/phase-49-local-postgresql-cloud-sync`
- 当前分支: `codex/phase-50-langgraph-redis`
- `phase-49-complete` annotated tag → `a044ce0c Complete phase 49 local PostgreSQL cloud sync`
- pytest: 1037 passed → Phase 0-9 后 1082 passed
- Stage 30: 91.52 / A / pass

## Phase 0-9 Findings（Codex 完成，已验收）

### Redis 连接工厂
- `RedisClientFactory` 实现 create → ping → fallback None 三步
- Redis 不可用时返回 None，调用者据此决定 fallback 策略

### Redis Embedding 缓存
- `RedisQueryEmbeddingCache` key 格式：`emb:{provider}:{model}:{dimension}:{sha256(normalized_query)}`
- 精确匹配 key（不是语义匹配），同一 query 二次查询跳过 embedding API
- Redis 错误时 fallback 到内存 `QueryEmbeddingCache`

### LangGraph StateGraph
- `LangGraphAgentState` TypedDict 定义 Agent 全状态
- 10 个 node 全部复用 `AgentToolbox`，通过 `ContextVar` 注入避免序列化问题
- 条件路由通过 `route_after_planner` → `next_action_from_state` 实现
- `LangGraphAgentService.query()` 返回与 `ReActAgentService` 相同的 `AgentQueryResult`

### Checkpointer 现状问题（Phase 10 修复目标）
- 代码写了 `RedisSaver`，但 `redis:7-alpine` 没有 RedisJSON/RediSearch 模块
- 运行时 `RedisSaver.setup()` 调用 RedisJSON 命令失败 → except → 返回 MemorySaver
- **实际效果：checkpointer 用的是内存，Redis 没起作用**
- 解决方案：换用 `redis/redis-stack-server`

### API 集成
- `mode="langgraph_agent"` 接入 `/agent/query` 和 `/agent/query/stream`
- SSE 事件格式完全兼容

## Phase 10-14 设计决策（待开发）

### Phase 10：redis-stack 决策点
- `redis/redis-stack-server:latest` 自带 RedisJSON 2.6 + RediSearch 2.10
- 不用 `redis/redis-stack`（含 RedisInsight UI 占用 8001 端口），dev/prod 都用 stack-server 纯 CLI 版
- `RedisSaver.setup()` 会创建 RediSearch 索引；需确认 `langgraph-checkpoint-redis>=0.4.1` 与 redis-stack 兼容

### Phase 11：Semantic Cache 设计
- **与 embedding cache 的区别**：embedding cache 缓存 embedding 向量（省 embedding API 调用），semantic cache 缓存**整个 Agent 回答**（省 LLM + 检索全流程）
- 利用 RediSearch 的 `VECTOR` 字段做 KNN 搜索
- 相似度阈值 0.92（cosine）；太低返回不相关缓存，太高几乎不命中
- 缓存内容：query、answer、sources、citations、mode、timestamp — 不缓存敏感信息
- TTL 1 小时（可配），面试时展开讲缓存失效策略

### Phase 12：Rate Limiting 算法选型
- 选 **ZSET 滑动窗口**：面试最能展开（令牌桶 vs 漏桶 vs 固定窗口 vs 滑动窗口）
- 只限 `/agent/query` 和 `/agent/query/stream`（LLM 调用昂贵），不限轻量端点
- client 标识用 IP（无登录系统）
- Redis 不可用时 fail-open（放行），不因 Redis 故障拖垮服务
- 响应头：`X-RateLimit-Limit`、`X-RateLimit-Remaining`、`X-RateLimit-Reset`

### Phase 14：pgvector HNSW 迁移设计

#### 当前向量检索链路（待改造）
- embedding 存储：`chunk_embeddings.embedding_json` TEXT 列，JSON 序列化的 float list
- 检索：进程内 FAISS `IndexFlatIP`（暴力内积），从 `data/faiss/*.index` 文件加载到内存
- 问题 1：O(n) 全量扫描，40000 vectors × 2048 dim 目前可接受，但扩展性差
- 问题 2：每个 worker 进程各自加载一份完整向量矩阵，内存浪费
- 问题 3：已迁移到 PostgreSQL 但向量检索仍走文件系统，架构割裂

#### pgvector + HNSW 方案
- PostgreSQL 镜像需支持 pgvector 扩展：`pgvector/pgvector:pg16` 或在现有 `postgres:16` 中安装
- `chunk_embeddings` 表新增 `embedding_vector` 列（`Vector(2048)` 类型），与 `embedding_json` 并存
- Alembic 迁移填充：`UPDATE chunk_embeddings SET embedding_vector = embedding_json::vector`（PostgreSQL 原生 cast）
- HNSW 索引参数：`m=16`（每层连接数）、`ef_construction=200`（构建精度）— 默认参数适用于 40k-100k 级数据
- 运行时参数：`SET hnsw.ef_search = 100`（检索精度，值越大 recall 越高但越慢）
- SQL 查询：`SELECT ... ORDER BY embedding_vector <=> $query_vector LIMIT $top_k`（cosine distance）

#### HNSW vs IVFFlat 选型
- **HNSW**：recall 更高（>95% @ top-10）、不需要训练（IVFFlat 需要 `CREATE INDEX` 时 k-means）、增量插入友好
- **IVFFlat**：构建更快、内存更省，但 recall 不如 HNSW，需要定期 `REINDEX`
- 选 HNSW：数据量 40k 不大，HNSW 构建成本可接受，面试讲解价值更高

#### Fallback 策略
- `pgvector_search_enabled` 默认 False，需显式开启
- pgvector 扩展不可用（如 SQLite fallback 环境）时自动走 FAISS
- 保留 FAISS 代码和 `data/faiss/` 目录，不删除
## Phase 14 Findings（2026-06-21）

- 文档采用顶部追加最新状态块，避免破坏旧中文内容在终端显示编码噪声的历史记录。
- `.env.example` / `.env.dev.example` 只写默认关闭和示例配置，不包含真实 secret。
- Obsidian Phase 10-14 每篇均包含目标、任务、修改内容、关键模块、问题、术语、验证、遗留问题、下一 Phase、面试表达。
- 最终验证后仍保持 `1093 passed, 1 skipped`；阶段状态为等待用户人工核验。

## Phase 13 Findings（2026-06-21）

- 全量回归从 Phase 0-9 的 1082 baseline 增至 1093 passed / 1 skipped，新增测试覆盖 redis-stack checkpointer、Semantic Cache 与 Rate Limiting。
- Stage 30 仍为 `91.52 / A / pass`，本阶段未改变评分权重、默认 provider、检索策略或外部数据源。
- RedisSaver 真实集成测试通过，说明 redis-stack-server + JSON 原生 LangGraph state 可以跨进程持久化 checkpoint。
- Semantic Cache 真实 KNN 路径由 Redis 命令封装与聚焦测试覆盖；它默认关闭，不作为 CI/全量测试前提。
- Rate Limiting 由 FakeRedis ZSET 单测覆盖滑动窗口与 fail-open；不要求真实 Redis 成为本地全量测试前提。
- Docker Compose prod config 需要 `.env.prod` 与必填 secret 参与插值；验证使用临时占位，未写入仓库。

## Phase 12 Findings（2026-06-21）

- Rate Limiting 采用 Redis `ZSET` 滑动窗口：每个请求以 timestamp 为 score 写入集合，先清理窗口外记录，再用 `ZCARD` 判断是否超限。
- 作用范围只覆盖 `/agent/query` 与 `/agent/query/stream`，因为这两个端点可能触发检索与 LLM 成本；轻量查询端点不受影响。
- 响应头契约：成功与 429 都带 `X-RateLimit-Limit`、`X-RateLimit-Remaining`、`X-RateLimit-Reset`，方便前端或调用方做退避。
- 关键可靠性决策：Redis 不可用时 fail-open，而不是 fail-closed；主问答服务可用性优先于限流严格性。
- 面试表达：ZSET sliding window 比固定窗口更平滑，避免分钟边界瞬时双倍请求；比令牌桶更容易在 Redis 中解释和验证。

## Phase 11 Findings（2026-06-21）

- Semantic Cache 与 Query Embedding Cache 的边界已落实：Query Embedding Cache 只缓存 embedding 向量，Semantic Cache 缓存完整 Agent answer/sources/citations/mode。
- Redis 数据结构：Hash 保存 payload 与 FLOAT32 embedding BLOB；RediSearch `FT.SEARCH ... KNN` 返回 cosine distance，代码按 `similarity = 1 - distance` 与阈值比较。
- 关键保守策略：只缓存无 conversation/history/source_id/image_path 的普通问答，避免不同上下文或限定来源下误命中。
- 安全边界：不缓存 tool_calls、search_results、供应商原始响应、API key、Bearer token 或受限全文；sources 只使用 API response 已允许返回的 source DTO。
- fallback 决策：任何 Redis/RediSearch/解码异常都返回 miss/skip，不阻断 Agent 正常执行。
- 面试表达：Semantic Cache 是“答案级缓存”。它用 query embedding 做近邻搜索，命中高相似历史问题时直接返回已验证答案，节省检索和 LLM 调用；与精确 embedding cache 互补。

## Phase 10 Findings（2026-06-21）

- Redis Stack：`redis/redis-stack-server:latest` 在本机 dev compose 下健康启动，`MODULE LIST` 返回 `search` 与 `ReJSON`，满足 RedisSaver 与后续 Semantic Cache 的 RediSearch/RedisJSON 前提。
- Checkpointer 修复：`RedisSaver.setup()` 已能在 Redis Stack 下成功；真实集成测试确认 `create_graph_checkpointer(...).backend == "redis"`，并能通过 LangGraph graph invoke 写入 checkpoint。
- 关键问题：RedisSaver 默认 JSON serializer 会尝试序列化 LangGraph state 中的 `ReActObservation`、`ReActStepRecord`、`AgentToolCallRecord` 等 Python dataclass，触发 serializer 版本边界问题。
- 关键决策：不引入 pickle fallback；改为让 LangGraph checkpoint state 保存 JSON 原生 `dict/list/str/int/float/bool/null`，在 `LangGraphAgentService` 返回前反序列化为原有 API DTO。
- 面试表达：Checkpoint state 是 Agent 每一步可恢复的运行状态。我们把“内部可持久化状态”和“外部 API 返回对象”解耦，让 Redis 层不依赖 Python 私有对象序列化，提升跨进程恢复和后续运维可解释性。
## Phase 16 设计决策：LangGraph Planner 接入快模型

### 动机
- 当前 `route_query_node` 使用 `DeterministicReActPlanner` 硬编码规则路由，灵活性有限
- 主模型 DeepSeek-v4-Pro 是推理模型，每次 tool calling 会生成大量 thinking token，延迟高
- 架构优化：用快模型（如 DeepSeek-v4-flash）做路由决策，强模型（Pro）只做最终回答生成
- 这是"Flash 做规划 + Pro 做生成"的分层架构，类似 Cursor/Perplexity 的工程实践

### 技术方案
- `route_query_node` 检查 ContextVar 中是否有 planner_chat_provider：
  - **有**：用 planner 快模型做 LLM 路由（输入问题 + 工具列表 + observations → 输出 JSON action）
  - **无**：保持现有 `DeterministicReActPlanner` 规则路由，行为零变化
- planner LLM prompt 设计：给出可选工具列表和描述，要求返回 JSON `{"action": "...", "query": "...", "reasoning_summary": "..."}`
- 解析失败时 fallback 到 `DeterministicReActPlanner`，保证鲁棒性
- `LangGraphAgentService` 通过 ContextVar 传入 planner provider，与现有 toolbox ContextVar 模式一致
- `latency_trace` 记录 planner 模型和延迟，方便对比 planner LLM vs 规则路由的性能差异

### 关键约束
- `generate_answer_node` 不变——最终回答仍用主 chat_model_provider（Pro）
- 不改变 `react_agent`、`tool_calling_agent`、`default` 模式的任何行为
- planner 未配置时零开销，与 Phase 0-15 行为完全一致
- planner LLM 不接触 embedding、不做检索，只做 action 选择
- 面试表达："路由层用轻量快模型做意图判断，生成层用强模型保证答案质量；两层解耦让我们可以独立优化路由延迟和答案质量"

## Phase 14 启动 Findings（2026-06-21）

- 当前向量数据已经随 Phase 49 进入 PostgreSQL，但在线检索仍主要依赖 `data/faiss/*.index` 文件和进程内 FAISS `IndexFlatIP`，数据库与检索索引生命周期分离。
- pgvector HNSW 的目标不是改变 embedding 生成流程，而是把已有 GLM-Embedding-3 / 2048 维向量同步到 `chunk_embeddings.embedding_vector`，再用 PostgreSQL 原生 `<=>` cosine distance 查询。
- 本轮必须保留 FAISS 作为 fallback：SQLite 测试、本地未启用 pgvector、PostgreSQL 未安装扩展或配置未开启时，都不能阻断现有检索。
- 新词解释：HNSW 是 Hierarchical Navigable Small World，近似最近邻图索引；在本项目中用于替代 FAISS 暴力全量扫描，面试可表述为“把向量索引放回数据库，减少文件索引同步与多进程内存重复加载问题”。
## Phase 50 Semantic Cache Stream 修正 Findings（2026-06-21）

- 运行实测发现：前端默认走 `/agent/query/stream`，而 Phase 11 的 Semantic Cache 初版只接入同步 `/agent/query`；因此 UI 重复提问仍会重新执行 Agent tool calls。
- 配置边界：`SEMANTIC_CACHE_ENABLED` 按阶段安全约束默认 `false`，本地人工测试需要在 `.env` 显式设置为 `true` 并重启服务。
- 修正决策：stream 路径现在会先查 Semantic Cache，命中时通过 SSE 输出 cached answer、metadata 和 done，不再执行 Agent；miss 后正常执行 Agent 并写入缓存。
- 会话内安全放宽：原规则只允许无 `conversation_id`、无 history 的请求缓存；现在额外允许“同一 conversation 内最后一条 user message 与当前问题完全相同”的重复请求命中缓存，避免普通追问误用旧答案。
- 测试口径：开启缓存后，历史未缓存的回答不会自动补入；用户需要先问一次让缓存写入，再问相同问题才会命中。

## Phase 15 收尾 Findings（2026-06-21）

- 回归结果：全量 pytest 当前为 `1100 passed, 1 skipped`，比 Phase 13 基线增加 7 个 pgvector focused tests；Stage 30 仍为 `91.52/A/pass`。
- Compose 验证：dev compose 直接通过；prod compose 因安全规则不提交 `.env.prod`，使用临时占位 `.env.prod` 展开配置，验证后立即删除。
- 文档策略：不重写历史阶段段落，只在目标文档顶部追加 Phase 14-15 最新状态，避免破坏早期阶段记录。
- Obsidian 策略：保留旧 `Phase 14 - 文档与 Obsidian 收尾.md`，新增本次真实 Phase 14 pgvector 和 Phase 15 收尾两篇小汇报，索引置顶补链。
- 人工核验重点：启用 `PGVECTOR_SEARCH_ENABLED=true` 后，对真实 PostgreSQL pgvector HNSW 召回质量和延迟做抽样；默认关闭保证上线前不改变现有行为。

## Phase 14 pgvector HNSW Findings（2026-06-21 完成）

- 当前割裂点：embedding 已在 PostgreSQL 的 `chunk_embeddings.embedding_json` 保存，但向量检索仍优先依赖 `data/faiss/*.index` 文件；pgvector 迁移把向量列与 HNSW 索引放回数据库，降低部署时文件索引漂移风险。
- HNSW：Hierarchical Navigable Small World，近似最近邻图索引；本项目在 `embedding_vector vector_cosine_ops` 上使用 `m=16, ef_construction=200` 创建索引，运行时用 `hnsw_ef_search=100` 控制搜索精度/耗时。
- 运行实测修正：pgvector 的 `vector` HNSW 索引最多支持 2000 维，而 GLM-Embedding-3 是 2048 维；因此保留 `embedding_vector Vector(2048)` 列，但 HNSW 索引改为 `(embedding_vector::halfvec(2048)) halfvec_cosine_ops` 表达式索引，查询侧同步用 halfvec cosine distance。
- pgvector 搜索开关默认关闭：`pgvector_search_enabled=False`，因此现有 `react_agent`、`default`、`langgraph_agent` 和 CI SQLite 测试默认仍走 FAISS/numpy fallback。
- 维度决策：生产 GLM-Embedding-3 为 2048 维，`embedding_vector` 固定 `Vector(2048)`；测试或临时低维 embedding 不写入向量列，避免 PostgreSQL 固定维度列报错。
- SQL 决策：`pgvector_search.py` 使用 `<=>` cosine distance，按距离升序排序，业务层将分数换算为 `1 - distance` 后继续复用原 `VectorSearchResult` 和 topic anchor rerank。
- Fallback 决策：非 PostgreSQL、配置关闭、维度非 2048、DB 查询异常时，`VectorSearchService` 返回原 FAISS/numpy 路径；`latency_trace.vector_search_backend` 用于核验实际 backend。
- 安全边界：迁移和测试只处理向量数值、chunk 元数据和安全文档，不写入 API key、Bearer token、供应商原始响应或受限全文。
## Semantic Cache Stream 与隔离最终修正（2026-06-21）

- `/agent/query/stream` 已接入 Semantic Cache lookup/store；命中时通过 SSE 输出 cached answer、metadata 和 done，不再执行 Agent。
- 同一会话内只允许“最后一条 user message 与当前问题完全相同”的重复请求命中缓存，避免普通追问误用旧答案。
- Semantic Cache payload/key 增加 `cache_context`（当前数据库 URL 的安全哈希）以及 embedding provider/model/dimension 校验，避免本地 PostgreSQL、测试 SQLite 或不同 embedding provider 串缓存。
- Redis KNN 从 1 个候选改为最多 5 个候选，遇到旧格式、mode/provider/context 不匹配的缓存会跳过继续看下一个候选。
- 本地 `.env` 已启用 `SEMANTIC_CACHE_ENABLED=true`；旧 `semcache:*` 和 `idx:semcache` 已清空，用户需要先问一次写入新格式缓存，再问完全相同问题验证命中。

## Phase 16 启动 Findings（2026-06-21）

- Phase 0-15 已完成：LangGraph Agent、Redis embedding cache、RedisSaver Checkpointer、Semantic Cache、Rate Limiting、pgvector HNSW 均已落地；基线为 `1100 passed, 1 skipped`，Stage 30 `91.52/A/pass`。
- 本 Phase 只改 LangGraph 路由层：planner 快模型负责把问题和已有 observations 映射为 `ReActAction`，最终 `answer_with_citations` 仍由主 `chat_model_provider`（Pro）执行。
- ContextVar 是合适的注入方式：LangGraph checkpoint state 保持 JSON 原生可序列化，runtime-only 的 planner provider 不进入 Redis checkpoint。
- planner provider 未配置时必须仍走 `DeterministicReActPlanner`，并在 latency trace 中记录 `planner_model=deterministic`、`planner_latency_ms=0`。

## Phase 16 完成 Findings（2026-06-21）

- `route_query_node` 已接入 `_CURRENT_PLANNER_PROVIDER`：仅在非图片、非表格硬规则分支使用 planner LLM；图片上传、表格问题和表格 evidence 后续路由仍保持确定性。
- planner prompt 只包含 action 名称、简短工具描述、当前问题和最近 observations 摘要，不包含 API key、内部 secret、供应商 raw response 或 hidden thought。
- planner JSON 解析失败、action payload 不合法、provider 异常时会记录 fallback 类型并回到 `DeterministicReActPlanner`；未配置 planner 时不调用模型。
- `LangGraphAgentService` 通过 ContextVar 注入并在 `finally` 中 reset planner provider，避免跨请求串用快模型。
- `latency_trace.planner_model` 用于区分 `deterministic` 与 `provider/model`；`planner_latency_ms` 只累计 planner LLM 调用时间。
- 额外修复：`refuse_node` 现在把 `ReActStepRecord` 序列化为 dict 后写回 LangGraph state，避免 RedisSaver 在拒答路径尝试序列化 dataclass。
- 聚焦回归：`tests/test_phase50_langgraph_planner.py`、LangGraph nodes/builder、Agent API/SSE、Semantic Cache 共 `69 passed`。

## Phase 17 完成 Findings（2026-06-21）

- 全量回归从 Phase 15 的 `1100 passed, 1 skipped` 增至 `1106 passed, 1 skipped`，新增 6 个 planner focused tests。
- Stage 30 保持 `91.52/A/pass`，说明 planner 快模型接入没有改变质量评分、默认 provider、检索策略或外部数据源。
- Compose 验证：dev config 直接通过；prod config 因 `.env.prod` gitignored，使用临时占位文件与进程级占位环境变量完成展开校验，随后删除。
- 文档策略：在 README、AGENT.MD、docs 顶部追加 Phase 16-17 最新状态，保留历史阶段记录。
- 环境模板策略：`PLANNER_CHAT_MODEL_*` 默认留空并只给示例注释；真实 API key 仍只能放本地 `.env` / `.env.prod`。
- 人工核验重点：配置真实 fast planner 后，对比 `latency_trace.planner_model`、`planner_latency_ms` 与最终回答质量，确认 Flash 路由 + Pro 生成的实际收益。
## Semantic Cache standalone eligibility finding (2026-06-21)
- Root cause of similar-question misses: the Redis semantic cache itself was not the first failure point. Requests inside a conversation were filtered by `semantic_cache_request_is_eligible()` unless the current query exactly matched the last user message, so similar standalone questions never reached RediSearch KNN lookup.
- Decision: allow standalone RFC/domain questions inside a conversation to use semantic cache lookup, while continuing to block contextual follow-ups with pronouns or continuation markers. This preserves the safety goal of avoiding cross-context answer reuse while making answer-level semantic cache useful for normal rephrased questions.
- Interview phrasing: Semantic Cache is an answer-level cache, but its eligibility gate matters as much as vector similarity. We separate standalone domain questions from context-dependent follow-ups before doing Redis KNN, so cache hits save Agent/LLM cost without leaking stale conversational context.

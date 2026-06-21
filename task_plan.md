# 阶段 50 任务计划：LangGraph Agent 编排与 Redis 全栈缓存层

## Goal

将当前手写的 ReAct Agent 循环重构为 LangGraph 声明式状态图，引入 Redis 作为**语义缓存（Semantic Cache）、API 限流（Rate Limiting）、query embedding 缓存、Agent 状态检查点（Checkpointer）**四大能力的后端，保持 Stage 30、pytest、前端行为和现有 API 契约不退化。

## Current Phase

Phase 16-17 追加：在 Phase 0-15 已完成的 LangGraph + Redis + pgvector 基础上，为 LangGraph `route_query_node` 接入可选 planner 快模型，并完成回归验证与文档收尾。

## 前置条件

- Phase 0-9（LangGraph 重构 + 基础 Redis embedding 缓存 + Checkpointer 代码框架）已完成
- pytest 1082 passed，Stage 30 91.52/A/pass
- 已有 `redis:7-alpine` 容器，但不支持 RedisJSON/RediSearch，导致 Checkpointer 实际 fallback 到 MemorySaver
- 已有 `RedisQueryEmbeddingCache`（精确匹配 key，非语义）
- 无 Rate Limiting
- 无 Semantic Cache

## 已完成 Phases（Phase 0-9，由 Codex 完成）

### Phase 0：启动校准 — [x] 完成
### Phase 1：Redis 容器与连接基础 — [x] 完成
### Phase 2：Redis Query Embedding 缓存 — [x] 完成
### Phase 3：LangGraph 依赖引入与状态定义 — [x] 完成
### Phase 4：LangGraph 图构建与条件路由 — [x] 完成
### Phase 5：Redis Checkpointer 集成（代码框架） — [x] 完成
### Phase 6：API 集成与模式切换 — [x] 完成
### Phase 7：回归验证与性能对比 — [x] 完成
### Phase 8：云端部署准备 — [x] 完成
### Phase 9：文档 + Obsidian 收尾（初版） — [x] 完成

## 新增 Phases（Phase 10-14）

### Phase 10：Redis Stack 升级与 Checkpointer 修复

- [ ] `docker-compose.dev.yml` 镜像从 `redis:7-alpine` 改为 `redis/redis-stack-server:latest`（自带 RedisJSON + RediSearch）
- [ ] `docker-compose.prod.yml` 同步升级
- [ ] 验证 `RedisSaver` 在 redis-stack 下 `setup()` 成功，checkpointer 不再 fallback 到 MemorySaver
- [ ] 验证 checkpoint 写入/读取/TTL 清理/恢复（真实 Redis，非 mock）
- [ ] `app/core/config.py` 如需新增配置项（如 `redis_stack_modules` 检测）
- [ ] 聚焦测试：RedisSaver 集成、fallback 路径保持（Redis 不可用时仍 MemorySaver）

### Phase 11：Semantic Cache（语义缓存）

- [ ] 新增 `app/services/cache/semantic_cache.py`
- [ ] 利用 RediSearch 的向量索引能力：将 query embedding 存入 Redis Hash + 向量索引，同时存储对应的完整 Agent 回答
- [ ] key 结构：`semcache:{sha256(normalized_query)}` → Hash 含 `embedding` (BLOB)、`answer` (JSON)、`mode`、`created_at`
- [ ] RediSearch 索引：`idx:semcache` on Hash prefix `semcache:` with VECTOR field
- [ ] 查询时：对 query 做 embedding → RediSearch KNN 搜索 → 相似度 > 阈值（默认 0.92）返回缓存回答
- [ ] 命中时跳过整个 Agent/检索/LLM 流程，直接返回缓存结果
- [ ] `app/core/config.py` 新增 `semantic_cache_enabled`（默认 False）、`semantic_cache_similarity_threshold`（默认 0.92）、`semantic_cache_ttl_seconds`（默认 3600）
- [ ] `app/api/agent.py` 在 Agent 调用前查 semantic cache，命中直接返回
- [ ] `latency_trace` 新增 `semantic_cache_hit`、`semantic_cache_similarity` 字段
- [ ] Redis 不可用或 RediSearch 不支持时 graceful skip
- [ ] 聚焦测试：命中/未命中/相似度阈值/TTL 过期/fallback

### Phase 12：Rate Limiting（API 限流中间件）

- [ ] 新增 `app/middleware/rate_limit.py`
- [ ] 算法：Redis `ZSET` 滑动窗口限流
  - key: `ratelimit:{client_ip}:{endpoint}`
  - member: 请求 timestamp（毫秒精度）
  - score: 同 member
  - 每次请求：`ZREMRANGEBYSCORE` 清理窗口外记录 → `ZCARD` 计数 → 超限返回 429 → 未超限 `ZADD` 当前时间
- [ ] `app/core/config.py` 新增 `rate_limit_enabled`（默认 False）、`rate_limit_requests_per_minute`（默认 30）、`rate_limit_window_seconds`（默认 60）
- [ ] 限流只作用于 `/agent/query` 和 `/agent/query/stream`，不影响 `/search`、`/chat` 等轻量端点
- [ ] 返回 `429 Too Many Requests`，响应头包含 `X-RateLimit-Limit`、`X-RateLimit-Remaining`、`X-RateLimit-Reset`
- [ ] Redis 不可用时 graceful skip（不限流），不阻断正常请求
- [ ] 聚焦测试：滑动窗口行为、窗口滑动后恢复、429 响应格式、Redis 不可用时放行

### Phase 13：全栈回归验证

- [ ] 全量 pytest，确认不退化（基线 1082）
- [ ] Stage 30 评分，确认 91.52/A/pass
- [ ] 验证四大 Redis 能力：
  - Embedding 缓存命中（已有，确认不被破坏）
  - Checkpointer 真实写入 Redis（redis-stack 下不再 fallback）
  - Semantic Cache 命中/未命中路径
  - Rate Limiting 429 + 放行路径
- [ ] LangGraph vs ReAct 对比评测不退化
- [ ] 浏览器 smoke
- [ ] Docker Compose dev + prod config 验证

### Phase 14：pgvector HNSW 向量索引迁移

- [ ] `docker-compose.dev.yml` 和 `docker-compose.prod.yml` 的 PostgreSQL 镜像确认支持 pgvector 扩展（`pgvector/pgvector:pg16` 或在现有镜像中 `CREATE EXTENSION vector`）
- [ ] Alembic 迁移：`chunk_embeddings` 表新增 `embedding_vector` 列（`pgvector.sqlalchemy.Vector(2048)` 类型），从现有 `embedding_json` TEXT 列批量转换填充
- [ ] Alembic 迁移：在 `embedding_vector` 列上创建 HNSW 索引（`CREATE INDEX ... USING hnsw (embedding_vector vector_cosine_ops) WITH (m=16, ef_construction=200)`）
- [ ] `app/db/models.py` 的 `ChunkEmbedding` 新增 `embedding_vector` mapped column
- [ ] 新增 `app/services/retrieval/pgvector_search.py`：基于 pgvector 的向量搜索实现，SQL 使用 `<=>` cosine distance 操作符 + `ORDER BY ... LIMIT top_k`
- [ ] `VectorSearchService` 新增 pgvector 搜索路径：当 PostgreSQL 启用 pgvector 时优先走数据库向量搜索，否则 fallback 到现有 FAISS
- [ ] `app/core/config.py` 新增 `pgvector_search_enabled`（默认 False）、`hnsw_ef_search`（默认 100，运行时搜索精度参数）
- [ ] 保留现有 FAISS 文件索引代码和 `data/faiss/` 目录作为 fallback
- [ ] `latency_trace` 新增 `vector_search_backend`（`pgvector_hnsw` / `faiss`）字段
- [ ] 聚焦测试：pgvector 搜索结果与 FAISS 的 recall 对比、HNSW 索引创建/查询、fallback 路径
- [ ] 不改变现有 embedding 生成流程（GLM-Embedding-3 / dim=2048），只改检索路径

### Phase 15：全栈回归验证与文档收尾

- [ ] 全量 pytest，确认不退化
- [ ] Stage 30 评分，确认 91.52/A/pass
- [ ] 验证 pgvector HNSW 搜索结果质量不劣于 FAISS
- [ ] Docker Compose dev + prod config 验证
- [ ] 更新 README、docs/progress.md、docs/architecture.md、AGENT.MD、deployment_guide.md、phase-50.md
- [ ] Obsidian：新增 Phase 14-15 小汇报，更新阶段 50 汇报索引
- [ ] 停在用户人工核验前状态

### Phase 16：LangGraph Planner 接入快模型（Flash 路由 + Pro 生成）

- [x] `app/services/agent/graph_nodes.py` 的 `route_query_node` 改造：当 `planner_chat_model_provider` 已配置时，用 planner 快模型（如 DeepSeek-v4-flash）做 LLM 路由决策，替代 `DeterministicReActPlanner` 硬编码规则
- [x] planner LLM 输入：当前问题 + 可选工具列表（search_knowledge / search_figures / search_tables / analyze_user_image / rewrite_query / answer_with_citations / refuse）+ observations 摘要 → 输出：选一个 action
- [x] planner LLM 输出解析：JSON `{"action": "search_knowledge", "query": "...", "reasoning_summary": "..."}` + fallback（解析失败时走 `DeterministicReActPlanner`）
- [x] `LangGraphAgentService.__init__` 接收可选 `planner_chat_provider: ChatModelProvider | None`，通过 ContextVar 传入 `route_query_node`
- [x] `app/api/agent.py` 的 `langgraph_agent` 模式调用点传入 `planner_chat_provider`（已有 Depends 注入）
- [x] `planner_chat_model_provider` 未配置时保持现有 `DeterministicReActPlanner` 兜底，行为零变化
- [x] `latency_trace` 新增 `planner_model`（记录 planner provider/model 或 "deterministic"）和 `planner_latency_ms` 字段
- [x] 聚焦测试：planner LLM mock 返回合法/非法 JSON、ContextVar 注入、fallback 到规则路由
- [x] 不改变 `generate_answer_node`——最终回答仍用主模型（Pro）

### Phase 17：全栈回归验证与文档收尾

- [x] 全量 pytest，确认不退化
- [x] Stage 30 评分，确认 91.52/A/pass
- [x] Docker Compose dev + prod config 验证
- [x] 更新 README、docs/progress.md、docs/architecture.md、AGENT.MD、deployment_guide.md、phase-50.md
- [x] `.env.example` / `.env.dev.example` 补充 planner 模型配置示例
- [x] Obsidian：新增 Phase 16-17 小汇报
- [x] 停在用户人工核验前状态

## 安全边界

- Stage 30 必须保持 91.52/A/pass 或不退化
- 不把 `.env.prod`、JWT secret、数据库密码、SSH 密码、API key、Bearer token、供应商原始响应写入 Git/CSV/文档/测试/Obsidian
- `.env.dev.example` 只包含示例值，不含真实密码
- 未经用户人工核验，不 git add/commit/tag/push/建 PR
- 现有 react_agent / default / tool_calling_agent 模式保持不变
- Redis 不可用时所有新功能必须 graceful fallback/skip，不能让 Redis 成为硬依赖
- 不删除现有 ReAct 实现代码，保持向后兼容
- 不让真实 API 成为 CI 或本地全量测试前提
- Semantic Cache 默认关闭（`semantic_cache_enabled=False`），需显式开启
- Rate Limiting 默认关闭（`rate_limit_enabled=False`），需显式开启

## 完成标准

- `docker-compose.dev.yml` 和 `docker-compose.prod.yml` 使用 `redis/redis-stack-server`，支持 RedisJSON + RediSearch
- Redis query embedding 缓存工作正常（已有，不退化）
- LangGraph Checkpointer 真实使用 RedisSaver 持久化到 Redis（不再 fallback 到 MemorySaver）
- Semantic Cache：query 语义相似度 > 阈值时命中缓存，跳过 Agent 全流程；TTL 过期自动失效
- Rate Limiting：`/agent/query` 滑动窗口限流，超限返回 429 + 标准响应头
- Redis 不可用时所有功能 graceful fallback，不阻断服务
- pgvector HNSW 索引：`chunk_embeddings.embedding_vector` 列 + HNSW 索引，cosine distance 搜索替代 FAISS 暴力扫描
- pgvector 不可用时 fallback 到现有 FAISS 文件索引
- 全量 pytest 通过，Stage 30 保持 91.52/A/pass
- 现有 react_agent / default 模式完全不受影响
- README、docs、AGENT.MD、Obsidian 同步完成
- 最终停在未 `git add`、未提交、未 tag、未 push、未 PR 的人工核验前状态
## Phase 14 完成更新（2026-06-21）

- [x] README、AGENT.MD、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/deployment_guide.md、docs/phase_reviews/phase-50.md 已更新 Phase 10-14 状态。
- [x] `.env.example` 与 `.env.dev.example` 已补充 Redis Stack、Semantic Cache、Rate Limiting 配置项。
- [x] Obsidian 阶段 50 Phase 10-14 小汇报已新增，阶段 50 索引、阶段页、阶段汇报索引已更新。
- [x] 文档/配置聚焦测试：29 passed。
- [x] 最终全量 pytest：1093 passed, 1 skipped。
- [x] 停在未 `git add`、未 commit、未 tag、未 push、未 PR 的人工核验前状态。

## Phase 13 完成更新（2026-06-21）

- [x] 全量 pytest：`1093 passed, 1 skipped`。
- [x] Stage 30：`overall=91.52 grade=A release_decision=pass`。
- [x] LangGraph vs ReAct：`langgraph_agent errors=0 same_refusal=6/6 same_top_source=5/6 decision=parallel_candidate`。
- [x] Docker Compose：dev config 通过；prod config 使用临时 `.env.prod` 与进程级占位 secret 验证通过，验证后已删除临时文件。
- [x] Redis 四项能力聚焦验证：`tests/test_phase50_embedding_cache.py`、`tests/test_phase50_redis_stack_checkpointer.py`、`tests/test_phase50_semantic_cache.py`、`tests/test_phase50_rate_limit.py`，结果 `19 passed`。
- [x] 真实 Redis Stack 下 RedisSaver checkpoint backend=`redis`，不再 fallback 到 `MemorySaver`。
- [x] Semantic Cache 与 Rate Limiting 均默认关闭，Redis 不可用时 graceful skip/fail-open。

## Phase 12 完成更新（2026-06-21）

- [x] 新增 `app/middleware/rate_limit.py`，实现 Redis ZSET sliding window rate limiter。
- [x] `app/core/config.py` 新增 `rate_limit_enabled=False`、`rate_limit_requests_per_minute=30`、`rate_limit_window_seconds=60`。
- [x] `app/main.py` 接入 `RateLimitMiddleware`，默认关闭时不影响现有请求。
- [x] 仅限制 `/agent/query` 与 `/agent/query/stream`，不限制 `/search` 等其他路径。
- [x] 超限返回 `429` 与 `X-RateLimit-Limit`、`X-RateLimit-Remaining`、`X-RateLimit-Reset`。
- [x] Redis 未配置、不可用或执行异常时 fail-open 放行。
- [x] 聚焦验证：`python -m pytest tests/test_phase50_rate_limit.py -q`，结果 `5 passed`。

## Phase 11 完成更新（2026-06-21）

- [x] 新增 `app/services/cache/semantic_cache.py`，基于 Redis Stack RediSearch `VECTOR FLAT` 索引实现语义缓存。
- [x] 缓存 key 为 `semcache:{sha256(normalized_query)}`，Hash 中保存 `query`、`answer`、`sources`、`citations`、`mode`、`created_at` 与 query embedding BLOB。
- [x] `app/core/config.py` 新增 `semantic_cache_enabled=False`、`semantic_cache_similarity_threshold=0.92`、`semantic_cache_ttl_seconds=3600`。
- [x] `/agent/query` 在 Agent 调用前检查 Semantic Cache；命中时直接返回缓存 answer，跳过 Agent 全流程。
- [x] 命中 response 的 `latency_trace` 包含 `semantic_cache_hit=True` 与 `semantic_cache_similarity`；未命中正常 Agent response 会补 `semantic_cache_hit=False`。
- [x] Redis 不可用、RediSearch 不支持、索引创建失败、payload 解码失败时 graceful skip。
- [x] 仅对无会话历史、无图片、无 `source_id` 的普通问答启用，避免上下文缓存误用。
- [x] 聚焦验证：`python -m pytest tests/test_phase50_semantic_cache.py tests/test_phase50_embedding_cache.py tests/test_agent_api.py::test_agent_api_explicit_langgraph_agent_mode_uses_graph_service tests/test_agent_stream_api.py::test_agent_stream_api_supports_langgraph_agent_mode -q`，结果 `15 passed`。

## Phase 10 完成更新（2026-06-21）

- [x] `docker-compose.dev.yml` 与 `docker-compose.prod.yml` 已从 `redis:7-alpine` 升级到 `redis/redis-stack-server:latest`。
- [x] dev/prod compose 配置已验证；prod 需要部署环境提供 `.env.prod` 与必填 secret 占位。
- [x] Redis Stack 容器实测健康，模块包含 `search` 与 `ReJSON`。
- [x] 修复 LangGraph checkpoint state 的 Redis 序列化边界：节点内部保存 JSON 原生 dict，服务输出仍还原为既有 `AgentQueryResult` dataclass 契约。
- [x] 真实 Redis Stack 下 `RedisSaver.setup()` 成功，LangGraph checkpoint 写入 Redis，backend=`redis`，不再 fallback 到 `MemorySaver`。
- [x] Redis 不可用或未配置时仍保留 `MemorySaver` fallback。
- [x] 聚焦验证：`python -m pytest tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_graph_checkpointer.py tests/test_phase50_redis_foundation.py tests/test_stage44_deployment.py tests/test_phase50_redis_stack_checkpointer.py -q`，结果 `35 passed`。
## Phase 15 全栈回归验证与文档收尾完成更新（2026-06-21）

- [x] 全量 pytest：`1100 passed, 1 skipped`。
- [x] Stage 30：`overall=91.52 grade=A release_decision=pass`。
- [x] Docker Compose：dev config 通过；prod config 使用临时占位 `.env.prod` 验证通过，验证后已删除临时文件。
- [x] 普通文档：`README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/deployment_guide.md`、`docs/phase_reviews/phase-50.md` 已补充 pgvector HNSW 收尾状态。
- [x] 环境模板：`.env.example`、`.env.dev.example` 已补充 `PGVECTOR_SEARCH_ENABLED=false` 和 `HNSW_EF_SEARCH=100`。
- [x] Obsidian：新增 `Phase 14 - pgvector HNSW 向量索引迁移.md`、`Phase 15 - 全栈回归验证与文档收尾.md`，并更新阶段 50 汇报索引、阶段页、阶段汇报索引。
- [x] 最终状态：未 `git add`、未 commit、未 tag、未 push、未 PR，等待用户人工核验。

## Phase 14 pgvector HNSW 迁移完成更新（2026-06-21）

- [x] `docker-compose.dev.yml` 与 `docker-compose.prod.yml` 的 PostgreSQL 镜像已改为 `pgvector/pgvector:pg16`，Redis Stack 配置保持不变。
- [x] 新增 Alembic 迁移 `20260621_0007_pgvector_hnsw.py`：PostgreSQL 环境下创建 `vector` 扩展、增加 `chunk_embeddings.embedding_vector Vector(2048)`、从 `embedding_json` 回填 2048 维历史向量、创建 HNSW cosine 索引。
- [x] `ChunkEmbedding` 新增 `embedding_vector` mapped column；`ChunkEmbeddingRepository.save_embedding()` 对 2048 维 embedding 同步写入向量列，低维测试 embedding 保持 JSON/FAISS fallback。
- [x] 新增 `app/services/retrieval/pgvector_search.py`：基于 `<=>` cosine distance 执行 PostgreSQL pgvector 检索，支持 `hnsw.ef_search`。
- [x] `VectorSearchService` 增加 pgvector 优先路径：`pgvector_search_enabled=True` 且 PostgreSQL + 2048 维可用时走 `pgvector_hnsw`，否则 fallback 到现有 FAISS/numpy 路径。
- [x] `app/core/config.py` 新增 `pgvector_search_enabled=False`、`hnsw_ef_search=100`，默认不改变现有检索行为。
- [x] `latency_trace` 新增 `vector_search_backend`，记录 `pgvector_hnsw` 或 `faiss`。
- [x] Focused tests：`python -m pytest tests/test_phase50_pgvector_hnsw.py tests/test_vector_search.py tests/test_vector_cache.py tests/test_phase49_local_postgres_dev.py tests/test_stage44_deployment.py -q`，结果 `25 passed`。
- [x] 保留 FAISS 文件索引实现与 `data/faiss/` fallback；不新增外部数据源；不让真实 API 成为测试前提。

## Phase 17 全栈回归验证与文档收尾完成更新（2026-06-21）

- [x] Phase 16 focused regression：`69 passed`。
- [x] 全量 pytest：`1106 passed, 1 skipped`。
- [x] Stage 30：`overall=91.52 grade=A release_decision=pass`。
- [x] Docker Compose：dev config 直接通过；prod config 使用临时占位 `.env.prod` 与进程级占位 secret 通过，验证后已删除临时文件。
- [x] 普通文档：README、AGENT.MD、docs/progress、docs/architecture、docs/data_sources、docs/deployment_guide、docs/phase_reviews/phase-50 已补充 planner 快模型收尾状态。
- [x] 环境模板：`.env.example` 与 `.env.dev.example` 已补充 `PLANNER_CHAT_MODEL_*` 示例注释。
- [x] Obsidian：新增 Phase 16-17 小汇报，并更新阶段 50 汇报索引、阶段页、阶段汇报索引。
- [x] 最终状态：未 `git add`、未 commit、未 tag、未 push、未 PR，等待用户人工核验。

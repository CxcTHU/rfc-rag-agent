# 阶段 50 Session Progress

## 阶段信息

- 阶段: 50 — LangGraph Agent 编排与 Redis 全栈缓存层
- 分支: `codex/phase-50-langgraph-redis`
- 基线: `main` / `origin/main` = `0671a31b Merge pull request #14`
- 基线 tag: `phase-49-complete` -> `a044ce0c`
- 基线 pytest: 1037 passed
- 基线 Stage 30: 91.52 / A / pass

## Phase 0-9（Codex 完成，Claude 已验收 PASS）

- Phase 0-9 完成 LangGraph Agent 编排 + 基础 Redis embedding 缓存 + Checkpointer 代码框架
- pytest: 1082 passed（+45）
- Stage 30: 91.52 / A / pass
- 已知问题：Checkpointer 因 redis:7-alpine 缺少 RedisJSON/RediSearch，实际 fallback 到 MemorySaver
- 已知问题：无 Semantic Cache、无 Rate Limiting

## Phase 10-14（待开发：补齐 Redis 全栈能力）

### Phase 10：Redis Stack 升级与 Checkpointer 修复 — 完成
### Phase 11：Semantic Cache（语义缓存） — 完成
### Phase 12：Rate Limiting（API 限流中间件） — 完成
### Phase 13：全栈回归验证 — 完成
### Phase 14：pgvector HNSW 向量索引迁移 — 完成
### Phase 15：全栈回归验证与文档收尾 — 完成
### Phase 16：LangGraph Planner 接入快模型（Flash 路由 + Pro 生成） — 完成
### Phase 17：全栈回归验证与文档收尾 — 完成

提交状态：尚未 `git add`，尚未 commit/tag/push/PR。

## Phase 16 启动日志：LangGraph Planner 接入快模型（2026-06-21）

- 已确认继续沿用 `codex/phase-50-langgraph-redis`，未新建分支。
- 已阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、task_plan.md、findings.md、progress.md。
- `git status -sb` 显示 Phase 50 既有大量未提交/未跟踪改动；本轮只在其上增量修改，不重置、不清理。
- 已确认 Phase 0-15 完成状态：全量 pytest `1100 passed, 1 skipped`，Stage 30 `91.52/A/pass`，LangGraph Agent、Redis 四项能力和 pgvector HNSW 可用。
- 本 Phase 目标：让 `route_query_node` 在配置 planner provider 时使用快模型做 action 选择；未配置时保持确定性规则路由零变化。
- 提交状态：尚未 `git add`，尚未 commit/tag/push/PR。

## Phase 16 完成日志：LangGraph Planner 接入快模型（2026-06-21）

- 新增 `_CURRENT_PLANNER_PROVIDER` ContextVar 与 set/reset helper；`LangGraphAgentService` 支持 `planner_chat_provider` 注入。
- `route_query_node` 在确定性图片/表格规则之后调用 planner LLM；planner 返回合法 JSON 时转换为 `ReActAction`，解析失败或 provider 异常时 fallback 到 `DeterministicReActPlanner`。
- `/agent/query` 与 `/agent/query/stream` 的 `langgraph_agent` 调用点已传入 `planner_chat_provider`；`react_agent`、`tool_calling_agent`、`default` 行为未改。
- `latency_trace` 增加 `planner_model` 默认值，保留已有 `planner_latency_ms`。
- 补充 `tests/test_phase50_langgraph_planner.py`，覆盖合法 JSON、非法 JSON fallback、provider None、ContextVar 注入/reset。
- 修复 `refuse_node` workflow step 序列化，避免 RedisSaver 拒答路径 dataclass 序列化风险。
- 验证：`python -m pytest tests/test_phase50_langgraph_planner.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_phase50_semantic_cache.py -q` -> `69 passed`。
- 提交状态：尚未 `git add`，尚未 commit/tag/push/PR。

## Phase 17 启动日志：全栈回归验证与文档收尾（2026-06-21）

- 本 Phase 解决 Phase 16 变更后的整体不退化验证、部署配置校验、普通文档更新和 Obsidian 草稿补齐。
- 在 RAG 链路中的位置：不新增 runtime 能力，负责把 planner 快模型路由的验证结果、配置示例和架构说明同步到项目文档。
- 计划验证：全量 pytest、Stage 30、dev/prod Docker Compose config。
- 提交状态：尚未 `git add`，尚未 commit/tag/push/PR。

## Phase 17 完成日志：全栈回归验证与文档收尾（2026-06-21）

- 全量测试：`python -m pytest -q` -> `1106 passed, 1 skipped`。
- Stage 30：`python scripts/score_stage30_quality.py` -> `overall=91.52 grade=A release_decision=pass`。
- Compose：`docker compose -f docker-compose.dev.yml config --quiet` 通过；`docker compose -f docker-compose.prod.yml config --quiet` 使用临时占位 `.env.prod` 与进程级占位变量通过，临时文件已删除。
- 普通文档：README、AGENT.MD、docs/progress、docs/architecture、docs/data_sources、docs/deployment_guide、docs/phase_reviews/phase-50、环境模板已更新。
- Obsidian：Phase 16-17 小汇报与阶段索引已补齐。
- 最终状态：Phase 50 Phase 16-17 已完成并停在人工核验前；尚未 `git add`、未 commit、未 tag、未 push、未 PR。

---

## Phase 0-9 详细日志（保留供参考）

### Phase 0 日志：启动校准
时间：2026-06-21
- 已确认阶段 49 合并到 main，phase-49-complete tag 存在且未移动
- 从 main 创建 codex/phase-50-langgraph-redis

### Phase 1 日志：Redis 容器与连接基础
时间：2026-06-21
- docker-compose.dev.yml 新增 Redis 7 容器
- 新增 RedisClientFactory，Redis 不可用时返回 None
- 验证：8 passed

### Phase 2 日志：Redis Query Embedding 缓存
时间：2026-06-21
- 新增 RedisQueryEmbeddingCache，key=emb:{provider}:{model}:{dim}:{sha256}
- Redis 不可用时 fallback 内存缓存
- 验证：19 passed

### Phase 3 日志：LangGraph 依赖引入与状态定义
时间：2026-06-21
- 新增 graph_state.py + graph_nodes.py，10 个 node 复用 AgentToolbox
- 验证：16 passed

### Phase 4 日志：LangGraph 图构建与条件路由
时间：2026-06-21
- 新增 graph_builder.py + LangGraphAgentService
- StateGraph 条件路由覆盖全部 8 种 action
- 验证：13 passed

### Phase 5 日志：Redis Checkpointer 集成
时间：2026-06-21
- 新增 graph_checkpointer.py，RedisSaver → MemorySaver fallback
- 发现 redis:7-alpine 不支持 RedisSaver（缺 RedisJSON/RediSearch）
- 验证：12 passed

### Phase 6 日志：API 集成与模式切换
时间：2026-06-21
- mode="langgraph_agent" 接入 /agent/query + /agent/query/stream
- SSE 事件格式保持兼容
- 验证：43 passed

### Phase 7 日志：回归验证与性能对比
时间：2026-06-21
- 全量 pytest 1082 passed，Stage 30 91.52/A/pass
- LangGraph vs ReAct 对比：errors=0, same_refusal=6/6, same_top_source=5/6

### Phase 8 日志：云端部署准备
时间：2026-06-21
- docker-compose.prod.yml 新增 Redis，部署文档更新

### Phase 9 日志：文档 + Obsidian 收尾
时间：2026-06-21
- 文档、Obsidian 同步完成
- 最终验证：1082 passed，91.52/A/pass
## Phase 14 日志：文档更新与 Obsidian 收尾
时间：2026-06-21
- 更新 README、AGENT.MD、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/deployment_guide.md、docs/phase_reviews/phase-50.md。
- 更新 `.env.example` 与 `.env.dev.example`，补充 Semantic Cache 与 Rate Limiting 默认关闭配置。
- 新增 Obsidian Phase 10-14 小汇报，更新阶段 50 汇报索引、阶段页和阶段汇报索引。
- 文档/配置聚焦测试：29 passed。
- 最终全量 pytest：1093 passed, 1 skipped。
- 最终状态：尚未 `git add`，尚未 commit/tag/push/PR，等待用户人工核验。

## Phase 13 日志：全栈回归验证
时间：2026-06-21
- 全量 pytest：1093 passed, 1 skipped。
- Stage 30：overall=91.52 grade=A release_decision=pass。
- Phase 50 LangGraph vs ReAct：langgraph_agent errors=0, same_refusal=6/6, same_top_source=5/6, decision=parallel_candidate。
- Docker Compose：dev config 通过；prod config 用临时 `.env.prod` 与进程级占位 secret 验证通过，临时文件已删除。
- Redis 能力聚焦验证：embedding cache、RedisSaver checkpointer、Semantic Cache、Rate Limiting 共 19 passed。
- 备注：一次手写 one-off Semantic Cache smoke 使用 Python Redis client 超时，但同一轮 pytest RedisSaver 真实集成与 Redis CLI 均正常；未将该 one-off 脚本作为门禁。
- 提交状态：尚未 `git add`，尚未 commit/tag/push/PR，等待用户人工核验。

## Phase 12 日志：Rate Limiting（API 限流中间件）
时间：2026-06-21
- 新增 `RedisSlidingWindowRateLimiter` 与 `RateLimitMiddleware`。
- `Settings` 新增 rate limit 开关、每分钟请求数、窗口秒数；默认关闭。
- 仅 `/agent/query` 与 `/agent/query/stream` 受限；超限返回 429 与 `X-RateLimit-*` 响应头。
- Redis 未配置/不可用/执行异常时 fail-open 放行，避免 Redis 故障阻断 Agent 服务。
- 聚焦测试：5 passed。
- 提交状态：尚未 `git add`，尚未 commit/tag/push/PR，等待用户人工核验。

## Phase 11 日志：Semantic Cache（语义缓存）
时间：2026-06-21
- 新增 `RedisSemanticCache`，使用 Redis Hash + RediSearch KNN 向量索引缓存完整 Agent 回答。
- `Settings` 新增 semantic cache 开关、相似度阈值、TTL；默认关闭，不影响现有测试和本地运行。
- `/agent/query` 接入 Agent 前查缓存；命中直接返回，未命中正常执行 Agent 并在 eligible 时写入缓存。
- `latency_trace` 增加 `semantic_cache_hit` 与 `semantic_cache_similarity`。
- Redis/RediSearch 不可用时 graceful skip；streaming SSE 路径保持原格式不变。
- 聚焦测试：15 passed。
- 提交状态：尚未 `git add`，尚未 commit/tag/push/PR，等待用户人工核验。

## Phase 10 日志：Redis Stack 升级与 Checkpointer 修复
时间：2026-06-21
- 已确认继续沿用 `codex/phase-50-langgraph-redis`，未新建分支。
- 已阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、task_plan.md、findings.md、progress.md。
- `planning-with-files` catchup 脚本因 PowerShell `&` 表达式解析失败未执行成功；已手动读取并校准规划文件。
- `docker-compose.dev.yml`、`docker-compose.prod.yml` Redis 镜像升级为 `redis/redis-stack-server:latest`。
- 本机 Redis Stack 容器健康，包含 RediSearch `search` 与 RedisJSON `ReJSON` 模块。
- 修复 LangGraph checkpoint state 的 Redis 序列化边界：state 内部使用 JSON 原生 dict，API 输出仍保持 `AgentQueryResult` 契约。
- 真实 Redis Stack 集成测试确认 RedisSaver backend=`redis`，checkpoint 可写入 Redis；Redis 未配置/不可用时保留 MemorySaver fallback。
- 聚焦测试：35 passed。
- 提交状态：尚未 `git add`，尚未 commit/tag/push/PR，等待阶段完成后用户人工核验。
## Phase 14 启动日志：pgvector HNSW 向量索引迁移
时间：2026-06-21
- 线程标题已追加：pgvector HNSW迁移。
- 已确认继续沿用 `codex/phase-50-langgraph-redis`，未新建分支。
- 已阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、task_plan.md、findings.md、progress.md。
- 已确认 Phase 0-13 完成状态：全量 pytest 1093 passed / 1 skipped，Stage 30 91.52/A/pass，LangGraph Agent 可用，Redis embedding cache / RedisSaver Checkpointer / Semantic Cache / Rate Limiting 四项能力可用。
- 本 Phase 目标：把向量检索主路径从文件系统 FAISS IndexFlatIP 扩展为 PostgreSQL pgvector HNSW，可用时优先数据库检索，不可用时 fallback 到现有 FAISS。
- 提交状态：尚未 `git add`，尚未 commit/tag/push/PR。
## Semantic Cache Stream 修正日志（2026-06-21）

- 问题：UI 重复相同问题仍重新思考并生成不同答案；日志显示请求走 `/agent/query/stream`，Semantic Cache 未命中且 Agent tool calls 被重新执行。
- 原因：本地 `.env` 未启用 `SEMANTIC_CACHE_ENABLED=true`；同时初版 Semantic Cache 只接同步 `/agent/query`，未覆盖前端默认 stream 路径；会话内请求也因 `conversation_id/history` 被判定为不 eligible。
- 修正：`/agent/query/stream` 已接入 Semantic Cache lookup/store；同一会话内最后一条 user message 与当前问题完全相同才允许缓存命中；本地 `.env` 已设置 `REDIS_URL=redis://localhost:6379/0`、`SEMANTIC_CACHE_ENABLED=true`。
- 验证：`python -m pytest tests/test_phase50_semantic_cache.py tests/test_agent_stream_api.py tests/test_agent_api.py::test_agent_api_explicit_langgraph_agent_mode_uses_graph_service -q` -> `18 passed`。
- 服务：8000 已重启，`/health` 返回 ok，Redis Stack `search` / `ReJSON` 模块可用。

## Phase 15 完成日志：全栈回归验证与文档收尾（2026-06-21）

- 全量测试：`python -m pytest -q` -> `1100 passed, 1 skipped`。
- Stage 30：`python scripts/score_stage30_quality.py` -> `overall=91.52 grade=A release_decision=pass`。
- Compose：`docker compose -f docker-compose.dev.yml config` 通过；`docker compose -f docker-compose.prod.yml config` 使用临时占位 `.env.prod` 通过，临时文件已删除。
- 文档：README、AGENT.MD、docs/progress、docs/architecture、docs/data_sources、docs/deployment_guide、docs/phase_reviews/phase-50、环境模板已更新。
- Obsidian：Phase 14-15 小汇报与阶段索引已补齐。
- 最终状态：Phase 50 Phase 14-15 已完成并停在人工核验前；尚未 `git add`、未 commit、未 tag、未 push、未 PR。

## Phase 14 完成日志：pgvector HNSW 向量索引迁移（2026-06-21）

- 分支：继续沿用 `codex/phase-50-langgraph-redis`，未新建分支。
- 完成内容：PostgreSQL 容器升级为 `pgvector/pgvector:pg16`；新增 pgvector Alembic 迁移、`embedding_vector Vector(2048)` 模型列、HNSW 索引、pgvector 检索服务、配置开关与 latency backend 字段。
- 检索路径：`pgvector_search_enabled=True` 且 PostgreSQL/2048 维可用时优先 `pgvector_hnsw`；否则自动 fallback 到原 FAISS/numpy 路径。
- 本地实测修正：pgvector `vector` HNSW 索引不能超过 2000 维，已将 HNSW 索引改为 `halfvec(2048)` 表达式索引，保留 `embedding_vector Vector(2048)` 数据列。
- 验证：`python -m pytest tests/test_phase50_pgvector_hnsw.py tests/test_vector_search.py tests/test_vector_cache.py tests/test_phase49_local_postgres_dev.py tests/test_stage44_deployment.py -q`，结果 `25 passed`。
- 状态：Phase 14 代码与 focused tests 完成；尚未 `git add`、未 commit、未 tag、未 push、未 PR。下一步进入 Phase 15 全栈回归验证与文档/Obsidian 收尾。
## Semantic Cache Stream 与隔离最终修正日志（2026-06-21）

- 问题：UI 默认走 `/agent/query/stream`，初版 Semantic Cache 只覆盖同步 `/agent/query`，并且缺少数据库上下文隔离。
- 修正：stream 路径已支持 Semantic Cache 命中和写入；会话内完全相同的重复问题可以命中；缓存 key/payload 绑定 database context、mode、embedding provider、model、dimension。
- 本地测试配置：`.env` 已设置 `REDIS_URL=redis://localhost:6379/0`、`SEMANTIC_CACHE_ENABLED=true`；Redis Stack `search` / `ReJSON` 模块可用。
- 清理：已删除旧格式 `semcache:*` 和 `idx:semcache`，避免旧缓存影响新格式筛选。
- 验证：`python -m pytest tests/test_phase50_semantic_cache.py tests/test_agent_stream_api.py tests/test_agent_api.py -q` -> `51 passed`。
- 服务：8000 已重启，PID `12868`，`/health` 返回 ok。
## Semantic Cache standalone query eligibility fix (2026-06-21)
- Issue observed in UI: semantically close standalone questions such as `堆石混凝土的性能` and `堆石混凝土的性能有哪些？` did not reach semantic cache lookup inside an existing conversation, because eligibility previously required an exact last-user-message match.
- Fix: `semantic_cache_request_is_eligible()` now still blocks source-filtered/image requests, but allows standalone RFC/domain questions inside a conversation to enter Redis KNN lookup; contextual follow-ups such as `它有哪些？` remain ineligible to avoid reusing an answer under the wrong context.
- Verification: `python -m pytest tests\test_phase50_semantic_cache.py::test_semantic_cache_config_and_request_eligibility -q` -> `1 passed`; `python -m pytest tests\test_phase50_semantic_cache.py -q` -> `8 passed`.
- Submission state remains unchanged: no `git add`, commit, tag, push, or PR.
## LangGraph safe answer-progress streaming update (2026-06-21)
- Added safe `agent_step` progress events before LangGraph `answer_with_citations` waits on final answer generation: evidence organization, related source count, citation-number check, and final Chinese answer generation.
- Frontend live thinking status now prefers SSE `step_summary`, so users see public progress such as `正在基于 5 条证据组织回答` instead of raw model CoT or provider `reasoning_content`.
- Verification: `node --check app\frontend\static\app.js` passed; `python -m pytest tests\test_phase50_langgraph_nodes.py::test_generate_answer_node_uses_answer_with_citations_contract tests\test_phase50_langgraph_nodes.py::test_generate_answer_node_emits_safe_answer_progress -q` -> `2 passed`; `python -m pytest tests\test_agent_stream_api.py -q` -> `10 passed`; `python -m pytest tests\test_frontend_app.py -q` -> `10 passed`.
- Submission state remains unchanged: no `git add`, commit, tag, push, or PR.
## LangGraph search-progress streaming update (2026-06-21)
- Issue observed in UI: the live thinking panel stayed on `检索知识库` for a long time. Backend logs confirmed this step includes query embedding, vector/keyword candidate retrieval, candidate fusion, and remote rerank.
- Fix: `search_knowledge_node` now emits safe `search_progress` SSE events through the existing event sink. These are public engineering-status messages, not model CoT, raw provider output, or hidden reasoning.
- `HybridSearchService` and `VectorSearchService` now accept an optional `progress_callback` and report: generating/reading query vector, vector similarity search, parallel keyword/vector retrieval, candidate merge/sort, and reranking.
- Frontend `app.js` localizes `search_progress` and continues to prefer `step_summary` for live status text.
- Logging fix: `log_agent_response_event` now reads `time_to_final_ms` instead of the non-existent `total_latency_ms`, so `answer_generated.latency_ms` is populated.
- Verification: `node --check app\frontend\static\app.js` passed; `python -m pytest tests\test_phase50_langgraph_nodes.py::test_search_knowledge_node_reuses_agent_toolbox_and_records_observation tests\test_phase50_langgraph_nodes.py::test_search_knowledge_node_emits_safe_search_progress tests\test_phase50_langgraph_nodes.py::test_generate_answer_node_emits_safe_answer_progress -q` -> `3 passed`; `python -m pytest tests\test_agent_stream_api.py -q` -> `10 passed`.
- Submission state remains unchanged: no `git add`, commit, tag, push, or PR.
## Frontend search-progress visibility update (2026-06-21)
- Issue: `search_progress` SSE events were emitted by the backend, but the frontend live-step container stayed hidden and final `metadata` rendering removed the live-step DOM before preserving it in the thought panel.
- Fix: `appendAgentLiveStep()` now unhides the live-step container when events arrive; final streaming render converts `_agentThoughtEvents` into `_live_thought_steps`, so search substeps remain visible under `查看思考过程` after the answer completes.
- Thought-step rendering now shows safe summaries from `step_summary` / `observation_summary` / `output_summary` / `input_summary`, allowing entries like query-vector generation, vector similarity search, candidate merge, and rerank to be readable.
- Verification: `node --check app\frontend\static\app.js` passed; `python -m pytest tests\test_frontend_app.py -q` -> `10 passed`; `python -m pytest tests\test_agent_stream_api.py tests\test_phase50_langgraph_nodes.py::test_search_knowledge_node_emits_safe_search_progress -q` -> `11 passed`.
- Submission state remains unchanged: no `git add`, commit, tag, push, or PR.
## LangGraph vector-search progress and local pgvector enablement (2026-06-21)
- User observed the UI staying on `正在并行检索关键词和向量候选证据` for a long time. Logs showed FAISS loading, meaning local runtime was falling back to FAISS instead of using Phase 14 pgvector HNSW.
- Root cause: `.env` did not set `PGVECTOR_SEARCH_ENABLED=true`, so the default disabled pgvector path and used FAISS fallback. Also, vector-search progress events emitted inside `ThreadPoolExecutor` did not inherit the LangGraph `ContextVar` event sink, so substeps from the vector worker were not visible in the frontend.
- Fix: `.env` now includes non-sensitive `PGVECTOR_SEARCH_ENABLED=true` and `HNSW_EF_SEARCH=100`; code captures the current event sink before entering hybrid search and passes it through the progress callback so worker-thread vector progress reaches SSE.
- Verification: `python -m pytest tests/test_phase50_langgraph_nodes.py::test_search_knowledge_node_emits_safe_search_progress tests/test_agent_stream_api.py -q` -> `11 passed`; `node --check app/frontend/static/app.js` passed.
- Service restarted on port 8000 for manual verification. Submission state remains unchanged: no `git add`, commit, tag, push, or PR.
## pgvector HNSW default correction (2026-06-21)
- User confirmed the intended default retrieval path should be HNSW-first. Root cause: Phase 14 kept `pgvector_search_enabled=False` and `PGVECTOR_SEARCH_ENABLED=false` in templates for conservative SQLite/CI compatibility, so local runtime could silently use FAISS fallback unless `.env` explicitly enabled pgvector.
- Correction: `app/core/config.py`, `.env.example`, and `.env.dev.example` now default pgvector search to enabled. Runtime remains graceful: PostgreSQL + pgvector + 2048-dimensional embeddings use `pgvector_hnsw`; SQLite, unavailable pgvector, non-PostgreSQL, or wrong dimension still fallback to FAISS/numpy.
- Docs updated: README, AGENT.MD, docs/architecture.md, docs/progress.md, and docs/phase_reviews/phase-50.md now describe HNSW-first defaults instead of conservative-off defaults.
- Verification: `python -m pytest tests/test_phase50_pgvector_hnsw.py tests/test_vector_search.py tests/test_vector_cache.py -q` -> `16 passed`; `python -m pytest tests/test_agent_stream_api.py tests/test_phase50_langgraph_nodes.py::test_search_knowledge_node_emits_safe_search_progress -q` -> `11 passed`; `node --check app/frontend/static/app.js` passed.
- Submission state remains unchanged: no `git add`, commit, tag, push, or PR.
## Phase 50 final submission validation (2026-06-21)
- User manually accepted Phase 50 and authorized commit, tag, push, and GitHub merge.
- Final validation before submission: `python -m pytest -q` -> `1110 passed, 1 skipped`; `python scripts/score_stage30_quality.py` -> `overall=91.52 grade=A release_decision=pass`; `docker compose -f docker-compose.dev.yml config --quiet` -> passed; `docker compose -f docker-compose.prod.yml config --quiet` -> passed with temporary placeholder `.env.prod` and process-level placeholder variables, then the temporary file was removed.
- Submission safety check: `.env`, `.env.prod`, and `obsidian-vault/` are not tracked by Git; no API keys, bearer tokens, provider raw responses, `raw_response`, `reasoning_content`, hidden thoughts, or restricted full text are intentionally staged.

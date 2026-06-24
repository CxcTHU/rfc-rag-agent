# 部署指南：FastAPI + Docker

## 适用范围

本指南最初对应阶段 39 的生产部署与端到端体验收尾；阶段 49 后，本地开发推荐使用 `docker-compose.dev.yml` 启动 PostgreSQL 16，生产部署推荐使用 `docker-compose.prod.yml`。旧 `docker-compose.yml` 仍保留为 SQLite fallback/历史单容器路径。

```text
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

旧 Chainlit 入口 `chainlit_app.py` 仅作为历史界面保留，不是 Docker 默认启动入口。

## 前置条件

- Python 3.11 用于本地开发。
- Docker Desktop 或兼容 Docker Engine 用于容器构建。
- 本地 `.env` 保存真实 provider 配置；`.env` 不得提交。
- `./data` 作为运行时数据卷挂载到容器内 `/app/data`。

## 可选 Planner 快模型配置

`react_agent` 与 `langgraph_agent` 支持 `PLANNER_CHAT_MODEL_*` 配置，用低延迟模型做 action 路由，主 `CHAT_MODEL_*` 仍用于最终引用式回答生成。生产 Docker Compose 要求显式配置 planner provider，避免生产环境静默退回 `DeterministicReActPlanner`；测试入口会在 `tests/conftest.py` 清空这些变量，确保 CI 仍走 deterministic 路径。

```text
PLANNER_CHAT_MODEL_PROVIDER=openai-compatible
PLANNER_CHAT_MODEL_NAME=deepseek-v4-flash
PLANNER_CHAT_MODEL_API_KEY=<local-only>
PLANNER_CHAT_MODEL_BASE_URL=<provider-base-url>
PLANNER_CHAT_MODEL_TEMPERATURE=0
PLANNER_CHAT_MODEL_TIMEOUT_SECONDS=10
```

部署时不要把真实 planner API key 写入 Git、镜像、文档或 Obsidian；只放在服务器本地 `.env.prod` 或等价 secret 管理中。

## 本地 PostgreSQL 开发启动（推荐）

复制本地 PostgreSQL 示例配置中的 `DATABASE_URL` 到 `.env`，或直接按需手动设置：

```powershell
Copy-Item .env.example .env
```

本地 PostgreSQL 示例连接串：

```text
DATABASE_URL=postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev
```

启动本地 PostgreSQL 16：

```powershell
docker compose -f docker-compose.dev.yml up -d db
```

建表并迁移本地 SQLite 数据：

```powershell
$env:DATABASE_URL="postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev"
python -m alembic upgrade head
python scripts/migrate_sqlite_to_postgres.py --source-sqlite-url sqlite:///./data/app.sqlite --target-database-url $env:DATABASE_URL
```

从 PostgreSQL 重建 FAISS：

```powershell
python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 --database-url $env:DATABASE_URL
```

启动 FastAPI：

```powershell
python -m uvicorn app.main:app --reload
```

访问：

```text
http://127.0.0.1:8000
```

## SQLite fallback 快速启动（历史路径）

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

按需填写本地 `.env` 后构建镜像：

```powershell
docker build -t rfc-rag-agent:phase39-production-deployment .
```

使用 Docker Compose 启动：

```powershell
docker compose up --build
```

访问：

```text
http://127.0.0.1:8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期返回：

```json
{
  "status": "ok",
  "service": "RFC-RAG-Agent",
  "environment": "production"
}
```

## 环境变量

推荐本地开发基础配置：

```text
APP_ENV=development
DATABASE_URL=postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev
RAW_DATA_DIR=data/raw
```

SQLite fallback 配置：

```text
APP_ENV=production
DATABASE_URL=sqlite:////app/data/app.sqlite
RAW_DATA_DIR=/app/data/raw
```

Chat provider：

```text
CHAT_MODEL_PROVIDER=
CHAT_MODEL_NAME=
CHAT_MODEL_API_KEY=
CHAT_MODEL_BASE_URL=
CHAT_MODEL_TEMPERATURE=0.2
CHAT_MODEL_TIMEOUT_SECONDS=30
```

生产 ReAct / LangGraph planner provider：

```text
PLANNER_CHAT_MODEL_PROVIDER=openai-compatible
PLANNER_CHAT_MODEL_NAME=deepseek-v4-flash
PLANNER_CHAT_MODEL_API_KEY=<local-only>
PLANNER_CHAT_MODEL_BASE_URL=<provider-base-url>
PLANNER_CHAT_MODEL_TEMPERATURE=0
PLANNER_CHAT_MODEL_TIMEOUT_SECONDS=10
```

真实 planner API key 只允许写入服务器本地 `.env.prod` 或等价 secret 管理，不得写入 Git、CSV、文档、测试或 Obsidian。

Embedding provider：

```text
EMBEDDING_PROVIDER=
EMBEDDING_MODEL_NAME=
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_DIMENSION=0
EMBEDDING_TIMEOUT_SECONDS=30
```

Redis / LangGraph（Phase 50）：

```text
REDIS_PASSWORD=<strong redis password>
REDIS_URL=redis://:<url-encoded redis password>@redis:6379/0
REDIS_SOCKET_TIMEOUT_SECONDS=1.0
LANGGRAPH_CHECKPOINT_TTL_MINUTES=60
LANGGRAPH_CHECKPOINT_REFRESH_ON_READ=true
```

`docker-compose.dev.yml` 和 `docker-compose.prod.yml` 都提供 Redis 7 容器。当前 Redis 主要用于 query embedding 缓存；命中后会跳过 embedding provider 调用。Redis 不可用、未配置或连接超时时，服务会 graceful fallback 到进程内 `QueryEmbeddingCache`。

`mode="langgraph_agent"` 会尝试使用 `langgraph-checkpoint-redis` 的 Redis checkpointer。该适配器需要 RedisJSON / RediSearch 模块；普通 `redis:7-alpine` 不一定具备这些模块，因此生产若只使用普通 Redis 7，Agent 会自动 fallback 到 `MemorySaver`，不影响回答链路。若需要真正跨进程持久化 LangGraph checkpoint，请在生产环境改用带 RedisJSON / RediSearch 的 Redis Stack 或 Redis 8 模块化镜像，并保留相同 `REDIS_URL`。

Reranking provider：

```text
RERANKING_ENABLED=true
RERANKING_PROVIDER=remote-bge-lora
RERANKING_MODEL_NAME=rfc-domain-bge-lora
RERANKING_API_KEY=
RERANKING_BASE_URL=http://127.0.0.1:8091
RERANKING_TIMEOUT_SECONDS=30
RERANKING_RECALL_K=75
```

The default RAG/Agent retrieval chain uses the Stage 3 quality-first setting:
`remote-bge-lora`, `candidate_pool_size=75`, and final evidence `top_k=8`.
The remote BGE LoRA service must be reached through a private path such as an
SSH tunnel to `127.0.0.1:8091`; do not expose the reranker port publicly. If
the remote reranker is unavailable, `HybridSearchService` fails open and
returns the original hybrid/RRF order instead of failing the request.

Offline rollback configuration:

```text
RERANKING_PROVIDER=deterministic
RERANKING_MODEL_NAME=keyword-overlap-reranker-v1
RERANKING_BASE_URL=
RERANKING_RECALL_K=25
```

真实 API key 只能放在本地 `.env` 或部署平台的 secret manager 中，不得写入 Git、CSV、文档、测试或 Obsidian。

## 数据卷

`docker-compose.yml` 默认挂载：

```text
./data:/app/data
```

PostgreSQL 开发数据默认位于 Docker volume：

```text
pgdata_dev
```

SQLite fallback 数据库默认位于：

```text
/app/data/app.sqlite
```

本地全文、原始 PDF、SQLite、FAISS index 和评测派生产物都属于运行时或可重建数据，不应进入镜像或 Git。

## 健康检查

Compose healthcheck 使用：

```text
GET /health
```

该接口只返回服务状态、服务名和环境名，不触发真实 provider、不写数据库、不读取受限全文。

## 生产 Smoke

服务启动后可运行：

```powershell
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120
```

smoke CSV 只记录 endpoint、状态、耗时、mode 校验、citation_count、refused、错误摘要等安全字段，不保存 response body、API key、Bearer token、raw provider response、`reasoning_content` 或受限全文。

## 结构化日志

阶段 39 使用标准 logging JSON 输出。请求日志包含：

```text
event
request_id
method
path
status_code
latency_ms
```

Agent 日志包含：

```text
query_received
tool_call_executed
answer_generated
refusal_triggered
```

日志不会记录 Authorization header、API key、Bearer token、raw provider response、`reasoning_content`、完整用户问题或完整 chunk。

## 常见问题

Docker build 连接失败：

```text
failed to connect to dockerDesktopLinuxEngine
```

处理方式：启动 Docker Desktop，确认当前 context 为 `desktop-linux` 或可用 Docker Engine。

服务启动后 `/health` 不是 production：

检查 compose 是否设置：

```text
APP_ENV=production
```

Agent 请求超时：

检查 `.env` 中 chat / embedding / reranking provider 配置、网络连通性和 timeout 秒数。不要把 provider 原始错误体复制到文档或 CSV。

Stage 30 回归：

运行：

```powershell
python scripts/score_stage30_quality.py
```

阶段 39 收尾要求保持：

```text
overall=91.52 grade=A release_decision=pass
```
## Phase 50 Redis Stack, Semantic Cache, And Rate Limiting

Phase 50 now expects Redis Stack for full Redis-backed behavior:

```text
docker-compose.dev.yml  -> redis/redis-stack-server:latest
docker-compose.prod.yml -> redis/redis-stack-server:latest
```

Required and optional runtime settings:

```text
REDIS_PASSWORD=<strong redis password>
REDIS_URL=redis://:<url-encoded redis password>@redis:6379/0
LANGGRAPH_CHECKPOINT_TTL_MINUTES=60
LANGGRAPH_CHECKPOINT_REFRESH_ON_READ=true
SEMANTIC_CACHE_ENABLED=false
SEMANTIC_CACHE_SIMILARITY_THRESHOLD=0.92
SEMANTIC_CACHE_TTL_SECONDS=3600
RATE_LIMIT_ENABLED=false
RATE_LIMIT_REQUESTS_PER_MINUTE=30
RATE_LIMIT_WINDOW_SECONDS=60
```

Redis failure behavior is intentionally graceful: embedding cache falls back to memory, LangGraph checkpoint falls back to `MemorySaver`, Semantic Cache skips, and Rate Limiting fail-opens. Keep Semantic Cache and Rate Limiting disabled until Redis Stack health and production traffic expectations are verified.
## Phase 50 pgvector HNSW Deployment Note

Phase 50 dev/prod Compose files now use `pgvector/pgvector:pg16` for PostgreSQL. Run Alembic after pulling the image so PostgreSQL can create the `vector` extension, `chunk_embeddings.embedding_vector Vector(2048)`, and the HNSW cosine index.

```powershell
docker compose -f docker-compose.dev.yml up -d db redis
$env:DATABASE_URL="postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev"
python -m alembic upgrade head
```

Enable pgvector search only after the migration succeeds:

```text
PGVECTOR_SEARCH_ENABLED=true
HNSW_EF_SEARCH=100
```

If pgvector is disabled or unavailable, the app continues to use the existing FAISS/numpy fallback. Keep `data/faiss/` as a rebuildable runtime artifact; do not commit FAISS files or secrets.

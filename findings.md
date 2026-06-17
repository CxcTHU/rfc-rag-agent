# 阶段 44 Findings：生产部署上线（PostgreSQL + 用户注册登录 + 云端部署）

## Requirements

- 主线 A：数据库抽象，SQLite ↔ PostgreSQL 双 engine 支持，由 `DATABASE_URL` scheme 自动切换。
- 主线 B：用户注册登录系统，User 模型 + bcrypt 密码哈希 + JWT 认证 + 对话隔离。
- 主线 C：docker-compose 生产部署配置，app + PostgreSQL 一键部署。
- Stage 30 评分不得低于 91.52 / A / pass。
- 不做跨会话长期记忆，不做用户画像/私人偏好记忆。
- 不把 summary 当作可引用资料来源。
- 不改变 Stage 30 评分规则、provider 拓扑或数据源边界。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、JWT secret、密码明文、供应商原始响应、raw_response、reasoning_content 写入 Git/CSV/文档/测试/Obsidian。
- 已租用的云服务器用于阶段 44 部署 smoke 与人工核验前验证，但不得成为 CI 或本地全量测试前提。

## Research Findings

### 数据库现状

- `app/db/session.py`：阶段 44 已新增 `create_database_engine()`，根据 `DATABASE_URL` backend 自动选择 SQLite 或 PostgreSQL；SQLite 继续使用 `check_same_thread=False`，PostgreSQL 使用 `pool_pre_ping=True`。
- `app/db/models.py`：阶段 44 前有 6 个 ORM 模型（Document, Source, Chunk, ChunkEmbedding, Conversation, Message）+ 1 个日志模型（QuestionAnswerLog）；阶段 44 已新增 `User`，并为 `Conversation` 增加 nullable `user_id` 外键。
- SQLAlchemy DeclarativeBase，使用 `mapped_column` 注解模式。
- 所有字段类型（Text, String, Integer, Boolean, DateTime, Float, JSON）天然兼容 PostgreSQL，无需改动列定义。
- `engine` 和 `SessionLocal` 仍是模块级全局变量，但 engine 创建逻辑已切换为 `create_database_engine(get_settings().database_url)`。

### 认证现状

- 阶段 44 已新增 `User` 模型、bcrypt 密码哈希、HS256 JWT、`/auth/register`、`/auth/login`、`/auth/me`。
- `POST /agent/query` 和 `/agent/query/stream` 已接入 `get_current_user()`；`AUTH_ENABLED=true` 时需要 Bearer token。
- `Conversation` 模型已新增 `user_id` 外键；`ConversationRepository` 已支持按 `user_id` 过滤读取、列表、消息、删除、重命名和计数。
- FastAPI 的 `Depends()` 依赖注入机制天然支持认证守卫。

### Docker 现状

- `Dockerfile`：multi-stage build，python:3.11-slim，uvicorn CMD。
- `docker-compose.yml`：单 service，`DATABASE_URL: sqlite:////app/data/app.sqlite`，`./data:/app/data` volume。
- `.dockerignore`：正确排除 .env、SQLite 文件、raw 数据、obsidian-vault、tests。
- 阶段 43 新增 `deploy/nginx-https.example.conf` 和 `deploy/Caddyfile.example` 反向代理模板。

### 云服务器现状（2026-06-17）

- 平台：并行智算云。
- 配置：纯 CPU、4 核、8GB 内存、Ubuntu 22.04 CMD、系统盘约 100GB、公网 IP `36.103.199.132`。
- 计费：按量计费，约 `0.69 元/小时`；长期运行前需要确认是否切换为包天/包月或人工释放策略。
- 远端初始化结果：
  - SSH 用户：`ubuntu`。
  - 已安装基础工具：`git`、`curl`、`vim`、`ca-certificates`、`gnupg`、`lsb-release`。
  - Docker：`Docker version 29.1.3`。
  - Docker Compose v2：`Docker Compose version 2.40.3`。
  - `ubuntu` 用户已加入 `docker` 组，新 SSH 会话中可直接执行 `docker ps`。
  - 根分区约 97GB，当前可用约 86GB；内存约 8GB，当前可用约 7GB。
- 该服务器尚未部署本项目应用，也尚未传输项目数据；当前状态是 Docker-ready 服务器，不是阶段 44 应用上线完成。
- 截图/对话中曾暴露初始 SSH 密码；用户明确要求暂不修改。后续文档、脚本、测试和 Obsidian 不得写入该密码。

### 技术选型决策

- **密码哈希**: bcrypt（passlib[bcrypt]），业界标准，自带 salt，抗暴力破解。
- **认证方式**: JWT Bearer Token。无状态，适合 API 场景，前端简单存储 token。
- **JWT 库**: python-jose[cryptography] 或 PyJWT。
- **JWT 实现校准**: 阶段 44 当前使用标准库实现 HS256 JWT（base64url + HMAC-SHA256），避免额外 JWT 运行时依赖；测试覆盖签名、过期字段和 subject。
- **PostgreSQL driver**: psycopg2-binary（开发/部署通用，免编译依赖）。
- **迁移工具**: Alembic（SQLAlchemy 官方迁移工具）。
- **生产 PostgreSQL 镜像**: postgres:16-alpine（轻量、长期支持）。
- **云服务器使用方式**: 服务器仅用于部署 smoke 与人工核验前验证；正式开发、全量 pytest、Stage 30 评分仍以本地 deterministic/SQLite 路径为主，避免远端环境成为必要前提。

### 安全边界

- JWT_SECRET_KEY 必须从环境变量读取，不进 Git。
- 密码必须 bcrypt 哈希存储，register/login 响应中不返回 password_hash。
- JWT token 有过期时间（建议 24h），过期后需重新登录。
- 日志中不输出密码明文、token 全文或 JWT secret。
- `.env.example` 只包含模板，不含真实值。
- 云服务器 SSH 密码、数据库密码、JWT secret、API key、Bearer token 只允许存在用户本地安全位置或服务器运行环境中，不得写入规划文件、提交物、部署文档示例、测试 fixture 或 Obsidian。
- 远端 smoke 只记录安全结论、HTTP 状态、健康检查、认证链路和脱敏错误摘要，不保存真实 token、密码、完整回答、完整 chunk 或供应商响应。

## Key Decisions

1. **保留 SQLite 本地开发路径**：`docker-compose.yml`（SQLite）用于本地开发，`docker-compose.prod.yml`（PostgreSQL）用于生产部署。两者共存，不强制本地安装 PostgreSQL。
2. **Alembic 管理迁移**：initial migration 包含全部现有表 + 新 User 表。后续阶段修改表结构通过 alembic revision --autogenerate。
3. **认证边界明确化**：生产环境必须启用认证；本地测试可通过显式环境变量走兼容模式，但必须有测试覆盖认证开启时 `/agent/query`、`/agent/query/stream`、`/conversations/*` 的 401 与用户隔离行为。
4. **对话隔离 nullable**：`Conversation.user_id` 设为 nullable，旧数据（无用户）保持兼容。新创建的对话在认证启用时必须绑定用户；列表、读取、重命名、删除和追加消息都必须按 `user_id` 过滤。
5. **前端认证入口需要纳入阶段 44**：浏览器 smoke 需要注册/登录/带 token 查询，因此阶段 44 不能只做后端 API；原生前端需要最小登录/注册入口、token 保存和 Authorization header 注入。
6. **远端部署 smoke 晚于本地验证**：先完成本地 SQLite 全量回归、Stage 30 和本地 `docker-compose.prod.yml` 验证，再把代码与必要数据传到服务器执行 smoke。

## Implementation Findings

### 聚焦测试结果

```text
python -m pytest tests/test_stage44_db_session.py tests/test_stage44_auth.py -q -> 9 passed
```

覆盖范围：

- SQLite engine 仍自动创建父目录。
- PostgreSQL engine 可在不连接数据库的情况下创建，并启用 `pool_pre_ping`。
- 未知 `DATABASE_URL` backend 会快速失败。
- bcrypt 哈希不保存明文，正确密码可验证，错误密码不可验证。
- 注册/登录/`/auth/me` 不返回 `password_hash`。
- `AUTH_ENABLED=true` 时 `/agent/query`、`/agent/query/stream`、`/conversations` 未登录返回 401。
- 两个用户创建的 conversation 互相不可见，跨用户读取/删除返回 404。

### 新词解释

- **bcrypt**：密码哈希算法，自带随机 salt，适合存储用户密码；本项目只保存 `password_hash`，不保存明文密码。
- **JWT（JSON Web Token）**：无状态访问令牌，本项目用 HS256 签名，payload 保存 `sub`（用户 id）、`iat`（签发时间）和 `exp`（过期时间）。
- **Bearer token**：HTTP `Authorization: Bearer <token>` 认证方式；前端登录后把 JWT 放入该请求头。
- **pool_pre_ping**：SQLAlchemy 连接池选项，取连接前先检查连接是否仍可用，适合 PostgreSQL 长连接环境。

### 2026-06-17 Implementation Update

- Alembic 已落地：`alembic.ini`、`alembic/env.py`、`alembic/script.py.mako`、`alembic/versions/20260617_0001_initial_schema.py`。
- Initial migration 显式创建全部现有表：`documents`、`sources`、`chunks`、`chunk_embeddings`、`conversations`、`messages`、`qa_logs`，并新增 `users` 与 `conversations.user_id`。
- 已用临时 SQLite smoke 库执行 `python -m alembic upgrade head`，迁移可真实运行。
- `docker-compose.prod.yml` 已新增 app + `postgres:16-alpine`，PostgreSQL 使用 named volume `postgres_data` 持久化，app 在 DB healthcheck 通过后执行 `alembic upgrade head` 再启动。
- `.env.example` 新增 `AUTH_ENABLED`、`JWT_SECRET_KEY`、JWT 过期时间、PostgreSQL 模板变量；`.env.prod` 被 `.gitignore` 覆盖，不应提交。
- `docs/deployment_cloud.md` 已记录云端部署、smoke、数据持久化和安全边界，仍只使用占位符。
- 前端已新增最小登录/注册/退出入口，JWT 保存在浏览器 `localStorage`，`fetchJson()` 和 `streamAgentQuery()` 统一注入 `Authorization: Bearer <token>`。
- `AUTH_ENABLED=true` 时已测试 `/health`、`/health/details`、`/auth/register`、`/auth/login` 公开，`/agent/query`、`/agent/query/stream`、`/conversations` 未登录 401，跨用户 conversation 访问 404。

### 2026-06-17 Focused Verification Update

```text
python -m pytest tests/test_stage44_auth.py tests/test_stage44_db_session.py tests/test_stage44_deployment.py tests/test_frontend_app.py -q -> 25 passed
python -m alembic upgrade head with sqlite:///data/stage44_alembic_smoke.sqlite -> passed
docker compose -f docker-compose.prod.yml --env-file .env.prod config --quiet with temporary placeholder env -> passed
```

注意：临时 `.env.prod` 只用于 compose config 验证，验证后已删除；不得将真实数据库密码、JWT secret、SSH 密码或 token 写入仓库。

### 2026-06-17 Remote Smoke Update

- 远端 Docker Hub 直连拉取 `postgres:16-alpine` 超时；使用临时镜像预拉取并 tag 后继续 smoke。
- 远端 Python 包下载直连 PyPI 很慢；`Dockerfile` 与 `docker-compose.prod.yml` 已新增可选 `PIP_INDEX_URL` / `PIP_TRUSTED_HOST` build arg，默认空值不影响普通环境，远端 `.env.prod` 临时设置 Python 包镜像源完成构建。
- 远端 app 初次启动暴露 `ModuleNotFoundError: No module named 'scripts'`，原因是 runtime 镜像只复制 `app/` 和 Alembic；已修复为 `COPY scripts ./scripts`，并补充部署测试。
- 远端 server-local smoke 通过：`127.0.0.1:8044/health` 200，register/login/me 200，未登录 `/agent/query` 401，带 token `/agent/query` 200，app/db containers healthy。
- 用户已在云平台端口列表放行公网 TCP 8044；公网 `http://36.103.199.132:8044/health` 从本机返回 200，首页返回 200，公网 register/login/me、未登录 `/agent/query` 401、带 token `/agent/query` 200 均通过。
- 公网页面人工 smoke 暴露前端未登录 UX 问题：`/conversations` 401 会显示泛化的 `Request failed`，且流式请求失败后回退到普通 `/agent/query` 时缺少 `Authorization` header。已修复为未登录时提示先登录/注册，并让回退请求携带 `authHeaders()`。
- 公网页面人工核验继续暴露认证入口不符合上线体验：顶部内联登录/注册表单拥挤，注册失败规则不清楚。已改为独立认证门页，未登录时隐藏工作台，支持 `Sign in` / `Create account` tab、注册前端校验和表单内错误提示；注册成功自动登录并进入对话页。
- 用户要求认证门页中文化；已将登录/注册门页、tab、按钮、占位符、登录状态、注册校验和错误提示切换为中文，避免生产入口混用英文。
- 用户人工注册时看到“请求的接口不存在”；公网直测 `/auth/register` 返回 200，判断更可能是浏览器缓存混用旧静态资源。已升级静态资源版本到 `phase44-auth-gate-zh-fix1`，并让前端 404 错误显示具体接口路径，便于后续定位。

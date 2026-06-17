# 阶段 44 Progress：生产部署上线（PostgreSQL + 用户注册登录 + 云端部署）

## Session: 2026-06-17

### Phase 0：启动校准与规划落盘（Claude 规划方 + Codex 校准）

- **Status:** complete
- **Started:** 2026-06-17

Phase purpose:

- 这一 Phase 由 Claude 规划方完成，为阶段 44 编写任务计划、发现记录和进度文件。
- 阶段 44 有三条主线：A（数据库抽象 SQLite↔PostgreSQL）、B（用户注册登录 + JWT）、C（docker-compose 生产部署）。
- 现在做它，是因为阶段 43 已完成多轮评测和可观测性增强，项目功能趋于完善，但仍停留在本地 SQLite 单机模式。数据库迁移、用户认证和生产部署是从"能跑通"到"能上线"的关键工程化能力。
- 2026-06-17 用户已租用并行智算云纯 CPU 服务器，Codex 已完成 Docker-ready 基础初始化，因此阶段 44 需要把"可部署形态"升级为"可在已准备服务器上 smoke 验证的部署形态"。

Actions taken:

- 确认阶段 43 最终状态：876 tests，Stage 30 = 91.52/A/pass，多轮 Judge 完成，HTTPS 模板完成。
- 审查数据库现状：`app/db/session.py` 硬编码 SQLite，6+1 个 ORM 模型兼容 PostgreSQL。
- 审查认证现状：无 User 模型、无认证中间件、对话无用户隔离。
- 审查 Docker 现状：Dockerfile + docker-compose.yml + .dockerignore + deploy/ 模板已有。
- 编写 `task_plan.md`（8 个 Phase）、`findings.md`（技术选型 + 安全边界）、`progress.md`。
- Codex 重新核对 Git 状态：
  - 当前分支：`codex/phase-43-multi-turn-quality-and-observability`。
  - `origin/main -> 5596d27 Merge phase 43 multi-turn quality and observability`。
  - `cbbc3ce Complete phase 43 multi-turn quality and observability` 是 `origin/main` 祖先。
  - 本地 `main -> d7dfca1 Merge phase 41 post-import retrieval optimization`，落后 `origin/main` 5 个提交；阶段 44 必须从 `origin/main` 创建分支。
  - 当前工作区已有阶段 44 规划改动：`task_plan.md`、`findings.md`、`progress.md`；另有未跟踪 `.playwright-mcp/`，后续不得误提交。
- Codex 已修改当前线程名称为：阶段44-生产部署上线。
- Codex 已根据服务器状态校准 Claude 原 prompt：阶段 44 共有 Phase 0-8（9 个 Phase），不是"8 个 Phase"；远端服务器用于部署 smoke，不作为 CI 或本地全量测试前提。
- Codex 已从 `origin/main -> 5596d27` 创建阶段分支：`codex/phase-44-cloud-deployment-auth`。
- Codex 已完成服务器基础初始化：
  - 服务器：并行智算云纯 CPU 4 核 8GB、Ubuntu 22.04 CMD、系统盘约 100GB、公网 IP `36.103.199.132`。
  - 已安装 `git`、`curl`、`vim`、`ca-certificates`、`gnupg`、`lsb-release`。
  - 已安装并启动 Docker：`Docker version 29.1.3`。
  - 已安装 Docker Compose v2：`Docker Compose version 2.40.3`。
  - `ubuntu` 用户已加入 `docker` 组，新 SSH 会话中 `docker ps` 可直接运行。
  - 磁盘状态：根分区约 97GB，已用约 12GB，可用约 86GB。
  - 内存状态：总计约 7.8GiB，可用约 7.2GiB。

Outcome:

- 规划文件已按服务器已就绪事实校准，阶段 44 分支已从 `origin/main` 正确创建。
- 当前仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

Risks / notes:

- 云服务器 SSH 初始密码曾在对话截图中出现；用户明确要求暂不修改。任何文档、测试、CSV、Obsidian 和 Git 提交均不得写入该密码。
- 远端服务器只是 Docker-ready；应用代码、数据、PostgreSQL compose 和认证链路尚未部署完成。
- 服务器仍有系统升级项未完整执行；为避免交互式升级影响当前工作，暂未强制 `apt upgrade -y` 全量升级。部署前可安排维护窗口升级和重启。
- 阶段 44 仍处于"尚未提交，等待用户人工核验"规则下。

### Phase 1/2/3 early implementation note（Codex）

- **Status:** started
- **Started:** 2026-06-17

Phase purpose:

- Phase 1 固定设计合同，Phase 2 解决 SQLite/PostgreSQL engine 抽象和迁移入口，Phase 3 建立用户模型与认证基础。
- 先实现后端最小闭环，是因为 API 认证和对话隔离都依赖 User 表、JWT、密码哈希和数据库 engine 抽象。

Actions taken:

- 新增 `app/db/session.py::create_database_engine()`：根据 `DATABASE_URL` backend 自动选择 SQLite 或 PostgreSQL；SQLite 保留 `check_same_thread=False`，PostgreSQL 使用 `pool_pre_ping=True`。
- 新增 `User` ORM 模型，`Conversation.user_id` nullable 外键，保持旧对话兼容。
- 新增 `UserRepository`、`UserCreate`，并扩展 `ConversationRepository` 支持按 `user_id` 过滤读取、列表、消息、删除、重命名和计数。
- 新增 `app/core/security.py`：bcrypt 密码哈希/校验、HS256 JWT 签发/校验、`get_current_user()` 认证依赖。
- 新增 `app/schemas/auth.py` 与 `app/api/auth.py`：`POST /auth/register`、`POST /auth/login`、`GET /auth/me`。
- `app/main.py` 已挂载 auth router。
- `/conversations/*` 与 `/agent/query`、`/agent/query/stream` 已接入 `get_current_user()`；`AUTH_ENABLED=false` 时兼容旧行为，`AUTH_ENABLED=true` 时要求 Bearer token。
- `pyproject.toml` 新增 `bcrypt`、`email-validator`、`psycopg2-binary`、`alembic` 依赖。
- 新增聚焦测试：
  - `tests/test_stage44_db_session.py`
  - `tests/test_stage44_auth.py`

Verification:

```text
python -m pytest tests/test_stage44_db_session.py tests/test_stage44_auth.py -q -> 9 passed
```

Risks / notes:

- Alembic 文件、docker-compose.prod.yml、前端登录入口和文档尚未完成。
- 认证默认兼容旧开发行为；生产 compose 必须显式设置 `AUTH_ENABLED=true`。
- 当前仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

### Phase 2/4/5 implementation update（Codex）

- **Status:** complete_pending_full_regression
- **Started:** 2026-06-17

Phase purpose:

- Phase 2 收尾迁移管理，确保 SQLite/PostgreSQL 双 engine 不是一次性建表，而是可由 Alembic 管理。
- Phase 4 收尾认证边界与对话隔离，确保生产启用认证后公开路由仍公开、受保护路由必须登录、conversation 不能跨用户访问。
- Phase 5 建立生产 compose 形态，把 app、PostgreSQL、healthcheck、volume、环境变量和迁移命令组织成可在服务器 smoke 的部署入口。

Actions taken:

- 新增 `alembic.ini`、`alembic/env.py`、`alembic/script.py.mako`、`alembic/versions/20260617_0001_initial_schema.py`。
- Initial migration 显式包含全部现有表 + `users` + `conversations.user_id`，旧 conversation 通过 nullable user_id 保持兼容。
- 新增 `docker-compose.prod.yml`：`app` + `db`，`db` 使用 `postgres:16-alpine` 和 named volume `postgres_data`，`app` 在 DB healthy 后执行 `alembic upgrade head` 再启动 Uvicorn。
- 更新 `Dockerfile`，把 Alembic 配置和迁移目录复制进 runtime 镜像。
- 更新 `.env.example`，增加认证和 PostgreSQL 模板变量；真实 `.env.prod` 仍由用户/部署环境本地创建且不提交。
- 新增 `docs/deployment_cloud.md`，说明服务器部署、smoke、数据目录和 PostgreSQL volume 持久化。
- 前端新增顶部登录/注册/退出入口，登录 token 存入浏览器 `localStorage`；`fetchJson()` 与 `/agent/query/stream` 统一注入 `Authorization` 请求头。
- 后端测试补充 `/health/details` 与 `/auth/login` 在认证开启时保持公开，以及 `/agent/query` 拒绝使用其他用户 conversation。

Verification:

```text
python -m pytest tests/test_stage44_auth.py tests/test_stage44_db_session.py tests/test_stage44_deployment.py tests/test_frontend_app.py -q -> 25 passed
python -m alembic upgrade head with sqlite:///data/stage44_alembic_smoke.sqlite -> passed
docker compose -f docker-compose.prod.yml --env-file .env.prod config --quiet with temporary placeholder env -> passed
```

Risks / notes:

- 尚未运行 `python -m pytest -q` 全量测试与 Stage 30 评分脚本。
- 尚未启动本地浏览器 smoke，也尚未把应用部署到云服务器进行远端 smoke。
- 临时 `.env.prod` 只用于 compose config 验证，已删除；后续仍不得写入真实 secret。
- 当前仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR，处于等待用户人工核验前的未提交开发态。

### Phase 7 remote smoke update（Codex）

- **Status:** complete
- **Date:** 2026-06-17

Actions taken:

- 重新上传阶段 44 smoke 包到云服务器。
- 远端 `docker-compose.prod.yml --env-file .env.prod config --quiet` 通过。
- Docker Hub 直连拉取 `postgres:16-alpine` 超时后，使用临时镜像预拉取并 tag。
- PyPI 直连过慢后，为 Dockerfile/compose 新增可选 `PIP_INDEX_URL` / `PIP_TRUSTED_HOST` build arg，并在远端临时 `.env.prod` 使用 Python 包镜像源。
- App 容器初次启动暴露 `scripts.sync_sources` 缺失；修复 Dockerfile，runtime 镜像复制 `scripts/`，并新增部署测试。
- 重新 build/up 后 app/db 容器均 healthy。

Verification:

```text
remote docker ps -> app Up healthy, db Up healthy, 0.0.0.0:8044->8000/tcp
remote server-local /health -> 200
remote register/login/me -> 200
remote unauthenticated /agent/query -> 401
remote authenticated /agent/query -> 200
```

Risks / notes:

- 用户已在并行智算云端口列表放行公网 TCP 8044；公网 `http://36.103.199.132:8044/health` 从本机返回 200，首页返回 200。
- 公网认证 smoke 通过：register/login/me 200，未登录 `/agent/query` 401，带 token `/agent/query` 200。
- 公网页面人工 smoke 后修复前端认证体验：未登录时会话区提示 `Sign in to load conversations`，Agent 提交提示先登录/注册；流式失败回退普通 `/agent/query` 时补充 `Authorization` header。
- 根据用户人工核验反馈，认证入口由顶部临时表单改为独立登录/注册门页：未登录隐藏工作台，注册页展示用户名/邮箱/密码规则，失败信息在表单内显示，注册成功自动登录进入对话。
- 新认证页已部署到远端运行容器和 `/home/ubuntu/rfc-rag-agent-stage44-smoke/` 源目录；公网确认 HTML/CSS/JS 均为 `phase44-auth-gate` 版本，真实公网 register/login/me smoke 通过。
- 根据用户反馈完成认证门页中文化：`登录后继续`、`登录`、`创建账号`、用户名/邮箱/密码提示、登录状态和错误提示均改为中文；公网 HTML/JS 已确认不再包含旧的 `Sign in to continue` / `Please sign in or register` 文案。
- 针对用户注册时出现“请求的接口不存在”：公网接口直测 `/auth/register` 可用；已释放误测账号，升级静态资源版本为 `phase44-auth-gate-zh-fix1`，并在前端 404 错误中加入接口路径提示。公网确认 HTML 引用新版本，JS 包含 `error.url` 与中文 404 路径提示。
- 已将修复后的 `app/frontend/index.html`、`app/frontend/static/app.js`、`app/frontend/static/styles.css` 同步到远端运行容器和 `/home/ubuntu/rfc-rag-agent-stage44-smoke/`，避免后续 rebuild 丢失该修复。
- 远端 `.env.prod` 只存在服务器运行目录，未写入仓库；本地临时部署包和 SSH 诊断日志已清理。
- 当前仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。
### 2026-06-18 Submit authorization update

- User manual verification is complete in chat.
- User explicitly authorized submitting Phase 44, uploading/merging to GitHub, and creating the phase tag.
- Data migration is intentionally deferred and remains out of this submit.
- Final local verification before submit:

```text
python -m pytest tests/test_stage44_auth.py tests/test_stage44_db_session.py tests/test_stage44_deployment.py tests/test_frontend_app.py -q -> 25 passed
python -m pytest -q -> 894 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors
sensitive-value scan -> no matches
```

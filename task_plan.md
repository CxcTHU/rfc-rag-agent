# 阶段 44 任务计划：生产部署上线（PostgreSQL + 用户注册登录 + 云端部署）

## Goal

在阶段 43 完成多轮评测 + 可观测性增强（876 tests, Stage 30 = 91.52/A/pass）的基础上，将项目从本地 SQLite 单机模式升级为可部署到云服务器的生产形态：支持 PostgreSQL、用户注册登录（JWT）、对话隔离、docker-compose 一键部署，并在已租用且完成 Docker-ready 初始化的云服务器上完成部署前 smoke 准备。完成开发、测试、普通文档与 Obsidian 草稿，停在用户人工核验前。

## Current Phase

Phase 44 planning calibration：Claude 规划方已编写任务计划、发现记录和进度文件；Codex 已根据阶段 43 合并状态与 2026-06-17 新增云服务器初始化结果完成执行前校准，等待正式创建阶段分支并按 Phase 顺序开发。

## 当前基线与工作区状态

- Git 基线：阶段 43 已完成并合并到 GitHub `origin/main -> 5596d27 Merge phase 43 multi-turn quality and observability`；`cbbc3ce Complete phase 43 multi-turn quality and observability` 是 `origin/main` 祖先。
- 本地 `main` 状态：仍停在 `d7dfca1 Merge phase 41 post-import retrieval optimization`，落后 `origin/main` 5 个提交；阶段 44 必须从 `origin/main` 创建新分支，不能从本地 stale `main` 出发。
- 当前分支：仍在 `codex/phase-43-multi-turn-quality-and-observability`，待从 `origin/main` 创建 `codex/phase-44-cloud-deployment-auth`。
- 当前工作区：`task_plan.md`、`findings.md`、`progress.md` 为阶段 44 规划校准改动；存在未跟踪 `.playwright-mcp/`，后续切分支和收尾时不得误提交无关运行产物。
- 本地 DB: SQLite, documents=753, chunks table rows=25,687，其中 indexable child chunks=19,300。
- Stage 30: 91.52 / A / pass。
- 全量测试: 876 passed。
- Docker: Dockerfile（multi-stage python:3.11-slim）+ docker-compose.yml + .dockerignore 已有（阶段 27/39）。
- 云服务器：并行智算云纯 CPU 4 核 8GB、Ubuntu 22.04 CMD、系统盘约 100GB、公网 IP `36.103.199.132`；已通过 SSH 登录并完成基础初始化。
- 服务器基础环境：已安装 git/curl/vim/ca-certificates/gnupg/lsb-release、Docker `29.1.3`、Docker Compose v2 `2.40.3`；`ubuntu` 用户可直接运行 Docker；根分区约 97GB，总可用约 86GB，内存约 8GB。
- 数据库: `app/db/session.py` 当前只支持 SQLite（`create_sqlite_engine`, `check_same_thread=False`）。
- 认证: 无用户模型、无注册登录、无 JWT、API 全开放。
- 对话: `Conversation` 和 `Message` 无 `user_id`，所有用户共享对话。
- HTTPS: 阶段 43 已有 Nginx/Caddy 反向代理模板（`deploy/` 目录）。

## Revised Goal Prompt

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及阶段 43 多轮对话质量与生产可观测性强化的验收结果，持续推进本项目开发，直到阶段 44“生产部署上线”的开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支建议为：

```text
codex/phase-44-cloud-deployment-auth
```

执行要求：

- 当前线程已改名为“阶段44-生产部署上线”。
- 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 必须确认阶段 43 已合并到 `origin/main`；当前事实为 `origin/main -> 5596d27`，包含阶段 43 合并；本地 `main -> d7dfca1` 已 stale，阶段 44 必须从 `origin/main` 出发。
- 从阶段 43 合并后的 `origin/main` 创建或切换到 `codex/phase-44-cloud-deployment-auth`。
- 可以创建或切换分支，但阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验。
- 正式开发前先校准 `task_plan.md`、`findings.md`、`progress.md`；本阶段共有 Phase 0-8（9 个 Phase），不是 8 个 Phase。
- 阶段 44 基于已租用并完成 Docker-ready 初始化的并行智算云服务器推进；该服务器用于部署前 smoke 与最终人工核验，不把远端真实部署作为本地全量测试前提。
- 严格按 Phase 0-8 顺序推进，不跳步。每开始一个 Phase，简短说明本 Phase 解决什么问题、为什么现在做。
- 每完成任意 Phase，必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 开发过程中暂不写入 Obsidian 小 Phase 汇报；全部开发完成后再统一按模板补齐。
- 阶段 44 不做多模态识别，不做复杂 LangGraph workflow，不新增爬虫或外部资料来源，不让真实 API 或云服务器成为 CI/本地全量测试前提。
- 不得把 API key、Bearer token、JWT secret、密码明文、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。

核心链路：

```text
数据库抽象（SQLite↔PostgreSQL 双 engine）
-> User 模型 + bcrypt 密码哈希 + JWT 认证
-> API 认证依赖 + 对话 user_id 隔离
-> docker-compose.prod.yml（app + PostgreSQL 一键部署）
-> Alembic 迁移管理
-> 本地全量回归 + Stage 30 不退化
-> 本地/远端 smoke（远端服务器只用于人工核验前部署验证）
-> 文档 + Obsidian 收尾
-> 停在人工核验待提交状态
```

完成标准：

- `app/db/session.py` 支持 SQLite 和 PostgreSQL 双 engine，由 `DATABASE_URL` scheme 自动切换。
- Alembic 迁移可用，initial migration 包含全部现有表 + User 表。
- 用户注册登录可用：`POST /auth/register`、`POST /auth/login`、`GET /auth/me`。
- 密码 bcrypt 哈希存储，JWT token 有过期时间，secret 从环境变量读取。
- `/agent/query`、`/agent/query/stream`、`/conversations/*` 在认证开启时需要认证；`/health`、`/health/details`、`/auth/register`、`/auth/login` 公开。
- Conversation 有 `user_id` 隔离，用户只能看到自己的对话。
- `docker-compose.prod.yml` 可一键启动 app + PostgreSQL。
- 已租用云服务器完成 Docker-ready 初始化，并在阶段收尾用于部署 smoke 或明确记录阻断原因。
- Stage 30 保持 `91.52 / A / pass` 或不退化。
- 全量测试通过。
- 普通文档与 Obsidian 草稿完成。
- 最终停在人工核验待提交状态。

## Phases

### Phase 0：启动校准与规划落盘

- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 43 已合并到 `origin/main`
- [x] 记录云服务器已租用并完成 Docker-ready 初始化
- [x] 从 `origin/main` 最新状态创建 `codex/phase-44-cloud-deployment-auth`
- [x] 校准 `task_plan.md`、`findings.md`、`progress.md`
- **Status:** complete

### Phase 1：设计文档与测试合同

- [x] 新增 `docs/stage44_cloud_deployment_auth.md`：设计文档
- [x] 明确三条主线：A（数据库抽象 SQLite↔PostgreSQL）、B（用户注册登录 + JWT）、C（docker-compose 生产部署）
- [x] 安全边界：密码 bcrypt 哈希不可逆存储、JWT secret 从环境变量读取不进 Git、不在日志/CSV/文档中记录密码或 token 明文
- [x] 新增 `tests/test_stage44_design.py` 设计合同测试
- **Status:** complete

### Phase 2：数据库抽象（SQLite ↔ PostgreSQL）

- [x] 重构 `app/db/session.py`：根据 `DATABASE_URL` scheme 自动选择 SQLite 或 PostgreSQL engine
- [x] SQLite 保留 `check_same_thread=False`；PostgreSQL 使用 `pool_pre_ping=True`
- [x] 确保所有 SQLAlchemy model 兼容 PostgreSQL（检查 Text/String 长度、Boolean、DateTime）
- [x] 新增 Alembic 迁移支持（`alembic init`、initial migration）
- [x] 新增测试验证双数据库 engine 创建逻辑
- [ ] 本地 SQLite 全量测试确认不退化
- **Status:** complete_pending_full_regression

### Phase 3：用户模型与认证

- [x] 新增 `User` 模型到 `app/db/models.py`：id, username, email, password_hash, is_active, created_at
- [x] 新增 `app/core/security.py`：bcrypt 密码哈希、JWT token 生成/验证、`JWT_SECRET_KEY` 从环境变量读取
- [x] 新增 `app/schemas/auth.py`：RegisterRequest, LoginRequest, TokenResponse, UserResponse
- [x] 新增 `app/api/auth.py`：`POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- [x] 密码存储必须 bcrypt 哈希，不可明文；JWT 有过期时间
- [x] 新增测试覆盖注册、登录、token 验证、密码不明文
- **Status:** complete

### Phase 4：API 认证中间件与对话隔离

- [x] 新增认证依赖：`get_current_user()` 从 Authorization header 解析 JWT
- [x] `/agent/query`、`/agent/query/stream`、`/conversations/*` 需要登录
- [x] `/health`、`/health/details`、`/auth/register`、`/auth/login` 保持公开
- [x] `Conversation` 新增 `user_id` 外键；用户只能看到自己的对话
- [x] Alembic migration 为现有 conversations 添加 `user_id`（nullable，旧数据兼容）
- [x] 新增测试覆盖认证拦截、对话隔离、未登录 401
- **Status:** complete_pending_full_regression

### Phase 5：docker-compose 生产部署配置

- [x] 新增 `docker-compose.prod.yml`：app service + PostgreSQL service + volume 持久化
- [x] PostgreSQL 使用 `postgres:16-alpine`，数据通过 named volume 持久化
- [x] app 等待 PostgreSQL ready 后启动（depends_on + healthcheck）
- [x] 环境变量：`DATABASE_URL=postgresql+psycopg2://...`, `JWT_SECRET_KEY`, `APP_ENV=production`
- [x] 保留原有 `docker-compose.yml` 用于本地 SQLite 开发
- [x] 新增 `.env.example` 包含所有必要环境变量模板（不含真实值）
- [x] 新增部署文档 `docs/deployment_cloud.md`
- [x] 在已初始化云服务器上准备部署 smoke 所需目录、环境变量模板和数据传输说明；不要写入真实 secret
- **Status:** complete_pending_remote_smoke

### Phase 6：全量回归与 Stage 30

- [x] 运行 `python -m pytest -q` 全量测试（SQLite 模式）
- [x] 运行 `python scripts/score_stage30_quality.py` 确认 91.52 / A / pass 或不退化
- [x] 运行 production smoke（本地 compose config + Alembic smoke）
- **Status:** complete

### Phase 7：浏览器 smoke

- [x] 启动本地服务，测试注册 → 登录 → 带 token 查询 → 对话隔离
- [x] 桌面 + 390x844 移动端 smoke
- [x] 验证未登录时 agent 接口返回 401
- [x] 如 Phase 5 产物通过本地验证，在云服务器上执行部署 smoke：server-local `127.0.0.1:8044` 通过 health/register/login/me/unauth 401/auth Agent 200，app/db containers healthy；云平台已放行公网 TCP 8044，公网 `http://36.103.199.132:8044` 通过 health/home/auth/query smoke
- **Status:** complete

### Phase 8：文档与 Obsidian 收尾

- [x] 更新 `README.md`（新增认证说明、部署说明）
- [x] 更新 `docs/progress.md`
- [x] 更新 `docs/architecture.md`（新增 User/Auth/PostgreSQL 模块）
- [x] 新增 `docs/phase_reviews/phase-44.md` 验收草稿
- [x] 更新 Obsidian：阶段 44 页、Phase 汇报、阶段索引、首页
- [x] 最终不执行 git add/commit/tag/push，停在人工核验前
- **Status:** complete

## 完成标准

- `app/db/session.py` 支持 SQLite 和 PostgreSQL 双 engine，由 `DATABASE_URL` scheme 自动切换。
- Alembic 迁移可用，initial migration 包含所有现有表 + User 表。
- 用户注册登录可用：`POST /auth/register`、`POST /auth/login`、`GET /auth/me`。
- 密码 bcrypt 哈希存储，JWT token 有过期时间，secret 从环境变量读取。
- `/agent/query`、`/conversations/*` 需要认证；`/health`、`/auth/*` 公开。
- Conversation 有 user_id 隔离，用户只能看到自己的对话。
- `docker-compose.prod.yml` 可一键启动 app + PostgreSQL。
- 部署文档清晰可操作。
- Stage 30 保持 91.52 / A / pass 或不退化。
- 全量测试通过（SQLite 模式）。
- 普通文档与 Obsidian 草稿完成。
- 最终停在人工核验前，不 git add/commit/tag/push/PR。
## 2026-06-18 Submit Authorization Update

- User manual verification is complete in chat.
- User explicitly authorized submitting Phase 44, uploading/merging to GitHub, and creating the phase tag.
- Data migration is intentionally deferred and remains out of this submit.
- Final local verification before submit: focused Phase 44 tests `25 passed`, full regression `894 passed`, Stage 30 `91.52 / A / pass`.

# 阶段 49 任务计划：本地 PostgreSQL 迁移与云端数据同步

## Goal

将本地开发环境从 SQLite 切换到 PostgreSQL，消除 dev/prod 数据库差异；同时把 Phase 45-48 新增的数据（table chunks、image_description chunks、表格 embedding、用户认证等）同步到云端 PostgreSQL，完成图片资产上传，并在云端验证 Phase 47-48 新功能（表格检索、用户图片分析、视觉意图门控）端到端可用。

## Current Phase

Phase 0：启动校准。

## 前置条件

- 阶段 48 已合并到 `main`，`phase-48-complete` tag 已确认
- 云端服务器 `36.103.199.132` 在 Phase 44 已完成 Docker + PostgreSQL + 认证 smoke test
- `scripts/migrate_sqlite_to_postgres.py` 已存在且可用
- `docker-compose.prod.yml` 已配置 PostgreSQL 16 + FastAPI 双容器
- 本地 Docker Desktop 已安装

## Phases

### Phase 0：启动校准（主 agent）

- [ ] 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md
- [ ] 阅读根目录 task_plan.md、findings.md、progress.md
- [ ] 运行 `git status -sb` 与 `git log --oneline -5`
- [ ] 确认阶段 48 已合并到 `main`，`phase-48-complete` tag 存在且未移动
- [ ] 从 `main` 创建 `codex/phase-49-local-postgresql-cloud-sync`
- [ ] 校准 task_plan.md、findings.md、progress.md

### Phase 1：本地 PostgreSQL 容器搭建

- [ ] 创建 `docker-compose.dev.yml`：PostgreSQL 16 容器，端口 5433（避免与生产冲突），volume `pgdata_dev`
- [ ] 新增 `.env.dev.example` 模板：`DATABASE_URL=postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev`
- [ ] 启动容器验证 `pg_isready` 通过
- [ ] 更新 `app/core/config.py` 的 `database_url` 默认值说明（仍保留 SQLite 作为 fallback 默认值，但文档说明推荐 PostgreSQL）

### Phase 2：本地数据库切换与数据迁移

- [ ] 运行 `alembic upgrade head` 对本地 PostgreSQL 创建全部表结构
- [ ] 运行 `python scripts/migrate_sqlite_to_postgres.py` 将 SQLite 数据导入 PostgreSQL
- [ ] 验证迁移完整性：documents、sources、chunks（含 table chunks）、chunk_embeddings（含 table embeddings）、qa_logs、users、conversations、messages 行数一致
- [ ] 检查并修复 SQLite 特有代码：
  - `check_same_thread` 只对 SQLite 生效（已在 `session.py` 处理）
  - `func.json_extract` 等 SQLite-only 函数（如有）
  - 任何硬编码 `sqlite:///` 的测试或脚本
- [ ] 切换本地 `.env` 的 `DATABASE_URL` 为 PostgreSQL 连接串

### Phase 3：本地 FAISS 重建与回归验证

- [ ] 从 PostgreSQL 重建 FAISS 索引：`python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048`
- [ ] 验证 FAISS 向量数量与 SQLite 时期一致（~40563）
- [ ] 运行全量 pytest，确认不退化
- [ ] 运行 Stage 30 评分，确认 91.52/A/pass
- [ ] 浏览器 smoke：Agent 查询、表格检索、图片检索、用户图片上传在本地 PostgreSQL 环境下可用

### Phase 4：SQLite 双引擎边界清理

- [ ] 审计所有 `.py` 文件中 SQLite 特有用法（`check_same_thread`、`:memory:`、`connect_args` 等），确保 PostgreSQL 路径无死代码
- [ ] 审计 Alembic 迁移脚本，确认 `batch_alter_table` 等 SQLite workaround 在 PostgreSQL 下不产生错误
- [ ] 审计测试中的 `sqlite:///:memory:` 用法，确保测试数据库引擎选择与生产一致或有明确隔离
- [ ] 更新 `.env.example` 和 `docs/deployment_guide.md`，标注推荐使用 PostgreSQL

### Phase 5：云端 PostgreSQL 数据同步

- [ ] 确认云端 PostgreSQL 的连接方式和当前数据状态（Phase 44 smoke 数据 vs 空库）
- [ ] 在本地准备迁移数据包（或直接用迁移脚本连接远程 PostgreSQL）
- [ ] 运行 `migrate_sqlite_to_postgres.py` 将完整本地数据同步到云端 PostgreSQL
- [ ] 验证云端 PostgreSQL 行数与本地一致

### Phase 6：云端图片资产同步

- [ ] 准备图片资产清单：`data/images/` 下约 14000+ 提取图片
- [ ] 确定传输方案：rsync / scp / 打包上传（根据服务器访问方式决定）
- [ ] 同步图片到云端服务器对应目录
- [ ] 验证云端图片路径与本地一致，`/assets/images/...` 能正常访问

### Phase 7：云端 FAISS 重建与应用部署

- [ ] 在云端从 PostgreSQL 重建 FAISS 索引
- [ ] 更新云端 docker-compose.prod.yml 镜像到包含 Phase 47-48 代码的版本
- [ ] `docker compose -f docker-compose.prod.yml up -d --build`
- [ ] 云端 health check、auth 验证

### Phase 8：云端功能 smoke 验证

- [ ] 基础 API smoke：/health、/search/hybrid、/agent/query、/quality-report
- [ ] Phase 47 功能验证：
  - `search_tables` 返回表格 evidence
  - 用户图片上传 + `analyze_user_image` 流程
  - 视觉意图门控（纯文字查询不返回图片）
- [ ] Phase 44 认证：register/login/me/auth guard
- [ ] 前端渲染：figure evidence card、表格 evidence card、citation drawer

### Phase 9：文档 + Obsidian 收尾

- [ ] 同步 README.md（说明推荐 PostgreSQL、Docker Compose 开发环境）
- [ ] 同步 docs/progress.md
- [ ] 同步 docs/architecture.md（更新数据库层从 SQLite → PostgreSQL）
- [ ] 同步 docs/deployment_guide.md（本地开发 + 云端部署双路径）
- [ ] 新增 docs/phase_reviews/phase-49.md 验收草稿
- [ ] Obsidian 本地知识库收尾：
  - 新建 `obsidian-vault/阶段/阶段 49 - 本地 PostgreSQL 迁移与云端数据同步.md`
  - 新建 `obsidian-vault/阶段汇报/阶段 49 - 本地 PostgreSQL 迁移与云端数据同步/` 目录
  - Phase 汇报索引 + 每个 Phase 的 10 项小汇报
  - 更新 `obsidian-vault/阶段汇报索引.md`
- [ ] 全量 pytest 通过，Stage 30 不退化
- [ ] 停在用户人工核验前状态

## 安全边界

- Stage 30 必须保持 91.52/A/pass 或不退化
- 不把 `.env.prod`、JWT secret、数据库密码、SSH 密码、API key、Bearer token、供应商原始响应写入 Git/CSV/文档/测试/Obsidian
- `.env.dev.example` 只包含示例值，不含真实密码
- 未经用户人工核验，不 git add/commit/tag/push/建 PR
- 云端操作如需 SSH/远程执行，仅在用户授权后进行
- 不删除本地 SQLite 文件（保留作为备份/回滚）
- `data/images/` 仍然 gitignored，只做本地/云端同步

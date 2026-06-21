# 阶段 49 任务计划：本地 PostgreSQL 迁移与云端数据同步

## Goal

将本地开发环境从 SQLite 切换到 PostgreSQL，消除 dev/prod 数据库差异；同时把 Phase 45-48 新增的数据（table chunks、image_description chunks、表格 embedding、用户认证等）同步到云端 PostgreSQL，完成图片资产上传，并在云端验证 Phase 47-48 新功能（表格检索、用户图片分析、视觉意图门控）端到端可用。

## Current Phase

Phase 9：文档 + Obsidian 收尾。

## 前置条件

- 阶段 48 已合并到 `main`，`phase-48-complete` tag 已确认
- 云端服务器 `36.103.199.132` 在 Phase 44 已完成 Docker + PostgreSQL + 认证 smoke test
- `scripts/migrate_sqlite_to_postgres.py` 已存在且可用
- `docker-compose.prod.yml` 已配置 PostgreSQL 16 + FastAPI 双容器
- 本地 Docker Desktop 已安装

## Phases

### Phase 0：启动校准（主 agent）

- [x] 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md
- [x] 阅读 docs/phase_reviews/phase-48.md、docs/phase48_evaluation_report.md
- [x] 阅读根目录 task_plan.md、findings.md、progress.md
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 48 已合并到 `main`，`phase-48-complete` tag 存在且未移动
- [x] 从 `main` 创建 `codex/phase-49-local-postgresql-cloud-sync`
- [x] 校准 task_plan.md、findings.md、progress.md

### Phase 1：本地 PostgreSQL 容器搭建

- [x] 创建 `docker-compose.dev.yml`：PostgreSQL 16 容器，端口 5433（避免与生产冲突），volume `pgdata_dev`
- [x] 新增 `.env.dev.example` 模板：`DATABASE_URL=postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev`
- [x] 启动容器验证 `pg_isready` 通过
- [x] 更新 `app/core/config.py` 的 `database_url` 默认值说明（仍保留 SQLite 作为 fallback 默认值，但文档说明推荐 PostgreSQL）
- [x] 新增聚焦测试锁定 dev compose 与示例环境文件

### Phase 2：本地数据库切换与数据迁移

- [x] 运行 `alembic upgrade head` 对本地 PostgreSQL 创建全部表结构
- [x] 修复 `scripts/migrate_sqlite_to_postgres.py` 的 Phase 46-48 字段与表覆盖：`caption`、`page_number`、`content_bbox_json`、`users`、`conversations`、`messages`、`qa_feedback`
- [x] 新增 Alembic `20260621_0006`，将 `chunks.heading_path` 扩为 `Text`，修复 SQLite 不强制长度而 PostgreSQL 拒绝超长路径的问题
- [x] 运行 `python scripts/migrate_sqlite_to_postgres.py` 将 SQLite 数据导入 PostgreSQL
- [x] 第二次运行迁移脚本验证幂等性
- [x] 验证迁移完整性：documents、sources、chunks（含 table/image_description chunks）、chunk_embeddings（含 table/image embeddings）、qa_logs、users、conversations、messages、qa_feedback 行数一致
- [x] 检查并修复 SQLite/PostgreSQL 差异：
  - `check_same_thread` 只对 SQLite 生效（已在 `session.py` 处理）
  - `func.json_extract` 等 SQLite-only 函数（如有）
  - 任何硬编码 `sqlite:///` 的测试或脚本
- [x] 切换本地 `.env` 的 `DATABASE_URL` 为 PostgreSQL 连接串

### Phase 3：本地 FAISS 重建与回归验证

- [x] 从 PostgreSQL 重建 FAISS 索引：`python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048`
- [x] 验证 FAISS 向量数量与 SQLite 时期一致（40563）
- [x] 运行全量 pytest，确认不退化
- [x] 运行 Stage 30 评分，确认 91.52/A/pass
- [x] 浏览器 smoke：Agent 查询、表格/图片 evidence 渲染、用户图片上传入口和 deterministic vision 安全拒答在本地 PostgreSQL 环境下可用

### Phase 4：SQLite 双引擎边界清理

- [x] 审计所有 `.py` 文件中 SQLite 特有用法（`check_same_thread`、`:memory:`、`connect_args` 等），确保 PostgreSQL 路径无死代码
- [x] 审计 Alembic 迁移脚本，确认 `batch_alter_table` 等 SQLite workaround 在 PostgreSQL 下不产生错误
- [x] 审计测试中的 `sqlite:///:memory:` 用法，确保测试数据库引擎选择与生产一致或有明确隔离
- [x] 更新 `.env.example` 和 `docs/deployment_guide.md`，标注推荐使用 PostgreSQL
- [x] 保留测试 fixture 的 SQLite 临时库作为快速隔离测试，不把它误判为运行时死代码

### Phase 5：云端 PostgreSQL 数据同步

- [x] 确认公开云端服务仍可达：`http://36.103.199.132:8044/health` 和首页均返回 200
- [x] 记录云端 PostgreSQL 真实写入需要 SSH/数据库密钥，当前 Codex 无法直接执行
- [x] 准备 `docs/phase49_cloud_sync_runbook.md`，记录本地到云端 PostgreSQL 迁移命令与行数验证命令
- [x] 标注云端 PostgreSQL 数据同步需要用户手动执行或另行授权后执行

### Phase 6：云端图片资产同步

- [x] 准备图片资产清单：`data/images/` 当前 16978 文件、854 目录，PostgreSQL image chunks with paths=15628
- [x] 确定传输方案：优先 rsync，Windows fallback 为 zip + scp
- [x] 在 `docs/phase49_cloud_sync_runbook.md` 记录同步与验证命令
- [x] 云端图片已同步；公开检查 `/assets/images/1059/page10_img1.png` 返回 200 OK

### Phase 7：云端 FAISS 重建与应用部署

- [x] 在 `docs/phase49_cloud_sync_runbook.md` 记录云端从 PostgreSQL 重建 FAISS 的命令和 `vectors=40563` 验证点
- [x] 记录 `docker compose -f docker-compose.prod.yml up -d --build` 部署命令
- [x] 记录云端 health/auth 验证命令
- [x] 云端 FAISS 已从云端 PostgreSQL 重建，输出 `vectors=40563`；应用已重启且 `/health` 返回 200

### Phase 8：云端功能 smoke 验证

- [x] 基础 API smoke：公开 `/health` 和首页当前 200；完整 `/search/hybrid`、`/agent/query`、`/quality-report` 需在云端数据同步后执行
- [x] Phase 47 功能验证命令已写入 runbook：
  - `search_tables` 返回表格 evidence
  - 用户图片上传 + `analyze_user_image` 流程
  - 视觉意图门控（纯文字查询不返回图片）
- [x] Phase 44 认证：register/login/me/auth guard 命令已写入 runbook
- [x] 前端渲染：figure evidence card、表格 evidence card、citation drawer、上传控件列入 runbook checklist
- [x] 标注真实云端 smoke 需用户手动执行或另行授权

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
- [x] 用户已在 2026-06-21 授权提交、打 tag、推送并合并

## 安全边界

- Stage 30 必须保持 91.52/A/pass 或不退化
- 不把 `.env.prod`、JWT secret、数据库密码、SSH 密码、API key、Bearer token、供应商原始响应写入 Git/CSV/文档/测试/Obsidian
- `.env.dev.example` 只包含示例值，不含真实密码
- 未经用户人工核验，不 git add/commit/tag/push/建 PR；2026-06-21 用户已授权阶段 49 提交合并
- 云端操作如需 SSH/远程执行，仅在用户授权后进行
- 不删除本地 SQLite 文件（保留作为备份/回滚）
- `data/images/` 仍然 gitignored，只做本地/云端同步

## 完成标准

- `docker-compose.dev.yml` 可一键启动本地 PostgreSQL 16，宿主端口为 5433。
- 本地 `DATABASE_URL` 可切换到 PostgreSQL；Alembic 建表与迁移脚本导入完成。
- PostgreSQL 中 Phase 45-48 数据完整，尤其是 table/image_description chunks、caption/page/bbox metadata、chunk embeddings、users 与 qa_feedback。
- 本地 FAISS 从 PostgreSQL 重建，`paratera / GLM-Embedding-3 / dim2048` 向量数约等于 Phase 48 基线 40563。
- 全量 pytest 通过，Stage 30 保持 `91.52 / A / pass`。
- 本地浏览器 smoke 覆盖 Agent 查询、`search_tables`、图片检索、用户图片上传。
- SQLite 特有代码边界清晰：SQLite 仅作 fallback/测试 fixture/备份，不作为阶段 49 主运行库。
- 云端 PostgreSQL 与 `data/images/` 同步方案、命令、验证结果或人工执行说明完整记录。
- README、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/deployment_guide.md、docs/phase_reviews/phase-49.md 与 Obsidian 草稿完成。
- 用户授权后执行 `git add`、提交、`phase-49-complete` tag、推送、PR 和 GitHub merge。
## Phase 9 收尾状态补记（2026-06-20）

- [x] README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/deployment_guide.md、AGENT.MD 已补充阶段 49 本地 PostgreSQL、FAISS、云端 runbook 和未提交边界。
- [x] `docs/phase_reviews/phase-49.md` 已新增。
- [x] Obsidian 已新增 `obsidian-vault/阶段/阶段 49 - 本地 PostgreSQL 迁移与云端数据同步.md`。
- [x] Obsidian 已新增 `obsidian-vault/阶段汇报/阶段 49 - 本地 PostgreSQL 迁移与云端数据同步/`，包含 Phase 0-9 小汇报和 `阶段 49 Phase 汇报索引.md`。
- [x] `obsidian-vault/阶段汇报索引.md` 与 `obsidian-vault/阶段索引.md` 已补充阶段 49 入口。
- [x] 全量 pytest 已在 Phase 3 通过：`1035 passed`；Stage 30 已验证 `91.52 / A / pass`。
- [x] 当前停在用户人工核验前状态：未 `git add`、未 commit、未 tag、未 push、未 PR。

遗留人工步骤：云端 PostgreSQL 数据同步、`data/images/` 同步、云端 FAISS 重建、生产 compose 重启和完整云端 smoke 需用户按 `docs/phase49_cloud_sync_runbook.md` 手动执行或另行授权。
## Phase 9 最终验证补记（2026-06-20）

- [x] `python -m pytest tests\test_phase49_local_postgres_dev.py tests\test_stage45_migration.py tests\test_stage44_db_session.py -q -> 11 passed`
- [x] `python -m pytest -q -> 1037 passed`
- [x] `python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- [x] 停在人工核验前：未 `git add`、未 commit、未 tag、未 push、未 PR。
## Cloud PostgreSQL 全量迁移完成补记（2026-06-20）

- [x] 根据用户新目标，切换为 Local PostgreSQL -> Cloud PostgreSQL 全量迁移。
- [x] 审计本地 PG 基线：核心表、chunk_type、embedding、用户列表正常。
- [x] 备份云端原阶段 44 smoke 数据库：`/home/ubuntu/phase49_pre_restore_20260620_214251.dump`。
- [x] 从本地 PG 生成 custom dump：`phase49_local_pg.dump`，约 453.5MB。
- [x] 上传 dump 到云端：`/home/ubuntu/phase49_local_pg.dump`。
- [x] 停止云端 app，drop/create 云端目标库，执行 `pg_restore`。
- [x] 校验云端 PG 与本地 PG：核心 counts、chunk_type、embedding 分组、Alembic 版本、documents/chunks 指纹和 sequences 一致。
- [x] 重建并启动云端 app，`/health` 返回 production ok。
- [x] 用户已在 2026-06-21 授权提交、打 tag、推送并合并。

## Cloud FAISS 与提交授权补记（2026-06-21）

- [x] 云端 FAISS 已从云端 PostgreSQL 重建：`provider=paratera model=GLM-Embedding-3 dimension=2048 vectors=40563`。
- [x] 云端应用已重启，`/health` 返回 production 200。
- [x] 公网图片资产 `/assets/images/1059/page10_img1.png` 返回 200 OK。
- [x] 用户已明确要求按 AGENT 提交阶段 49 整体开发工作、上传 merge 至 GitHub 并打 tag。
## Cloud Image Asset Sync 完成补记（2026-06-21）

- [x] 确认云端 `data/images` 初始为 0 文件，示例图片 URL 返回 404。
- [x] 确认本地 `data/images` 为 16978 文件，约 3.01GB。
- [x] 生成本地 tar：`C:\Users\admin\AppData\Local\Temp\phase49_data_images.tar`。
- [x] 上传到云端：`/home/ubuntu/phase49_data_images.tar`。
- [x] 解包到：`/home/ubuntu/rfc-rag-agent-stage44-smoke/data/images`。
- [x] 云端文件数验证：16978。
- [x] 内网与公网 `/assets/images/1059/page10_img1.png` 均返回 200 OK。
- [x] 保持未提交状态：未 `git add`、未 commit、未 tag、未 push、未 PR。

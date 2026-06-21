# 阶段 49 Session Progress

## 阶段信息

- 阶段: 49 — 本地 PostgreSQL 迁移与云端数据同步
- 目标分支: `codex/phase-49-local-postgresql-cloud-sync`
- 基线: 阶段 48 合并后的 `main`
- 状态: 尚未创建开发分支，等待 Codex 启动
- Git 边界: 未经用户人工核验，不 git add/commit/tag/push/建 PR

## 启动校准

- [x] 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md
- [x] 阅读 docs/phase_reviews/phase-48.md、docs/phase48_evaluation_report.md
- [x] 阅读根目录 task_plan.md、findings.md、progress.md
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 48 已合并到 `main`，`phase-48-complete` tag 存在且未移动
- [x] 从 `main` 创建 `codex/phase-49-local-postgresql-cloud-sync`
- [x] 校准基线

## 执行进展

- [x] Phase 0: 启动校准
- [x] Phase 1: 本地 PostgreSQL 容器搭建
- [x] Phase 2: 本地数据库切换与数据迁移
- [x] Phase 3: 本地 FAISS 重建与回归验证
- [x] Phase 4: SQLite 双引擎边界清理
- [x] Phase 5: 云端 PostgreSQL 数据同步（Codex 可准备部分完成；真实远程写入待用户手动执行/授权）
- [x] Phase 6: 云端图片资产同步（Codex 可准备部分完成；真实远程文件同步待用户手动执行/授权）
- [x] Phase 7: 云端 FAISS 重建与应用部署（命令与验证点完成；真实远程执行待用户手动执行/授权）
- [x] Phase 8: 云端功能 smoke 验证（公开 health/home 检查完成；完整云端 smoke 待用户手动执行/授权）
- [ ] Phase 9: 文档 + Obsidian 收尾

## 当前状态

Codex 已启动阶段 49，当前分支为 `codex/phase-49-local-postgresql-cloud-sync`。

## Phase 0 日志：启动校准

时间：2026-06-20

- 已按入口规则阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-48.md`、`docs/phase48_evaluation_report.md`、`task_plan.md`、`findings.md`、`progress.md`。
- `git status -sb`：`## main...origin/main`，启动前工作树干净。
- `git log --oneline -5 --decorate`：`main` / `origin/main` / `origin/HEAD` 位于 `4fefaafc Merge pull request #13 from CxcTHU/codex/phase-48-multimodal-evaluation`。
- `phase-48-complete` 是 annotated tag，tag 对象指向 `4fefaafc`；未移动任何已有阶段 tag。
- `phase-48-complete` 已确认是 `main` 的祖先；`main` 没有停在阶段 47 合并点，因此可以从 Phase 48 合并后的正确基线继续。
- 已创建并切换到 `codex/phase-49-local-postgresql-cloud-sync`。
- 已盘点 `app/db/session.py`：SQLite 分支使用 `check_same_thread=False`，PostgreSQL 分支使用 `pool_pre_ping=True`。
- 已盘点 `scripts/migrate_sqlite_to_postgres.py`：现有幂等迁移覆盖 documents/sources/chunks/chunk_embeddings/qa_logs，但缺少 Phase 46-48 的 `caption`、`page_number`、`content_bbox_json` 字段以及 `users`、`conversations`、`messages`、`qa_feedback` 表。
- 已盘点 `docker-compose.prod.yml`：生产 PostgreSQL 16、`postgres_data`、healthcheck 与 `alembic upgrade head` 启动链路可复用。

测试结果：Phase 0 为校准阶段，尚未运行代码测试。

遗留风险：本地 Docker/PostgreSQL 可用性尚未验证；迁移脚本需要在 Phase 2 修复覆盖范围后再做真实导入。

提交状态：尚未 `git add`，尚未 commit/tag/push/PR，等待阶段开发完成后由用户人工核验。

## Phase 1 日志：本地 PostgreSQL 容器搭建

时间：2026-06-20

- 新增 `docker-compose.dev.yml`，提供本地 PostgreSQL 16 容器，宿主端口 `5433`，数据卷 `pgdata_dev`，healthcheck 使用 `pg_isready`。
- 新增 `.env.dev.example`，给出本地开发 PostgreSQL `DATABASE_URL` 示例。
- 更新 `.env.example` 与 `app/core/config.py` 注释：SQLite 保留为 fallback/测试路径，阶段 49 推荐本地 PostgreSQL 开发以贴近生产。
- 新增 `tests/test_phase49_local_postgres_dev.py`，锁定 dev compose、示例连接串和“不出现 token/API secret”边界。

验证结果：

```text
docker compose -f docker-compose.dev.yml config -> passed
docker version --format '{{.Server.Version}}' -> 29.5.3
python -m pytest tests\test_phase49_local_postgres_dev.py tests\test_stage44_db_session.py -q -> 7 passed
docker compose -f docker-compose.dev.yml up -d db -> container started
docker inspect rfc-rag-postgres-dev health -> healthy
docker exec rfc-rag-postgres-dev pg_isready -U rfc_user -d rfc_rag_dev -> accepting connections
```

说明：启动时 Docker Compose 提示存在历史 orphan container `rfc-rag-agent-rfc-rag-agent-1`，未执行清理，避免影响用户已有运行状态。

遗留风险：本地 PostgreSQL 当前为空库，Phase 2 需要运行 Alembic 并修复迁移脚本后导入完整 SQLite 数据。

提交状态：尚未 `git add`，尚未 commit/tag/push/PR。

## Phase 5-8 日志：云端同步、资产、部署与 smoke 准备

时间：2026-06-20

- 公开检查 `http://36.103.199.132:8044/health`：返回 `{"status":"ok","service":"RFC-RAG-Agent","environment":"production"}`。
- 公开检查 `http://36.103.199.132:8044/`：HTTP 200。
- 公开检查 `http://36.103.199.132:8044/assets/images/1059/page10_img1.png`：404，说明云端图片资产尚未完成同步。
- 本地资产盘点：`data/images` 文件数 16978，目录数 854；PostgreSQL image chunks with paths=15628。
- 新增 `docs/phase49_cloud_sync_runbook.md`，记录云端 PostgreSQL 数据同步、图片资产同步、云端 FAISS 重建、生产 compose 部署、认证与多模态 smoke 验证命令。
- 补充 runbook 安全测试，禁止真实 token/secret 形态进入文档。
- 清理本地 browser smoke 产生的测试用户和消息，使本地 PostgreSQL 回到 `users=3`、`messages=117`。

验证结果：

```text
public cloud /health -> 200 production
public cloud / -> 200
public cloud /assets/images/1059/page10_img1.png -> 404
local data/images files -> 16978
local PostgreSQL image chunks with source_image_path -> 15628
python -m pytest tests\test_phase49_local_postgres_dev.py -q -> 4 passed
```

远程执行状态：

```text
Codex cannot execute SSH/cloud DB/file sync without credentials in this thread.
Manual runbook is ready at docs/phase49_cloud_sync_runbook.md.
Cloud PostgreSQL row sync, data/images sync, cloud FAISS rebuild, docker compose deploy, and authenticated multimodal smoke remain manual/authorized remote steps.
```

提交状态：尚未 `git add`，尚未 commit/tag/push/PR。

## Phase 4 日志：SQLite 双引擎边界清理

时间：2026-06-20

- 使用 `rg` 审计 `check_same_thread`、`:memory:`、`sqlite3.connect`、`sqlite://`、`connect_args`、`batch_alter_table`、`json_extract` 等 SQLite/双引擎关键词。
- 确认运行时引擎入口集中在 `app/db/session.py`：SQLite 和 PostgreSQL 分支清晰。
- 确认 Alembic 迁移无 `batch_alter_table`；新增 `20260621_0006` 已在 PostgreSQL 执行。
- 保留测试和历史数据修复脚本中的 SQLite 临时库/本地库用法，不作为生产死代码删除。
- 更新 `docs/deployment_guide.md`：阶段 49 后推荐本地 PostgreSQL dev，旧 SQLite compose 标为 fallback/历史路径。
- 扩展 `tests/test_phase49_local_postgres_dev.py` 覆盖部署指南。

验证结果：

```text
python -m pytest tests\test_phase49_local_postgres_dev.py tests\test_stage44_db_session.py tests\test_stage45_migration.py tests\test_stage39_deployment_docs.py tests\test_stage44_deployment.py -q -> 18 passed
```

遗留风险：

- 仍存在大量 Phase 45/46 `sqlite3.connect()` 本地修复脚本，它们是历史 SQLite 黄金库维护能力；云端和本地 PostgreSQL 主路径不应依赖这些脚本。
- 旧 `docker-compose.yml` 仍是 SQLite fallback，后续文档需持续引导用户优先使用 `docker-compose.dev.yml` 或 `docker-compose.prod.yml`。

提交状态：尚未 `git add`，尚未 commit/tag/push/PR。

## Phase 3 日志：本地 FAISS 重建与回归验证

时间：2026-06-20

- 使用 PostgreSQL `DATABASE_URL` 重建 `paratera / GLM-Embedding-3 / dim2048` FAISS。
- 运行 Stage 30 评分。
- 运行 Agent/table/FAISS 聚焦测试和全量 pytest。
- 启动本地 8050 服务做浏览器 smoke；为避免真实 API 成为本地 smoke 前提，显式使用 deterministic chat/embedding/vision 环境。
- 通过 Playwright CLI 验证登录/注册、工作台渲染、历史图片 evidence card、Agent 表格问题、图片上传入口和 deterministic vision 安全拒答。
- 结束 8050 服务并关闭 Playwright 浏览器。

验证结果：

```text
python scripts\build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 --database-url postgresql+psycopg2://... -> vectors=40563
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest tests\test_faiss_index.py tests\test_vector_cache_faiss.py tests\test_agent_tools.py tests\test_phase47_tables.py -q -> 27 passed
python -m pytest -q -> 1035 passed
browser smoke -> registered local smoke user, workspace rendered, existing figure evidence cards visible, Agent deterministic answer returned citation, image chooser/upload state visible, deterministic vision refusal rendered
```

错误与解决：

```text
initial /agent/query API smoke used wrong field name task -> 422; corrected schema is question
real-provider Agent smoke timed out / was too slow for automated local smoke -> restarted server with deterministic chat/embedding/vision for repeatable UI smoke
first browser register used invalid .example.test email -> frontend/API returned 422; changed to phase49smoke@example.com and registration succeeded
```

遗留风险：

- Phase 3 的 browser smoke 没有把真实 GLM image/table query embedding 作为必跑前提；真实 provider 路径已在 Phase 48 gate 中验证，阶段 49 后续云端 smoke可在人工授权环境下再跑。
- 本地 smoke 创建了 `phase49smoke` 测试用户和少量本地会话/上传运行态数据，位于本地 PostgreSQL 和 gitignored runtime 目录，不进入 Git。

提交状态：尚未 `git add`，尚未 commit/tag/push/PR。

## Phase 2 日志：本地数据库切换与数据迁移

时间：2026-06-20

- 扩展 `scripts/migrate_sqlite_to_postgres.py`：
  - `chunks` 迁移补齐 `caption`、`page_number`、`content_bbox_json`。
  - 新增 `users`、`conversations`、`messages`、`qa_feedback` 迁移。
  - 通过 source -> target id map 重建 user/conversation/message/feedback 关系。
- 扩展 `tests/test_stage45_migration.py`，覆盖 Phase 46-48 metadata、用户、会话、消息和反馈的迁移与幂等。
- 运行本地 PostgreSQL Alembic：先升级到 `20260621_0005`，迁移时发现 `chunks.heading_path` 超出 PostgreSQL `varchar(500)`。
- 新增 `alembic/versions/20260621_0006_chunk_heading_path_text.py`，并把 `app/db/models.py::Chunk.heading_path` 改为 `Text`。
- 重新执行 Alembic 到 `20260621_0006 (head)`。
- 执行 SQLite -> PostgreSQL 全量迁移，并二次执行验证幂等。
- 定向更新本地 `.env` 的 `DATABASE_URL` 为本地 PostgreSQL dev 连接串，未读取或输出其他 `.env` 内容。

验证结果：

```text
python -m pytest tests\test_stage45_migration.py tests\test_phase49_local_postgres_dev.py -q -> 4 passed
python -m alembic upgrade head (PostgreSQL) -> 20260621_0006
first migration -> documents=1146, sources=1073, chunks=50250, chunk_embeddings=72579, users=3, conversations=7, messages=117
second migration -> inserted=0 for existing migrated tables
PostgreSQL chunk_type counts -> text=33182, image_description=15628, table=1440
PostgreSQL GLM embeddings -> 40563
python -m pytest tests\test_stage45_migration.py tests\test_phase49_local_postgres_dev.py tests\test_stage44_db_session.py -q -> 9 passed
app SessionLocal query through .env PostgreSQL -> backend=postgresql, documents=1146
```

错误与解决：

```text
error: psycopg2.errors.StringDataRightTruncation on chunks.heading_path varchar(500)
root cause: SQLite did not enforce String(500), PostgreSQL does
resolution: widen chunks.heading_path to Text via Alembic 20260621_0006 and ORM model update
```

遗留风险：

- 直接用 Python `sqlite3.connect('data/app.sqlite')` 做源库 count 曾超时；迁移脚本已完整读源并成功导入，目标库计数与迁移输出一致。后续如需源库只读审计，应拆成专用脚本或使用迁移结果作为对账依据。
- `qa_feedback` 当前源库为 0，因此迁移代码有测试覆盖但本地真实数据没有反馈行可验证。

提交状态：尚未 `git add`，尚未 commit/tag/push/PR。
## Phase 9 日志：文档 + Obsidian 收尾

时间：2026-06-20

- 更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD，记录 Phase 49 基线、本地 PostgreSQL 迁移、FAISS 40563、pytest 1035、Stage 30 91.52/A/pass、云端图片 404 缺口和未提交边界。
- 新增 `docs/phase_reviews/phase-49.md`。
- 新增 Obsidian 阶段页 `obsidian-vault/阶段/阶段 49 - 本地 PostgreSQL 迁移与云端数据同步.md`。
- 新增 Obsidian 阶段汇报目录 `obsidian-vault/阶段汇报/阶段 49 - 本地 PostgreSQL 迁移与云端数据同步/`，包含 Phase 0-9 小汇报和 `阶段 49 Phase 汇报索引.md`。
- 更新 `obsidian-vault/阶段汇报索引.md` 和 `obsidian-vault/阶段索引.md`。
- 校准 `task_plan.md`、`findings.md`、`progress.md` 的阶段 49 收尾状态。

验证状态：
```text
Phase 3 full pytest -> 1035 passed
Phase 3 Stage30 -> 91.52 / A / pass
Phase 9 docs/tests final focused rerun -> pending in current closeout
```

遗留风险：
- 云端 PostgreSQL 数据同步、`data/images/` 同步、云端 FAISS 重建、生产 compose 和完整云端 smoke 仍需用户按 `docs/phase49_cloud_sync_runbook.md` 手动执行或另行授权。
- 当前未 `git add`、未 commit、未 tag、未 push、未 PR，等待用户人工核验。
## Phase 9 最终验证补记

时间：2026-06-20

```text
python -m pytest tests\test_phase49_local_postgres_dev.py tests\test_stage45_migration.py tests\test_stage44_db_session.py -q -> 11 passed
python -m pytest -q -> 1037 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
```

当前仍未 `git add`、未 commit、未 tag、未 push、未 PR；等待用户人工核验。
## Cloud PostgreSQL 全量迁移完成补记

时间：2026-06-20

用户确认后，阶段 49 云端数据库迁移方案从 SQLite -> Cloud PostgreSQL 切换为 Local PostgreSQL -> Cloud PostgreSQL，以保证后续开发和部署基线一致。

执行结果：
```text
SSH -> ubuntu@36.103.199.132 connected with local key C:\Users\admin\.ssh\rfc_rag_phase49
cloud deploy dir -> /home/ubuntu/rfc-rag-agent-stage44-smoke
cloud pre-restore backup -> /home/ubuntu/phase49_pre_restore_20260620_214251.dump
local pg_dump custom format -> /tmp/phase49_local_pg.dump in rfc-rag-postgres-dev, copied to C:\Users\admin\AppData\Local\Temp\phase49_local_pg.dump
uploaded dump -> /home/ubuntu/phase49_local_pg.dump
cloud PostgreSQL -> dropped/recreated target database, restored local PostgreSQL dump
cloud app -> rebuilt from uploaded Phase 49 code and restarted
cloud health -> {"status":"ok","service":"RFC-RAG-Agent","environment":"production"}
```

Local PostgreSQL and cloud PostgreSQL now match on the checked release-baseline invariants:
```text
documents=1146
sources=1073
chunks=50250
chunk_embeddings=72579
qa_logs=227
users=3
conversations=7
messages=117
qa_feedback=0
chunk_type: image_description=15628, table=1440, text=33182
embeddings: paratera/GLM-Embedding-3/2048=40563, deterministic/hash-token-v1/64=19300, jina/jina-embeddings-v3/1024=12716
alembic_version=20260621_0006
documents_fp=204ed79b5065798774d2f202546aad0f
chunks_fp=65c5aa1705958abdae7f02b1b180c72e
sequence values match for documents/chunks/chunk_embeddings/users/conversations/messages/qa_logs/sources/qa_feedback
```

说明：
- 本次目标只完成数据库全量迁移与校验；`data/images/` 资产同步和云端 FAISS 重建仍属于后续云端多模态运行完整化步骤。
- 当前本地 Git 仍未 `git add`、未 commit、未 tag、未 push、未 PR。
## Cloud Image Asset Sync 完成补记

时间：2026-06-21

用户指出云端 `data/images/` 仍为 0 文件且图片 URL 404。已补充执行图片资产同步：

```text
local data/images -> files=16978, size≈3.01GB
local tar -> C:\Users\admin\AppData\Local\Temp\phase49_data_images.tar, size≈3.03GB
uploaded cloud tar -> /home/ubuntu/phase49_data_images.tar
extract target -> /home/ubuntu/rfc-rag-agent-stage44-smoke/data/images
cloud data/images -> files=16978, size≈2.9G
cloud app health -> healthy
```

验证结果：

```text
http://127.0.0.1:8044/assets/images/1059/page10_img1.png -> 200 OK, content-type=image/png, content-length=452728
http://36.103.199.132:8044/assets/images/1059/page10_img1.png -> 200 OK, content-type=image/png, content-length=452728
```

## Cloud FAISS 与提交授权补记

时间：2026-06-21

```text
cloud FAISS rebuild -> provider=paratera model=GLM-Embedding-3 dimension=2048 vectors=40563
cloud app restart -> completed
cloud health -> {"status":"ok","service":"RFC-RAG-Agent","environment":"production"}
cloud public image asset -> http://36.103.199.132:8044/assets/images/1059/page10_img1.png returned 200 OK
user submission approval -> commit, phase-49-complete tag, push, PR, and GitHub merge authorized
```

遗留风险：
- 真实 provider 的云端 Agent smoke 受外部 API 可用性影响，不作为 CI 或本地全量测试前提。
- 提交前继续检查 staged files，确保 `.env`、数据库 dump、图片 tar、FAISS 文件和敏感凭据不进入 Git。

说明：
- 本次同步只补齐图片资产，不修改数据库。
- 云端图片 URL 已不再 404。
- 当前本地 Git 仍未 `git add`、未 commit、未 tag、未 push、未 PR。

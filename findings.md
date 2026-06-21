# 阶段 49 Findings

## 阶段 48 基线确认

- Git 基线: 当前 `main` 与 `origin/main` 均为 `4fefaafc Merge pull request #13 from CxcTHU/codex/phase-48-multimodal-evaluation`
- `phase-48-complete`: annotated tag，tag 对象指向 `4fefaafc`，未移动；`phase-48-complete` 是 `main` 的祖先
- `phase-47-complete`: 保持在阶段 47 合并点，未移动
- 全量测试: Phase 48 文档记录 `1033 passed`
- Stage 30: 91.52 / A / pass
- Alembic head: `20260621_0005`
- FAISS 向量: 40563（含 1440 table embeddings + 14158 image_description embeddings）
- 数据库引擎: SQLite `./data/app.sqlite`
- 云端状态: Phase 44 时 `36.103.199.132:8044` smoke 通过（Docker + PostgreSQL + 认证），但数据仅为 smoke 测试数据，Phase 45-48 的数据未同步

## 现有基础设施盘点

### 已就绪（可直接复用）

| 组件 | 文件 | 状态 |
|---|---|---|
| PostgreSQL 双引擎支持 | `app/db/session.py:create_database_engine()` | Phase 44 已实现，支持 `sqlite` 和 `postgresql` backend |
| SQLite → PostgreSQL 迁移脚本 | `scripts/migrate_sqlite_to_postgres.py` | Phase 45 已实现，幂等设计；阶段 49 需补 Phase 46-48 字段和新表 |
| 生产 Docker Compose | `docker-compose.prod.yml` | Phase 44 已配置 PostgreSQL 16 + FastAPI |
| FAISS 构建脚本 | `scripts/build_faiss_index.py` | 支持从任意 DATABASE_URL 重建 |
| Alembic 迁移 | 所有迁移文件 | 支持 SQLite 和 PostgreSQL |
| 认证系统 | JWT + bcrypt | Phase 44 已实现 |
| HTTPS 模板 | `deploy/nginx-https.example.conf`、`deploy/Caddyfile.example` | Phase 39/44 已提供 |

### 需要新建

| 组件 | 用途 |
|---|---|
| `docker-compose.dev.yml` | 本地开发用 PostgreSQL 容器 |
| `.env.dev.example` | 本地 PostgreSQL 开发环境模板 |

### Phase 1 验证发现

- `docker-compose.dev.yml` 已使用 `postgres:16-alpine`、宿主端口 `${POSTGRES_DEV_PORT:-5433}`、volume `pgdata_dev` 和 `pg_isready` healthcheck。
- `.env.dev.example` 只包含本地示例密码 `dev_password`，用于 localhost 开发；真实生产密码仍只能放 `.env.prod` 或本地 `.env`，不得提交。
- `docker compose -f docker-compose.dev.yml config` 通过，解析后的端口为 `5433:5432`。
- Docker Server 版本为 `29.5.3`。
- `docker compose -f docker-compose.dev.yml up -d db` 已启动 `rfc-rag-postgres-dev`；healthcheck 为 `healthy`；`docker exec rfc-rag-postgres-dev pg_isready -U rfc_user -d rfc_rag_dev` 返回 accepting connections。
- Compose 提示存在历史 orphan container `rfc-rag-agent-rfc-rag-agent-1`；阶段 49 未清理它，避免破坏用户/历史运行状态。

新词解释：

- `pg_isready`：PostgreSQL 自带的连接探测命令，本项目在 Docker healthcheck 中用它判断数据库容器是否可接收连接；面试中可说“应用要等数据库健康后再迁移和启动，避免启动顺序竞争”。
- `Docker volume`：Docker 管理的持久化数据卷，本项目 `pgdata_dev` 保存本地 PostgreSQL 数据文件；删除容器不等于删除数据卷，便于阶段内反复重启。

## 关键决策

### 本地 SQLite → PostgreSQL

- 动机: 消除 dev/prod 差异。Phase 45 曾因 SQLite `database is locked` 问题不得不用串行 importer
- 方案: 本地用 Docker 跑 PostgreSQL 16 容器，端口 5433（避免与生产端口冲突）
- SQLite 保留: 不删除 `data/app.sqlite`，保留作为备份和回滚参考；`config.py` 的默认值仍为 SQLite，通过 `.env` 切换
- `app/db/session.py` 决策: `check_same_thread=False` 只在 SQLite 分支生效；PostgreSQL 分支使用 `pool_pre_ping=True`，没有把 SQLite 参数带入生产引擎。
- 新词解释：`pool_pre_ping` 是 SQLAlchemy 连接池在复用连接前先 ping 数据库的设置，本项目在 PostgreSQL 分支用于降低长时间空闲连接失效导致的请求失败风险；面试中可说“生产数据库连接需要健康检查，SQLite 本地文件则不需要连接池预 ping”。

### 云端数据同步

- 数据差距: 云端 PostgreSQL 只有 Phase 44 smoke 数据，缺少 Phase 45-48 的全部语料、table chunks、image_description chunks 和 embedding
- 方案: 用现有 `migrate_sqlite_to_postgres.py` 直连云端 PostgreSQL（或本地 PostgreSQL → 云端 PostgreSQL dump/restore）
- 图片资产: `data/images/` 约 14000+ 文件需要 rsync/scp 到云端
- Phase 45-48 差距清单: Phase 45 本地新增大量 documents/chunks/image_description/embeddings；Phase 46 修复和重描图片、补 `caption`/`page_number`；Phase 47 补 `content_bbox_json`、`qa_feedback`、用户图片和表格交互；Phase 48 新增 1440 table chunks/table embeddings，并将 FAISS 基线提升到 40563。
- 云端 smoke 基线: Phase 44 在 `36.103.199.132:8044` 通过 `/health`、首页、注册、登录、`/auth/me`、未认证 Agent 401、认证 Agent 200。阶段 49 的云端 smoke 需要在同步 Phase 45-48 数据后再次覆盖这些认证链路，以及 Phase 47-48 的表格/图片功能。
- 安全决策: 云端 SSH/rsync/docker 操作如果 Codex 无法直接执行，只记录完整命令和验证步骤，标注需要用户手动执行；不把服务器密码、JWT secret、数据库密码写入文档或 Obsidian。

### 迁移脚本幂等设计

- 现有 `scripts/migrate_sqlite_to_postgres.py` 按 `Document.content_hash`、`Source.source_id`、`Chunk(document_id, chunk_index)`、`ChunkEmbedding(chunk_id, provider, model_name)`、`qa_logs` 问答组合去重。
- 发现的阶段 49 缺口: `migrate_chunks()` 目前只迁 `chunk_type` 和 `source_image_path`，未迁 `caption`、`page_number`、`content_bbox_json`；脚本也未迁 `users`、`conversations`、`messages`、`qa_feedback`。
- 关键决策: 阶段 49 应保留现有幂等键，不按源 id 强行复写 target id；关系字段通过 id map 重建。`users` 可按 username/email 去重，`conversations`/`messages` 需要用源 conversation/message id map 保持归属，`qa_feedback` 需要按 qa_log/conversation/message 映射并设计重复判断。
- Phase 2 已修复: 脚本现在迁移 `caption`、`page_number`、`content_bbox_json`，并新增 `users`、`conversations`、`messages`、`qa_feedback` 的 id map 和幂等插入。
- Phase 2 新增测试: `tests/test_stage45_migration.py` 现在覆盖 image metadata、用户、会话、消息、反馈迁移和二次运行幂等。
- 新词解释：`id map` 是迁移时把源库自增 id 映射到目标库新 id 的字典，本项目用于把 SQLite 的 document/chunk/user/conversation/message 关系安全迁到 PostgreSQL；面试中可说“跨数据库迁移不能假设自增主键一致，必须用业务去重键插入后再建立映射”。

### Phase 2 迁移验证发现

- `alembic upgrade head` 在本地 PostgreSQL 上成功执行到 `20260621_0005`，随后新增并执行 `20260621_0006`。
- 首次迁移失败: PostgreSQL 报 `value too long for type character varying(500)`，失败字段是 `chunks.heading_path`。根因是 SQLite 不强制 `String(500)` 长度，而 PostgreSQL 强制列宽。
- 修复决策: 新增 Alembic `20260621_0006_chunk_heading_path_text.py`，并把 `app/db/models.py::Chunk.heading_path` 改为 `Text`。不选择迁移时截断，因为 heading path 是检索和溯源 metadata，截断会损失可解释性。
- 迁移成功结果：

```text
documents: inserted=1146 skipped=0 updated=0
sources: inserted=1073 skipped=0 updated=0
chunks: inserted=50250 skipped=0 updated=19285
chunk_embeddings: inserted=72579 skipped=0 updated=0
qa_logs: inserted=227 skipped=0 updated=0
users: inserted=3 skipped=0 updated=0
conversations: inserted=7 skipped=0 updated=0
messages: inserted=117 skipped=0 updated=0
qa_feedback: inserted=0 skipped=0 updated=0
```

- 二次迁移幂等结果：documents/sources/chunks/chunk_embeddings/qa_logs/users/conversations/messages 均 `inserted=0`，已有行全部 skipped；`qa_feedback` 源库当前为 0。
- PostgreSQL 目标库对账：

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
chunk_type: text=33182, image_description=15628, table=1440
embeddings: paratera/GLM-Embedding-3/dim2048=40563, deterministic/hash-token-v1/dim64=19300, jina/jina-embeddings-v3/dim1024=12716
```

- 本地 `.env` 的 `DATABASE_URL` 已定向替换为 `postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev`，未读取或输出其他 `.env` 密钥。
- 应用运行时验证：`app.db.session.engine.url.get_backend_name()` 为 `postgresql`，通过 `SessionLocal` 查询 `documents=1146`。
- 源 SQLite 直接 count 查询曾两次超时；迁移脚本本身已完整读取源库，且首次插入数与 PostgreSQL 目标库计数一致。后续如需更强审计，可用迁移输出加目标库对账，不再阻塞主链路。

新词解释：

- `Alembic revision`：数据库 schema 版本文件，本项目用它把 PostgreSQL 表结构从 Phase 44 初始 schema 升到 Phase 47/49 字段；面试中可说“代码模型和数据库结构必须通过 migration 同步，不能只改 ORM 类”。
- `idempotent migration`：可重复运行且不会重复插入的迁移。本项目第二次运行迁移脚本时 rows 变成 skipped，证明脚本适合本地和云端断点重跑。

### 生产 Compose 边界

- `docker-compose.prod.yml` 使用 `postgres:16-alpine`、`postgres_data` volume、`pg_isready` healthcheck、`alembic upgrade head && uvicorn ...` 启动命令。
- 生产 `DATABASE_URL` 由 compose 使用 `.env.prod` 中的 PostgreSQL 变量拼接；`.env.prod` 不得提交。
- 阶段 49 不修改 provider 拓扑，不新增 Agent 工具；生产 compose 只需要确保代码版本、数据库、`data/images/` 和 FAISS 派生产物一致。

### SQLite 双引擎审计初步发现

- `rg` 显示大量测试使用 `create_sqlite_engine(f"sqlite:///{tmp_path...}")`，这是测试隔离 fixture，不等于运行时死代码。
- `tests/test_backfill_chunk_bbox.py`、`tests/test_phase46_image_page_number_backfill.py` 使用 `sqlite3.connect(":memory:")` 测脚本级 SQLite helper；阶段 49 应记录其测试用途，避免误删。
- `scripts/evaluate_stage23_agentic_auto_routing.py`、`scripts/evaluate_stage32_react_agent.py`、`scripts/evaluate_stage37_tool_calling_vs_react.py` 使用临时 SQLite fixture 做离线评测，属于 deterministic 回归边界。
- 尚未发现应用运行时把 `check_same_thread` 带入 PostgreSQL；后续 Phase 4 需继续审计 `sqlite3` 直连脚本是否只面向历史/评测/本地数据修复。

### Phase 4 双引擎边界结论

- `app/db/session.py` 是唯一运行时数据库引擎入口：SQLite 分支创建父目录并设置 `check_same_thread=False`；PostgreSQL 分支只设置 `pool_pre_ping=True`。
- Alembic 版本目录没有 `batch_alter_table`；阶段 49 新增 `20260621_0006` 已在 PostgreSQL 上执行成功。
- `.env.example` 保留 SQLite fallback，但新增 Phase 49 注释指向 `docker-compose.dev.yml` 和 `.env.dev.example`。
- `docs/deployment_guide.md` 已改为推荐本地 PostgreSQL dev 路径，并把旧 SQLite compose 标为 fallback/历史路径。
- 旧 `docker-compose.yml` 仍保留 SQLite app-only 路径，用于 Phase 39 历史/fallback；生产 PostgreSQL 仍以 `docker-compose.prod.yml` 为准，本地 PostgreSQL 以 `docker-compose.dev.yml` 为准。
- 直接使用 `sqlite3.connect()` 的脚本主要是 Phase 45/46 的本地数据修复、manifest、caption/page/bbox 回填脚本，目标对象是本地 SQLite 黄金库或临时测试库；阶段 49 不删除它们，以保留 SQLite 备份和历史修复能力。
- 聚焦测试 `18 passed` 覆盖 dev compose、PostgreSQL engine factory、迁移脚本和部署文档。

新词解释：

- `fallback`：主路径失败或为了兼容历史数据时保留的备选路径。本项目 Phase 49 后 PostgreSQL 是本地开发主路径，SQLite 是备份、测试 fixture 和历史修复 fallback。
- `batch_alter_table`：Alembic 为 SQLite 表结构变更常用的临时表复制方案。本项目当前迁移未使用它，PostgreSQL 路径不会因此触发 SQLite-only workaround。

### Phase 3 FAISS 与 smoke 发现

- `scripts/build_faiss_index.py --database-url postgresql+psycopg2://...` 从本地 PostgreSQL 成功重建 `data/faiss/paratera_GLM-Embedding-3_dim2048.index`，向量数 `40563`，与 Phase 48 基线一致。
- Stage 30 在 PostgreSQL `.env` 下保持 `overall=91.52 grade=A release_decision=pass`。
- 全量 pytest 在 PostgreSQL `.env` 下通过：`1035 passed`。相比 Phase 48 文档 `1033 passed` 多出的测试来自 Phase 49 新增 dev compose/迁移覆盖。
- 浏览器 smoke 使用本地 PostgreSQL + deterministic chat/embedding/vision，避免真实 API 成为 smoke 前提：
  - `/health` 200。
  - 登录门可见；使用本地 smoke 用户注册并进入工作台。
  - 工作台显示历史图片 evidence cards，说明图片 evidence 前端渲染和 `/assets/images/...` 链路可见。
  - 提交表格相关 Agent 问题后返回 deterministic cited answer。
  - 点击“添加图片”打开 file chooser，选择本地 `data/images/1059/page10_img1.png` 后页面显示 `已添加图片：page10_img1.png`。
  - 发送带图问题后 deterministic vision 按设计拒答：“当前启用的是 deterministic 测试视觉模型...”，证明上传链路和安全门控可达。
- 浏览器 console 唯一 error 是 smoke 中第一次使用 `.example.test` 邮箱导致 `/auth/register` 422；改用 `phase49smoke@example.com` 后注册成功。该 422 属于测试输入错误，不是应用回归。
- API smoke 经验：在真实 `.env` provider 下直接跑 Agent 问题会被真实模型/embedding 网络等待拖慢；阶段 49 继续坚持“真实 API 不作为 CI 或本地全量 smoke 前提”，真实 provider smoke 仅作为人工校准或云端运行检查。

新词解释：

- `FAISS index`：本项目的本地向量检索文件，由 `chunk_embeddings` 派生，不进 Git；面试中可说“PostgreSQL 保存权威 embedding 行，FAISS 是可重建的召回加速层”。
- `deterministic provider`：测试用固定规则模型，不理解真实语义或图片，但能稳定验证链路、schema、拒答和 UI 状态；面试中可说“真实模型用于发布前校准，deterministic provider 负责可重复回归”。

### Phase 5-8 云端同步准备结论

- 公开云端 `http://36.103.199.132:8044/health` 当前返回 production health 200，首页返回 200。
- 公开检查 `http://36.103.199.132:8044/assets/images/1059/page10_img1.png` 返回 404，说明至少该本地图片资产尚未同步到云端。
- Codex 当前没有 SSH、云端数据库密码或 `.env.prod`，不能直接执行云端 PostgreSQL 写入、服务器文件同步、云端 FAISS 重建或认证 smoke。
- 已新增 `docs/phase49_cloud_sync_runbook.md`，覆盖：
  - 本地 SQLite 黄金库 -> 云端 PostgreSQL 的安全迁移命令。
  - 云端 row count、chunk_type、embedding count 验证。
  - `data/images/` rsync / zip+scp 同步命令。
  - 云端从 PostgreSQL 重建 FAISS，预期 `vectors=40563`。
  - `docker compose -f docker-compose.prod.yml up -d --build` 部署命令。
  - health/auth/Agent/table/figure/text-only/front-end smoke checklist。
- 本地 `data/images/` 资产盘点：文件数 16978，文档目录数 854；PostgreSQL 中 `image_description` 且有 `source_image_path` 的 chunks 为 15628。
- 本地 PostgreSQL smoke 临时用户已清理，`users=3`、`messages=117` 回到迁移基线；runbook 明确云端迁移源应使用 SQLite 黄金库，避免复制本地 smoke 运行态。

新词解释：

- `runbook`：给人工或运维执行的步骤手册。本项目用它记录云端同步命令和验证点，避免在 Codex 无法 SSH 时遗漏操作。
- `rsync`：增量文件同步工具，适合 `data/images/` 这类大量图片资产；面试中可说“数据库只存路径和 metadata，文件资产要用 rsync/scp 单独同步”。

### 测试策略

- pytest 使用 `sqlite:///:memory:` 的测试需要审计，确保不依赖 SQLite-only 特性
- 全量 pytest 和 Stage 30 在切换后必须通过
- 浏览器 smoke 需要在本地 PostgreSQL 环境下重新验证

## 供应商与 API 约束

- Embedding: GLM-Embedding-3 via Paratera（不变）
- Rerank: GLM-Rerank via Paratera `/v1/p002/rerank`（不变）
- Vision: GLM-4.6V via Paratera 5 路分片（不变）
- api.jina.ai 仍然 TLS 不可用（不变）
## Phase 9 文档与 Obsidian 收尾决策（2026-06-20）

- README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/deployment_guide.md、AGENT.MD 和 `docs/phase_reviews/phase-49.md` 已记录 Phase 49 本地 PostgreSQL 迁移、FAISS `40563` 向量基线、pytest `1035 passed`、Stage 30 `91.52 / A / pass`、云端 runbook 和未提交边界。
- Obsidian 已建立 `obsidian-vault/阶段汇报/阶段 49 - 本地 PostgreSQL 迁移与云端数据同步/`，包含 Phase 0-9 小汇报和 `阶段 49 Phase 汇报索引.md`。
- Obsidian 已建立 `obsidian-vault/阶段/阶段 49 - 本地 PostgreSQL 迁移与云端数据同步.md`，并更新 `阶段汇报索引.md` 与 `阶段索引.md`。
- 关键决策：文档只记录占位命令、计数、URL、验证状态和安全边界，不记录 `.env` 内容、数据库密码、JWT secret、SSH 密码、API key、Bearer token 或供应商原始响应。
- 面试表达：阶段 49 的价值是把 SQLite 黄金库迁到 PostgreSQL，并用 Alembic、幂等迁移、FAISS 向量数、Stage 30、pytest、浏览器 smoke 和云端 runbook 证明 RAG 链路可在生产型数据库上继续运行。
## Cloud PostgreSQL 全量迁移决策（2026-06-20）

- 用户指出长期开发不能接受两个 PostgreSQL 数据库内容不一致，因此阶段 49 云端数据库迁移方案改为 Local PostgreSQL -> Cloud PostgreSQL 全量 dump/restore。
- 本地 PostgreSQL 审计结果：`documents=1146`、`sources=1073`、`chunks=50250`、`chunk_embeddings=72579`、`users=3`、`conversations=7`、`messages=117`、`qa_feedback=0`；未发现 Phase49 smoke 用户残留。
- 云端迁移前已备份当前阶段 44 smoke 数据库到 `/home/ubuntu/phase49_pre_restore_20260620_214251.dump`。
- 使用 `pg_dump -Fc` 从本地 `rfc-rag-postgres-dev / rfc_rag_dev` 导出，再上传到 `/home/ubuntu/phase49_local_pg.dump`，云端 drop/create 后 `pg_restore`。
- 云端恢复后，与本地 PostgreSQL 对齐的校验项包括核心表行数、chunk_type 分布、embedding 分组、Alembic 版本、documents/chunks 指纹和 sequence last_value。
- 云端 app 已用 Phase 49 代码重建并恢复健康；镜像 tag 名仍沿用历史 `phase44-production-auth`，但 build context 已是服务器目录中的 Phase 49 代码。
- 云端 PostgreSQL 数据库迁移目标已完成；后续多模态运行一致性依赖的 `data/images/` 同步和云端 FAISS 重建也已在 2026-06-21 补齐。
## Cloud Image Asset Sync 决策与结果（2026-06-21）

- 用户指出数据库迁移完成后，云端图片资产仍未同步，导致 `/assets/images/...` 404。该问题会影响云端图片 evidence 展示和多模态检索体验。
- 初始云端检查：`data/images` 文件数为 0，`/assets/images/1059/page10_img1.png` 返回 404。
- 本地资产基线：`data/images` 文件数 16978，总大小约 3.01GB。
- 直接 tar stream 通过 ssh 管道失败，Windows `ssh.exe` 报内存不足；改为先生成本地 `phase49_data_images.tar`，再用 `scp -O` 上传，最后在云端解包。
- 同步后云端 `data/images` 文件数为 16978，大小约 2.9G；内网和公网图片 URL 均返回 200 OK。
- 云端 FAISS 已从云端 PostgreSQL 重建：`provider=paratera model=GLM-Embedding-3 dimension=2048 vectors=40563`。
- 云端应用重启后 `/health` 返回 production 200。
- 面试表达：数据库只保存图片路径和 chunk metadata，真正的图片 evidence 还依赖文件资产同步；多模态 RAG 上云必须同时迁移结构化数据和静态资产。

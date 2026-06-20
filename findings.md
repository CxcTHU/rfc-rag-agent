# 阶段 49 Findings

## 阶段 48 基线确认

- 全量测试: 1033 passed
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
| SQLite → PostgreSQL 迁移脚本 | `scripts/migrate_sqlite_to_postgres.py` | Phase 45 已实现，幂等设计 |
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

## 关键决策

### 本地 SQLite → PostgreSQL

- 动机: 消除 dev/prod 差异。Phase 45 曾因 SQLite `database is locked` 问题不得不用串行 importer
- 方案: 本地用 Docker 跑 PostgreSQL 16 容器，端口 5433（避免与生产端口冲突）
- SQLite 保留: 不删除 `data/app.sqlite`，保留作为备份和回滚参考；`config.py` 的默认值仍为 SQLite，通过 `.env` 切换

### 云端数据同步

- 数据差距: 云端 PostgreSQL 只有 Phase 44 smoke 数据，缺少 Phase 45-48 的全部语料、table chunks、image_description chunks 和 embedding
- 方案: 用现有 `migrate_sqlite_to_postgres.py` 直连云端 PostgreSQL（或本地 PostgreSQL → 云端 PostgreSQL dump/restore）
- 图片资产: `data/images/` 约 14000+ 文件需要 rsync/scp 到云端

### 测试策略

- pytest 使用 `sqlite:///:memory:` 的测试需要审计，确保不依赖 SQLite-only 特性
- 全量 pytest 和 Stage 30 在切换后必须通过
- 浏览器 smoke 需要在本地 PostgreSQL 环境下重新验证

## 供应商与 API 约束

- Embedding: GLM-Embedding-3 via Paratera（不变）
- Rerank: GLM-Rerank via Paratera `/v1/p002/rerank`（不变）
- Vision: GLM-4.6V via Paratera 5 路分片（不变）
- api.jina.ai 仍然 TLS 不可用（不变）

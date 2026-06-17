# Stage 44 Cloud Deployment And Auth

## Goal

Stage 44 turns the project from a local SQLite-first single-user app into a deployable production shape:

```text
SQLite/PostgreSQL database engine selection
-> Alembic migrations
-> User registration/login with bcrypt and JWT
-> authenticated Agent and conversation APIs
-> per-user conversation isolation
-> docker-compose.prod.yml app + PostgreSQL deployment
-> local regression and cloud-server smoke
```

The already initialized cloud server is a verification target, not a prerequisite for CI or local full tests.

## Starting Point

- Phase 43 is merged into `origin/main -> 5596d27`.
- Local `main` is stale, so Stage 44 starts from `origin/main`.
- Current cloud server is Docker-ready: Ubuntu 22.04 CMD, 4 vCPU, 8GB RAM, about 100GB system disk, Docker 29.1.3, Docker Compose v2.40.3.
- Existing local development still uses SQLite by default.

## Track A: Database Abstraction

`app/db/session.py` owns engine creation.

- SQLite URLs keep `check_same_thread=False` and auto-create the parent directory.
- PostgreSQL URLs use SQLAlchemy with `pool_pre_ping=True`.
- Unsupported URL backends fail fast.
- Alembic owns production schema migrations. `Base.metadata.create_all()` remains for local tests and backward-compatible lightweight startup.

## Track B: Auth And User Isolation

New auth components:

- `User` ORM model: `id`, `username`, `email`, `password_hash`, `is_active`, `created_at`.
- `app/core/security.py`: bcrypt password hashing, JWT creation/verification, Bearer-token dependency.
- `app/api/auth.py`: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`.
- `Conversation.user_id`: nullable foreign key for backward compatibility with old local conversations.

Runtime behavior:

- `AUTH_ENABLED=false`: local/dev compatibility mode. Existing unauthenticated tests and local workflows keep working.
- `AUTH_ENABLED=true`: `/agent/query`, `/agent/query/stream`, and `/conversations/*` require `Authorization: Bearer <token>`.
- `/health`, `/health/details`, `/auth/register`, and `/auth/login` remain public.
- When auth is enabled, users can only list, read, rename, delete, and append messages to their own conversations.

## Track C: Docker Production Deployment

`docker-compose.prod.yml` will run:

- `app`: FastAPI container built from the existing Dockerfile.
- `db`: `postgres:16-alpine` with a named volume.

Required production environment variables:

```text
APP_ENV=production
AUTH_ENABLED=true
DATABASE_URL=postgresql+psycopg2://...
JWT_SECRET_KEY=<real secret outside Git>
```

The existing `docker-compose.yml` remains the SQLite development compose file.

## Safety Boundary

- Never write API keys, Bearer tokens, JWT secret, SSH password, database password, plaintext user passwords, raw provider responses, `raw_response`, `reasoning_content`, hidden reasoning, full chunks, or restricted full text to Git, CSV, tests, docs, or Obsidian.
- Real provider APIs and the cloud server must not become CI or local full-test prerequisites.
- Stage 30 scoring rules, provider topology, and data-source boundaries stay unchanged.
- Stage 44 does not add crawlers, external data sources, multimodal recognition, complex LangGraph workflows, or long-term user profiling.

## Verification Contract

Focused checks:

```text
python -m pytest tests/test_stage44_db_session.py tests/test_stage44_auth.py -q
```

Stage closeout checks:

```text
python -m pytest -q
python scripts/score_stage30_quality.py
python scripts/run_production_smoke.py
```

Browser smoke must cover registration, login, token-authenticated Agent query, conversation isolation, and unauthenticated 401 behavior.

Cloud-server smoke happens after local verification and uses only safe status observations.

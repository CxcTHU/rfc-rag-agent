# Phase 44 Cloud Deployment

This document records the deployment path for the Phase 44 production shape. It intentionally uses placeholders for secrets.

## Target

- Runtime: Docker Compose.
- Services: FastAPI app, PostgreSQL, and Redis Stack.
- Production app networking: the app service uses the CPU host network namespace
  so outbound model/provider traffic follows the host egress path instead of
  Docker bridge/NAT. PostgreSQL and Redis remain containerized but bind only to
  `127.0.0.1`.
- Database: PostgreSQL 16 in production, SQLite still available for local development.
- Auth: enabled in production with bcrypt password hashes and JWT bearer tokens.
- Cloud server: the initialized CPU Ubuntu server is a smoke-test target before user verification, not a CI or full-test prerequisite.

## Files

- `Dockerfile`: builds the app image and copies Alembic migration files into the runtime image.
- `docker-compose.yml`: local SQLite compose path.
- `docker-compose.prod.yml`: production app + PostgreSQL path.
- `alembic.ini` and `alembic/`: migration configuration and initial schema.
- `.env.example`: non-secret template values.

## First Deploy

1. Copy the repository to the server.
2. Create `.env.prod` from `.env.example`.
3. Fill only local runtime secrets in `.env.prod`:

```text
POSTGRES_PASSWORD=<strong database password>
REDIS_PASSWORD=<strong redis password>
REDIS_URL=redis://:<url-encoded redis password>@127.0.0.1:${REDIS_HOST_PORT:-16379}/0
JWT_SECRET_KEY=<long random jwt secret>
APP_PORT=8000
```

If the server has slow PyPI access, set a local build mirror in `.env.prod`:

```text
PIP_INDEX_URL=<python package mirror url>
PIP_TRUSTED_HOST=<mirror host if required>
```

4. Start the stack:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

The app container runs `alembic upgrade head` before starting Uvicorn.
Because the production app uses host networking, Uvicorn listens directly on
`${APP_PORT}` and provider calls leave through the CPU host network stack.

## Smoke Checks

```bash
curl http://127.0.0.1:${APP_PORT:-8000}/health
curl -X POST http://127.0.0.1:${APP_PORT:-8000}/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_user","email":"smoke@example.com","password":"replace-with-local-password"}'
curl -X POST http://127.0.0.1:${APP_PORT:-8000}/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username_or_email":"smoke_user","password":"replace-with-local-password"}'
```

Do not write returned bearer tokens, JWT secrets, database passwords, API keys, or provider raw responses into Git, docs, tests, CSV, logs, or Obsidian.

## Data

The app mounts `./data` into `/app/data`. Copy only required non-secret data and generated indexes to the server. PostgreSQL state is stored in the named Docker volume `postgres_data`, so app restarts and server reboots keep database rows unless the volume is removed.

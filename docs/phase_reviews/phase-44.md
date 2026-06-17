# Phase 44 Review Draft: Production Deployment Auth

Status: development complete except remote smoke status readback; not staged, not committed, not tagged, not pushed.

## Scope

- SQLite/PostgreSQL dual engine selected by `DATABASE_URL`.
- Alembic initial migration for existing schema plus `users` and `conversations.user_id`.
- User registration/login/me APIs with bcrypt and JWT.
- Auth guard for Agent and conversation APIs when `AUTH_ENABLED=true`.
- Per-user conversation isolation.
- `docker-compose.prod.yml` app + PostgreSQL deployment path.
- Chinese standalone frontend auth gate and bearer-token request injection.
- Local full regression, Stage 30 non-regression, browser smoke, and documentation.

## Verification

```text
python -m pytest tests/test_stage44_auth.py tests/test_stage44_db_session.py tests/test_stage44_deployment.py tests/test_frontend_app.py -q -> 25 passed
python -m pytest -q -> 894 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m alembic upgrade head with temporary SQLite smoke DB -> passed
docker compose -f docker-compose.prod.yml --env-file .env.prod config --quiet with temporary placeholder env -> passed
local browser smoke AUTH_ENABLED=true -> register/login/conversation/Agent/mobile passed, console errors []
```

## Remote Smoke

The cloud server had already been initialized with Docker and Docker Compose. A Phase 44 smoke package was uploaded and `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build` succeeded after using pre-pulled Docker mirror images and a temporary Python package mirror build arg. Server-local smoke on `127.0.0.1:8044` passed: health 200, register/login/me 200, unauthenticated Agent 401, authenticated Agent 200, app and db containers healthy. After the cloud platform inbound TCP 8044 rule was opened, public smoke on `http://36.103.199.132:8044` also passed health/home/auth/query checks. The final frontend follow-up replaced the initial inline auth controls with a Chinese standalone auth gate and bumped static assets to `phase44-auth-gate-zh-fix1`.

## Security Notes

No real `.env.prod`, JWT secret, database password, SSH password, bearer token, API key, raw provider response, or restricted full text should be committed. Temporary local smoke artifacts were removed.

## New Terms

- Alembic: SQLAlchemy migration tool for controlled schema changes.
- bcrypt: password hashing algorithm with per-password salt.
- JWT: signed bearer token containing subject and expiry.
- `pool_pre_ping`: SQLAlchemy connection pool check that avoids stale PostgreSQL connections.

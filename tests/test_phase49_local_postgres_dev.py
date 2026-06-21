from pathlib import Path


def test_phase49_dev_compose_runs_postgres_on_5433() -> None:
    compose = Path("docker-compose.dev.yml").read_text(encoding="utf-8")

    assert "pgvector/pgvector:pg16" in compose
    assert "pgdata_dev:/var/lib/postgresql/data" in compose
    assert "${POSTGRES_DEV_PORT:-5433}:5432" in compose
    assert "pg_isready" in compose
    assert "JWT_SECRET_KEY" not in compose


def test_phase49_env_dev_example_uses_example_postgres_url() -> None:
    env_example = Path(".env.dev.example").read_text(encoding="utf-8")

    assert "DATABASE_URL=postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev" in env_example
    assert "POSTGRES_PASSWORD=dev_password" in env_example
    assert "API_KEY" not in env_example
    assert "Bearer " not in env_example


def test_phase49_deployment_guide_prefers_local_postgres_dev_path() -> None:
    guide = Path("docs/deployment_guide.md").read_text(encoding="utf-8")

    assert "docker-compose.dev.yml" in guide
    assert "postgresql+psycopg2://rfc_user:dev_password@localhost:5433/rfc_rag_dev" in guide
    assert "python -m alembic upgrade head" in guide
    assert "migrate_sqlite_to_postgres.py" in guide
    assert "SQLite fallback" in guide


def test_phase49_cloud_sync_runbook_uses_placeholders_and_safe_boundaries() -> None:
    runbook = Path("docs/phase49_cloud_sync_runbook.md").read_text(encoding="utf-8")

    assert "36.103.199.132:8044/health" in runbook
    assert "<db_password>" in runbook
    assert "<cloud_user>" in runbook
    assert "migrate_sqlite_to_postgres.py" in runbook
    assert "paratera/GLM-Embedding-3/dim2048=40563" in runbook
    assert "Bearer <token_from_login>" in runbook
    forbidden = ["Bearer ey", "JWT_SECRET_KEY=", "sk-", "tp-"]
    for literal in forbidden:
        assert literal not in runbook

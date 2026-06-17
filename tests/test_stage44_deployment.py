from pathlib import Path


def test_stage44_production_compose_uses_postgres_auth_and_migrations() -> None:
    compose = Path("docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "postgres:16-alpine" in compose
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert 'AUTH_ENABLED: "true"' in compose
    assert "postgresql+psycopg2://" in compose
    assert "JWT_SECRET_KEY: ${JWT_SECRET_KEY:?set JWT_SECRET_KEY" in compose
    assert "alembic upgrade head" in compose
    assert "PIP_INDEX_URL: ${PIP_INDEX_URL:-}" in compose
    assert "PIP_TRUSTED_HOST: ${PIP_TRUSTED_HOST:-}" in compose


def test_stage44_cloud_deployment_doc_keeps_remote_server_as_smoke_target() -> None:
    document = Path("docs/deployment_cloud.md").read_text(encoding="utf-8")

    assert "smoke-test target" in document
    assert "not a CI or full-test prerequisite" in document
    assert "docker compose -f docker-compose.prod.yml" in document
    assert "postgres_data" in document
    assert "<strong database password>" in document


def test_stage44_secret_templates_do_not_contain_real_values() -> None:
    files = [
        Path(".env.example"),
        Path("docker-compose.prod.yml"),
        Path("docs/deployment_cloud.md"),
    ]
    forbidden_literals = [
        "Bearer ey",
        "stage44-test-secret",
    ]

    for path in files:
        content = path.read_text(encoding="utf-8")
        for literal in forbidden_literals:
            assert literal not in content


def test_stage44_dockerfile_copies_runtime_import_dependencies() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY app ./app" in dockerfile
    assert "COPY scripts ./scripts" in dockerfile
    assert "COPY alembic.ini ./alembic.ini" in dockerfile
    assert "COPY alembic ./alembic" in dockerfile

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_runs_fastapi_without_copying_runtime_data() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.11-slim" in dockerfile
    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "pip wheel" in dockerfile
    assert "uvicorn" in dockerfile
    assert "app.main:app" in dockerfile
    assert "chainlit run" not in dockerfile
    assert "chainlit_app.py" not in dockerfile
    assert "COPY . ." not in dockerfile
    assert ".env" not in dockerfile
    assert "app.sqlite" not in dockerfile
    assert "obsidian-vault" not in dockerfile


def test_dockerignore_excludes_secrets_database_and_obsidian() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    required_patterns = [
        ".env",
        ".venv",
        ".git",
        "tests",
        "data/evaluation",
        "obsidian-vault",
        "data/app.sqlite",
        "data/raw",
        "data/fulltext",
        "*.sqlite",
        "*.db",
    ]
    for pattern in required_patterns:
        assert pattern in dockerignore


def test_docker_compose_mounts_data_and_uses_runtime_env_file() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "build:" in compose
    assert "8000:8000" in compose
    assert "rfc-rag-agent:phase39-production-deployment" in compose
    assert "env_file:" in compose
    assert "- .env" in compose
    assert "APP_ENV: production" in compose
    assert "./data:/app/data" in compose
    assert "sqlite:////app/data/app.sqlite" in compose
    assert "healthcheck:" in compose
    assert "http://127.0.0.1:8000/health" in compose


def test_github_actions_ci_runs_deterministic_pytest() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "pull_request:" in workflow
    assert "main" in workflow
    assert '"codex/**"' in workflow
    assert '"claude/**"' in workflow
    assert "python-version: \"3.11\"" in workflow
    assert "python -m pip install -e \".[dev]\"" in workflow
    assert "python -m pytest -q" in workflow
    assert "CHAT_MODEL_PROVIDER: deterministic" in workflow
    assert "EMBEDDING_PROVIDER: deterministic" in workflow
    assert "RERANKING_PROVIDER: deterministic" in workflow

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stage39_dockerfile_uses_fastapi_uvicorn_runtime() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    for phrase in [
        "FROM python:3.11-slim AS builder",
        "FROM python:3.11-slim AS runtime",
        "COPY pyproject.toml README.md ./",
        "RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .",
        "COPY --from=builder /wheels /wheels",
        "RUN python -m pip install --no-cache-dir /wheels/*.whl",
        "COPY app ./app",
        'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]',
    ]:
        assert phrase in dockerfile

    assert "chainlit run" not in dockerfile
    assert "chainlit_app.py" not in dockerfile
    assert "COPY . ." not in dockerfile


def test_stage39_docker_compose_declares_runtime_env_volume_and_healthcheck() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    for phrase in [
        "image: rfc-rag-agent:phase39-production-deployment",
        "env_file:",
        "- .env",
        "APP_ENV: production",
        "DATABASE_URL: sqlite:////app/data/app.sqlite",
        "./data:/app/data",
        "healthcheck:",
        "http://127.0.0.1:8000/health",
        "restart: unless-stopped",
    ]:
        assert phrase in compose


def test_stage39_dockerignore_excludes_local_and_evaluation_artifacts() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    for pattern in [
        ".env",
        ".env.*",
        "!.env.example",
        ".git",
        ".venv",
        "tests",
        "data/evaluation",
        "data/app.sqlite",
        "data/raw",
        "data/fulltext",
        "obsidian-vault",
        "*.sqlite",
        "*.db",
        "*.log",
    ]:
        assert pattern in dockerignore

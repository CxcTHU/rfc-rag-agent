from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stage39_deployment_guide_documents_fastapi_docker_flow() -> None:
    guide = (ROOT / "docs" / "deployment_guide.md").read_text(encoding="utf-8")

    for phrase in [
        "uvicorn app.main:app --host 0.0.0.0 --port 8000",
        "docker build -t rfc-rag-agent:phase39-production-deployment .",
        "docker compose up --build",
        "GET /health",
        "python scripts/run_production_smoke.py --execute",
        "overall=91.52 grade=A release_decision=pass",
    ]:
        assert phrase in guide

    assert "旧 Chainlit 入口" in guide
    assert "不是 Docker 默认启动入口" in guide


def test_stage39_deployment_guide_documents_security_boundaries() -> None:
    guide = (ROOT / "docs" / "deployment_guide.md").read_text(encoding="utf-8")

    for phrase in [
        "真实 API key 只能放在本地 `.env`",
        "不得写入 Git、CSV、文档、测试或 Obsidian",
        "不保存 response body",
        "raw provider response",
        "`reasoning_content`",
        "受限全文",
        "不会记录 Authorization header",
    ]:
        assert phrase in guide


def test_env_example_lists_runtime_provider_and_reranking_settings() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for key in [
        "APP_ENV=development",
        "DATABASE_URL=sqlite:///./data/app.sqlite",
        "CHAT_MODEL_PROVIDER=",
        "PLANNER_CHAT_MODEL_PROVIDER=",
        "EMBEDDING_PROVIDER=",
        "RERANKING_ENABLED=true",
        "RERANKING_PROVIDER=deterministic",
        "RERANKING_RECALL_K=25",
    ]:
        assert key in env_example

    assert "sk-" not in env_example.casefold()
    assert "bearer " not in env_example.casefold()


def test_readme_quick_start_points_to_phase39_fastapi_container() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for phrase in [
        "## Docker Quick Start",
        "Docker 默认入口是 FastAPI + uvicorn",
        "uvicorn app.main:app --host 0.0.0.0 --port 8000",
        "docker build -t rfc-rag-agent:phase39-production-deployment .",
        "docker compose up --build",
        "Compose healthcheck 访问 `GET /health`",
        "docs/deployment_guide.md",
    ]:
        assert phrase in readme


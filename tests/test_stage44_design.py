from pathlib import Path


def test_stage44_design_document_records_core_tracks_and_boundaries() -> None:
    document = Path("docs/stage44_cloud_deployment_auth.md").read_text(encoding="utf-8")

    assert "SQLite/PostgreSQL database engine selection" in document
    assert "Alembic migrations" in document
    assert "User registration/login with bcrypt and JWT" in document
    assert "per-user conversation isolation" in document
    assert "docker-compose.prod.yml app + PostgreSQL deployment" in document
    assert "cloud server is a verification target" in document
    assert "must not become CI or local full-test prerequisites" in document


def test_stage44_design_document_keeps_sensitive_values_out() -> None:
    document = Path("docs/stage44_cloud_deployment_auth.md").read_text(encoding="utf-8")

    forbidden_literals = [
        "Bearer ey",
        "JWT_SECRET_KEY=stage44",
        "password=stage44",
    ]
    for literal in forbidden_literals:
        assert literal not in document


def test_stage44_planning_records_nine_phases_and_server_boundary() -> None:
    task_plan = Path("task_plan.md").read_text(encoding="utf-8")

    assert "Phase 0-8（9 个 Phase）" in task_plan
    assert "origin/main -> 5596d27" in task_plan
    assert "Docker-ready 初始化" in task_plan
    assert "远端服务器只用于人工核验前部署验证" in task_plan

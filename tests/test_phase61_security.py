from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import Base
from app.db.session import create_sqlite_engine, get_db
from app.main import app


@contextmanager
def make_phase61_client(
    tmp_path: Path,
    *,
    app_env: str = "development",
    auth_enabled: bool = True,
    source_sync_allowed_roots: str | None = None,
    export_allowed_dir: str | None = None,
) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "phase61.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_settings() -> Settings:
        return Settings(
            app_env=app_env,
            auth_enabled=auth_enabled,
            jwt_secret_key="phase61-test-secret",
            database_url=f"sqlite:///{database_path.as_posix()}",
            source_sync_allowed_roots=source_sync_allowed_roots or str(tmp_path),
            export_allowed_dir=export_allowed_dir or str(tmp_path / "exports"),
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_settings
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def register(client: TestClient, username: str, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "phase61-password",
        },
    )
    assert response.status_code == 200
    return response.json()


def token_for(client: TestClient, username: str) -> str:
    response = client.post(
        "/auth/login",
        json={
            "username_or_email": username,
            "password": "phase61-password",
        },
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_phase61_first_user_is_admin_and_prod_registration_closes(tmp_path) -> None:
    with make_phase61_client(tmp_path, app_env="production") as client:
        first = register(client, "admin", "admin@example.com")
        second = client.post(
            "/auth/register",
            json={
                "username": "ordinary",
                "email": "ordinary@example.com",
                "password": "phase61-password",
            },
        )

    assert first["role"] == "admin"
    assert second.status_code == 403
    assert second.json()["detail"] == "public registration is disabled"


def test_phase61_production_settings_force_auth_and_rate_limit() -> None:
    settings = Settings(
        app_env="production",
        auth_enabled=False,
        rate_limit_enabled=False,
    )

    assert settings.auth_enabled is True
    assert settings.rate_limit_enabled is True


def test_phase61_sensitive_routes_require_auth_when_enabled(tmp_path) -> None:
    with make_phase61_client(tmp_path) as client:
        responses = [
            client.get("/documents"),
            client.post("/search", json={"query": "RFC"}),
            client.post("/chat", json={"question": "What is RFC?"}),
            client.post("/feedback", json={"question": "q", "answer": "a", "rating": "positive"}),
            client.post("/agent/upload-image", files={"file": ("x.png", b"bad", "image/png")}),
        ]

    assert [response.status_code for response in responses] == [401, 401, 401, 401, 401]


def test_phase61_logged_in_user_can_open_original_document_via_cookie(tmp_path) -> None:
    markdown_content = "# RFC\n\n堆石混凝土原文可供登录用户查看。"
    with make_phase61_client(tmp_path) as client:
        register(client, "reader", "reader@example.com")
        token_for(client, "reader")
        import_response = client.post(
            "/documents/import",
            files={"file": ("rfc.md", markdown_content.encode("utf-8"), "text/markdown")},
        )
        document_id = import_response.json()["document_id"]
        open_response = client.get(f"/documents/{document_id}/open")

    assert import_response.status_code == 200
    assert open_response.status_code == 200
    assert "堆石混凝土原文" in open_response.text


def test_phase61_admin_routes_reject_non_admin_user(tmp_path) -> None:
    with make_phase61_client(tmp_path) as client:
        register(client, "admin", "admin@example.com")
        admin_token = token_for(client, "admin")
        user = register(client, "alice", "alice@example.com")
        user_token = token_for(client, "alice")
        stats_response = client.get("/feedback/stats", headers=auth_header(user_token))
        export_response = client.get("/feedback/export", headers=auth_header(user_token))
        sync_response = client.post(
            "/sources/sync",
            json={"include_defaults": False},
            headers=auth_header(admin_token),
        )

    assert user["role"] == "user"
    assert stats_response.status_code == 200
    assert export_response.status_code == 403
    assert sync_response.status_code == 200


def test_phase61_source_sync_rejects_paths_outside_allowed_roots(tmp_path) -> None:
    allowed_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    candidate_csv = outside_root / "sources.csv"
    candidate_csv.write_text("source_id,title\ns1,Outside\n", encoding="utf-8")

    with make_phase61_client(
        tmp_path,
        source_sync_allowed_roots=str(allowed_root),
    ) as client:
        register(client, "admin", "admin@example.com")
        token = token_for(client, "admin")
        response = client.post(
            "/sources/sync",
            json={"include_defaults": False, "candidate_csvs": [str(candidate_csv)]},
            headers=auth_header(token),
        )

    assert response.status_code == 400
    assert "outside allowed roots" in response.json()["detail"]


def test_phase61_feedback_export_rejects_paths_outside_export_dir(tmp_path) -> None:
    export_dir = tmp_path / "exports"
    with make_phase61_client(tmp_path, export_allowed_dir=str(export_dir)) as client:
        register(client, "admin", "admin@example.com")
        token = token_for(client, "admin")
        response = client.get(
            f"/feedback/export?dry_run=false&output_path={tmp_path / 'escape.csv'}",
            headers=auth_header(token),
        )

    assert response.status_code == 400
    assert "outside allowed roots" in response.json()["detail"]


def test_phase61_health_details_is_admin_only_in_production(tmp_path) -> None:
    with make_phase61_client(tmp_path, app_env="production") as client:
        unauthenticated = client.get("/health/details")
        register(client, "admin", "admin@example.com")
        token = token_for(client, "admin")
        authenticated = client.get("/health/details", headers=auth_header(token))

    assert unauthenticated.status_code == 401
    assert authenticated.status_code in {200, 503}

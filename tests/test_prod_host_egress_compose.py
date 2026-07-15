from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_prod_compose_routes_app_through_host_network() -> None:
    override = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))

    services = override["services"]
    app = services["app"]

    assert app["network_mode"] == "host"
    assert app.get("ports", []) == []
    assert "uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8000}" in " ".join(
        app["command"]
    )
    assert "http://127.0.0.1:${APP_PORT:-8000}/health" in " ".join(
        app["healthcheck"]["test"]
    )

    environment = app["environment"]
    assert "@127.0.0.1:${POSTGRES_HOST_PORT:-15432}/" in environment["DATABASE_URL"]
    assert "@127.0.0.1:${REDIS_HOST_PORT:-16379}/0" in environment["REDIS_URL"]


def test_prod_compose_keeps_datastores_localhost_only() -> None:
    override = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))

    services = override["services"]

    assert services["db"]["ports"] == ["127.0.0.1:${POSTGRES_HOST_PORT:-15432}:5432"]
    assert services["redis"]["ports"] == ["127.0.0.1:${REDIS_HOST_PORT:-16379}:6379"]

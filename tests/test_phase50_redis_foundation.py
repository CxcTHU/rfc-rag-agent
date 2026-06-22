from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.cache.redis_client import RedisClientFactory, get_redis_client


def test_phase50_dev_compose_adds_optional_redis_service() -> None:
    compose = Path("docker-compose.dev.yml").read_text(encoding="utf-8")

    assert "redis/redis-stack-server:latest" in compose
    assert "container_name: rfc-rag-redis-dev" in compose
    assert "127.0.0.1:${REDIS_DEV_PORT:-6379}:6379" in compose
    assert "--requirepass ${REDIS_PASSWORD:-dev_redis_password}" in compose
    assert "--protected-mode yes" in compose
    assert "redis-cli" in compose
    assert 'redis-cli -a \\"$${REDIS_PASSWORD}\\" ping' in compose
    assert "redisdata_dev:/data" in compose
    assert "JWT_SECRET_KEY" not in compose


def test_phase50_env_dev_example_uses_safe_redis_url() -> None:
    env_example = Path(".env.dev.example").read_text(encoding="utf-8")

    assert "REDIS_URL=redis://:dev_redis_password@localhost:6379/0" in env_example
    assert "REDIS_PASSWORD=dev_redis_password" in env_example
    assert "REDIS_DEV_PORT=6379" in env_example
    assert "API_KEY" not in env_example
    assert "Bearer " not in env_example


def test_phase50_settings_make_redis_optional() -> None:
    default_settings = Settings(_env_file=None)
    redis_settings = Settings(redis_url="redis://localhost:6379/0")

    assert default_settings.redis_url == ""
    assert default_settings.redis_socket_timeout_seconds == 1.0
    assert redis_settings.redis_url == "redis://localhost:6379/0"


def test_redis_client_factory_returns_none_when_url_is_missing() -> None:
    factory = RedisClientFactory("")

    assert factory.create_client() is None
    assert factory.last_status.configured is False
    assert factory.last_status.available is False
    assert factory.last_status.reason == "redis_url_not_configured"


def test_redis_client_factory_returns_none_when_package_is_missing() -> None:
    factory = RedisClientFactory("redis://localhost:6379/0", redis_library=None)

    assert factory.create_client() is None
    assert factory.last_status.configured is True
    assert factory.last_status.available is False
    assert factory.last_status.reason == "redis_package_not_installed"


def test_redis_client_factory_pings_before_returning_client() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.ping_called = False

        def ping(self) -> bool:
            self.ping_called = True
            return True

    class FakeRedis:
        created_client = FakeClient()
        from_url_kwargs = {}

        @classmethod
        def from_url(cls, url: str, **kwargs):
            cls.from_url_kwargs = {"url": url, **kwargs}
            return cls.created_client

    class FakeRedisLibrary:
        Redis = FakeRedis

    factory = RedisClientFactory(
        "redis://localhost:6379/0",
        socket_timeout_seconds=0.25,
        redis_library=FakeRedisLibrary,
    )

    client = factory.create_client()

    assert client is FakeRedis.created_client
    assert client.ping_called is True
    assert FakeRedis.from_url_kwargs["url"] == "redis://localhost:6379/0"
    assert FakeRedis.from_url_kwargs["socket_timeout"] == 0.25
    assert FakeRedis.from_url_kwargs["socket_connect_timeout"] == 0.25
    assert FakeRedis.from_url_kwargs["decode_responses"] is False
    assert factory.last_status.available is True
    assert factory.last_status.reason == "ok"


def test_redis_client_factory_falls_back_when_ping_fails() -> None:
    class FakeClient:
        def ping(self) -> bool:
            raise TimeoutError("redis unavailable")

    class FakeRedis:
        @classmethod
        def from_url(cls, _url: str, **_kwargs):
            return FakeClient()

    class FakeRedisLibrary:
        Redis = FakeRedis

    factory = RedisClientFactory(
        "redis://localhost:6379/0",
        redis_library=FakeRedisLibrary,
    )

    assert factory.create_client() is None
    assert factory.last_status.configured is True
    assert factory.last_status.available is False
    assert "TimeoutError" in factory.last_status.reason


def test_get_redis_client_uses_settings_and_falls_back_without_url() -> None:
    assert get_redis_client(Settings(redis_url="")) is None

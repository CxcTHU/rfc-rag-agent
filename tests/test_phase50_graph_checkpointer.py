from __future__ import annotations

from app.core.config import Settings
from app.services.agent.graph_checkpointer import (
    create_graph_checkpointer,
    redis_ttl_config,
    reset_graph_checkpointer_cache,
)


def test_graph_checkpointer_uses_memory_when_redis_url_is_missing() -> None:
    reset_graph_checkpointer_cache()
    selection = create_graph_checkpointer(Settings(redis_url=""))

    assert selection.backend == "memory"
    assert selection.available is True
    assert selection.reason == "redis_url_not_configured"
    assert selection.checkpointer is not None


def test_graph_checkpointer_reuses_memory_fallback_for_resume() -> None:
    reset_graph_checkpointer_cache()
    first = create_graph_checkpointer(Settings(redis_url=""))
    second = create_graph_checkpointer(Settings(redis_url=""))

    assert first.checkpointer is second.checkpointer


def test_graph_checkpointer_uses_memory_when_redis_saver_is_missing() -> None:
    selection = create_graph_checkpointer(
        Settings(redis_url="redis://localhost:6379/0"),
        redis_client=object(),
        redis_saver_cls=None,
    )

    assert selection.backend == "memory"
    assert selection.reason == "langgraph_checkpoint_redis_not_installed"


def test_graph_checkpointer_uses_memory_when_redis_client_is_unavailable() -> None:
    selection = create_graph_checkpointer(
        Settings(redis_url="not-a-redis-url"),
        redis_saver_cls=object(),
    )

    assert selection.backend == "memory"
    assert selection.reason == "redis_unavailable"


def test_graph_checkpointer_uses_memory_when_redis_saver_setup_fails() -> None:
    class FailingRedisSaver:
        def __init__(self, redis_client=None, ttl=None) -> None:
            pass

        def setup(self) -> None:
            raise RuntimeError("missing redis module")

    selection = create_graph_checkpointer(
        Settings(redis_url="redis://localhost:6379/0"),
        redis_client=object(),
        redis_saver_cls=FailingRedisSaver,
    )

    assert selection.backend == "memory"
    assert selection.reason.startswith("redis_checkpointer_unavailable: RuntimeError")


def test_graph_checkpointer_uses_redis_when_saver_setup_succeeds() -> None:
    class FakeRedisSaver:
        setup_called = False

        def __init__(self, redis_client=None, ttl=None) -> None:
            self.client = redis_client
            self.ttl = ttl

        def setup(self) -> None:
            self.__class__.setup_called = True

    client = object()
    selection = create_graph_checkpointer(
        Settings(redis_url="redis://localhost:6379/0"),
        redis_client=client,
        redis_saver_cls=FakeRedisSaver,
    )

    assert selection.backend == "redis"
    assert selection.reason == "ok"
    assert selection.checkpointer.client is client
    assert selection.checkpointer.ttl == {
        "default_ttl": 60,
        "refresh_on_read": True,
    }
    assert FakeRedisSaver.setup_called is True


def test_redis_ttl_config_can_disable_expiration() -> None:
    assert redis_ttl_config(Settings(langgraph_checkpoint_ttl_minutes=0)) is None

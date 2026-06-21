from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.services.cache.redis_client import RedisClientFactory

try:  # LangGraph 1.2 keeps MemorySaver as a compatibility alias.
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:  # pragma: no cover
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver  # type: ignore

try:  # Optional dependency introduced in Phase 5.
    from langgraph.checkpoint.redis import RedisSaver
except ImportError:  # pragma: no cover - package is optional.
    RedisSaver = None  # type: ignore[assignment]


@dataclass(frozen=True)
class GraphCheckpointerSelection:
    checkpointer: Any
    backend: str
    available: bool
    reason: str


_GLOBAL_MEMORY_CHECKPOINTER = MemorySaver()
_GLOBAL_SELECTION: GraphCheckpointerSelection | None = None
_GLOBAL_SELECTION_SIGNATURE: tuple[str, float, str] | None = None


def create_graph_checkpointer(
    settings: Settings | None = None,
    *,
    redis_client: Any | None = None,
    redis_saver_cls: Any | None = RedisSaver,
) -> GraphCheckpointerSelection:
    global _GLOBAL_SELECTION, _GLOBAL_SELECTION_SIGNATURE

    active_settings = settings or get_settings()
    memory = _GLOBAL_MEMORY_CHECKPOINTER
    redis_url = active_settings.redis_url.strip()
    saver_name = getattr(redis_saver_cls, "__name__", str(redis_saver_cls))
    signature = (
        redis_url,
        active_settings.redis_socket_timeout_seconds,
        saver_name,
    )
    if (
        redis_client is None
        and _GLOBAL_SELECTION is not None
        and _GLOBAL_SELECTION_SIGNATURE == signature
    ):
        return _GLOBAL_SELECTION

    if not redis_url:
        selection = GraphCheckpointerSelection(
            checkpointer=memory,
            backend="memory",
            available=True,
            reason="redis_url_not_configured",
        )
        _GLOBAL_SELECTION = selection
        _GLOBAL_SELECTION_SIGNATURE = signature
        return selection
    if redis_saver_cls is None:
        return GraphCheckpointerSelection(
            checkpointer=memory,
            backend="memory",
            available=True,
            reason="langgraph_checkpoint_redis_not_installed",
        )

    client = redis_client
    if client is None:
        client = RedisClientFactory(
            redis_url,
            socket_timeout_seconds=active_settings.redis_socket_timeout_seconds,
        ).create_client()
    if client is None:
        return GraphCheckpointerSelection(
            checkpointer=memory,
            backend="memory",
            available=True,
            reason="redis_unavailable",
        )

    try:
        ttl_config = redis_ttl_config(active_settings)
        try:
            checkpointer = redis_saver_cls(redis_client=client, ttl=ttl_config)
        except TypeError:
            checkpointer = redis_saver_cls(client)
        setup = getattr(checkpointer, "setup", None)
        if callable(setup):
            setup()
    except Exception as exc:
        return GraphCheckpointerSelection(
            checkpointer=memory,
            backend="memory",
            available=True,
            reason=f"redis_checkpointer_unavailable: {exc.__class__.__name__}: {exc}",
        )

    selection = GraphCheckpointerSelection(
        checkpointer=checkpointer,
        backend="redis",
        available=True,
        reason="ok",
    )
    if redis_client is None:
        _GLOBAL_SELECTION = selection
        _GLOBAL_SELECTION_SIGNATURE = signature
    return selection


def reset_graph_checkpointer_cache() -> None:
    global _GLOBAL_SELECTION, _GLOBAL_SELECTION_SIGNATURE
    _GLOBAL_SELECTION = None
    _GLOBAL_SELECTION_SIGNATURE = None


def redis_ttl_config(settings: Settings) -> dict[str, object] | None:
    ttl_minutes = settings.langgraph_checkpoint_ttl_minutes
    if ttl_minutes <= 0:
        return None
    return {
        "default_ttl": ttl_minutes,
        "refresh_on_read": settings.langgraph_checkpoint_refresh_on_read,
    }

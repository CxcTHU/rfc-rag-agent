from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings

try:  # pragma: no cover - covered through injected fake modules in tests.
    import redis as redis_module
except ImportError:  # pragma: no cover
    redis_module = None


@dataclass(frozen=True)
class RedisConnectionStatus:
    configured: bool
    available: bool
    reason: str


class RedisClientFactory:
    """Create optional Redis clients with graceful fallback semantics."""

    def __init__(
        self,
        redis_url: str,
        *,
        socket_timeout_seconds: float = 1.0,
        redis_library: Any | None = redis_module,
    ) -> None:
        self.redis_url = (redis_url or "").strip()
        self.socket_timeout_seconds = socket_timeout_seconds
        self.redis_library = redis_library
        self._last_status = RedisConnectionStatus(
            configured=bool(self.redis_url),
            available=False,
            reason="not_checked",
        )

    @property
    def last_status(self) -> RedisConnectionStatus:
        return self._last_status

    def create_client(self) -> Any | None:
        if not self.redis_url:
            self._last_status = RedisConnectionStatus(
                configured=False,
                available=False,
                reason="redis_url_not_configured",
            )
            return None
        if self.redis_library is None:
            self._last_status = RedisConnectionStatus(
                configured=True,
                available=False,
                reason="redis_package_not_installed",
            )
            return None

        try:
            client = self.redis_library.Redis.from_url(
                self.redis_url,
                socket_timeout=self.socket_timeout_seconds,
                socket_connect_timeout=self.socket_timeout_seconds,
                decode_responses=False,
            )
            client.ping()
        except Exception as exc:  # Redis fallback must absorb connection issues.
            self._last_status = RedisConnectionStatus(
                configured=True,
                available=False,
                reason=f"{exc.__class__.__name__}: {exc}",
            )
            return None

        self._last_status = RedisConnectionStatus(
            configured=True,
            available=True,
            reason="ok",
        )
        return client


def get_redis_client(settings: Settings | None = None) -> Any | None:
    active_settings = settings or get_settings()
    return RedisClientFactory(
        active_settings.redis_url,
        socket_timeout_seconds=active_settings.redis_socket_timeout_seconds,
    ).create_client()

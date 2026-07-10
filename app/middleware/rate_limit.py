from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import Settings, get_settings
from app.services.cache.redis_client import get_redis_client


RATE_LIMITED_PATHS = frozenset(
    {
        "/agent/query",
        "/agent/query/stream",
        "/agent/judge",
        "/agent/upload-image",
        "/chat",
        "/search",
        "/search/vector",
        "/search/hybrid",
        "/documents/import",
        "/sources/sync",
        "/feedback",
        "/feedback/export",
    }
)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch_seconds: int


class RedisSlidingWindowRateLimiter:
    def __init__(
        self,
        redis_client: Any,
        *,
        limit: int,
        window_seconds: int,
        key_prefix: str = "ratelimit",
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0")
        self.redis_client = redis_client
        self.limit = limit
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix.strip(":") or "ratelimit"

    def check(self, *, client_id: str, endpoint: str, now: float | None = None) -> RateLimitDecision:
        current_time = time.time() if now is None else now
        window_start = current_time - self.window_seconds
        key = rate_limit_key(client_id, endpoint, prefix=self.key_prefix)

        self.redis_client.zremrangebyscore(key, 0, window_start)
        count = int(self.redis_client.zcard(key))
        if count >= self.limit:
            reset_at = self._reset_time(key, current_time)
            return RateLimitDecision(
                allowed=False,
                limit=self.limit,
                remaining=0,
                reset_epoch_seconds=reset_at,
            )

        member = f"{current_time:.6f}"
        self.redis_client.zadd(key, {member: current_time})
        self.redis_client.expire(key, self.window_seconds)
        return RateLimitDecision(
            allowed=True,
            limit=self.limit,
            remaining=max(0, self.limit - count - 1),
            reset_epoch_seconds=int(current_time + self.window_seconds),
        )

    def _reset_time(self, key: str, now: float) -> int:
        try:
            oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
        except Exception:
            oldest = []
        if oldest:
            return int(float(oldest[0][1]) + self.window_seconds)
        return int(now + self.window_seconds)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not rate_limit_should_apply(request, settings):
            return await call_next(request)

        redis_client = get_redis_client(settings)
        if redis_client is None:
            return await call_next(request)

        limiter = RedisSlidingWindowRateLimiter(
            redis_client,
            limit=settings.rate_limit_requests_per_minute,
            window_seconds=settings.rate_limit_window_seconds,
        )
        try:
            decision = limiter.check(
                client_id=client_identifier(request),
                endpoint=request.url.path,
            )
        except Exception:
            return await call_next(request)

        headers = rate_limit_headers(decision)
        if not decision.allowed:
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers=headers,
            )

        response: Response = await call_next(request)
        response.headers.update(headers)
        return response


def rate_limit_should_apply(request: Request, settings: Settings) -> bool:
    return settings.rate_limit_enabled and request.url.path in RATE_LIMITED_PATHS


def client_identifier(request: Request) -> str:
    settings = get_settings()
    forwarded_for = request.headers.get("x-forwarded-for") if settings.trust_forwarded_for else None
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    client = getattr(request, "client", None)
    if client is None:
        return "unknown"
    return getattr(client, "host", None) or "unknown"


def rate_limit_key(client_id: str, endpoint: str, *, prefix: str = "ratelimit") -> str:
    safe_client = client_id.replace(":", "_").replace("/", "_")
    safe_endpoint = endpoint.strip("/").replace("/", ":") or "root"
    return f"{prefix}:{safe_client}:{safe_endpoint}"


def rate_limit_headers(decision: RateLimitDecision) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
        "X-RateLimit-Reset": str(decision.reset_epoch_seconds),
    }

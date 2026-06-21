from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.middleware import rate_limit
from app.middleware.rate_limit import (
    RateLimitMiddleware,
    RedisSlidingWindowRateLimiter,
    client_identifier,
    rate_limit_key,
)


class FakeRedisZset:
    def __init__(self) -> None:
        self.zsets: dict[str, dict[str, float]] = {}
        self.fail = False

    def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
        if self.fail:
            raise TimeoutError("redis unavailable")
        values = self.zsets.setdefault(key, {})
        removed = [member for member, score in values.items() if minimum <= score <= maximum]
        for member in removed:
            values.pop(member, None)
        return len(removed)

    def zcard(self, key: str) -> int:
        if self.fail:
            raise TimeoutError("redis unavailable")
        return len(self.zsets.setdefault(key, {}))

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        if self.fail:
            raise TimeoutError("redis unavailable")
        self.zsets.setdefault(key, {}).update(mapping)
        return len(mapping)

    def expire(self, _key: str, _ttl_seconds: int) -> bool:
        if self.fail:
            raise TimeoutError("redis unavailable")
        return True

    def zrange(self, key: str, start: int, end: int, *, withscores: bool = False):
        values = sorted(self.zsets.setdefault(key, {}).items(), key=lambda item: item[1])
        selected = values[start : end + 1]
        if withscores:
            return selected
        return [member for member, _score in selected]


def test_redis_sliding_window_rate_limiter_blocks_and_recovers() -> None:
    redis_client = FakeRedisZset()
    limiter = RedisSlidingWindowRateLimiter(
        redis_client,
        limit=2,
        window_seconds=60,
    )

    first = limiter.check(client_id="127.0.0.1", endpoint="/agent/query", now=100.0)
    second = limiter.check(client_id="127.0.0.1", endpoint="/agent/query", now=101.0)
    blocked = limiter.check(client_id="127.0.0.1", endpoint="/agent/query", now=102.0)
    recovered = limiter.check(client_id="127.0.0.1", endpoint="/agent/query", now=161.0)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert blocked.allowed is False
    assert blocked.reset_epoch_seconds == 160
    assert recovered.allowed is True


def test_rate_limit_key_normalizes_client_and_endpoint() -> None:
    assert rate_limit_key("127.0.0.1:1234", "/agent/query") == "ratelimit:127.0.0.1_1234:agent:query"


def test_rate_limit_middleware_returns_429_with_headers(monkeypatch) -> None:
    redis_client = FakeRedisZset()
    monkeypatch.setattr(
        rate_limit,
        "get_settings",
        lambda: Settings(rate_limit_enabled=True, rate_limit_requests_per_minute=1),
    )
    monkeypatch.setattr(rate_limit, "get_redis_client", lambda _settings: redis_client)

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/agent/query")
    async def query():
        return {"ok": True}

    @app.post("/agent/query/stream")
    async def stream_query():
        return {"ok": True}

    client = TestClient(app)

    first = client.post("/agent/query")
    second = client.post("/agent/query")
    first_stream = client.post("/agent/query/stream")
    second_stream = client.post("/agent/query/stream")

    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "1"
    assert first.headers["X-RateLimit-Remaining"] == "0"
    assert second.status_code == 429
    assert second.json() == {"detail": "rate limit exceeded"}
    assert second.headers["X-RateLimit-Limit"] == "1"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert "X-RateLimit-Reset" in second.headers
    assert first_stream.status_code == 200
    assert second_stream.status_code == 429


def test_rate_limit_middleware_fail_open_and_ignores_other_paths(monkeypatch) -> None:
    monkeypatch.setattr(
        rate_limit,
        "get_settings",
        lambda: Settings(rate_limit_enabled=True, rate_limit_requests_per_minute=1),
    )
    monkeypatch.setattr(rate_limit, "get_redis_client", lambda _settings: None)

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/agent/query")
    async def query():
        return {"ok": True}

    @app.get("/search")
    async def search():
        return {"ok": True}

    client = TestClient(app)

    assert client.post("/agent/query").status_code == 200
    assert client.post("/agent/query").status_code == 200
    assert client.get("/search").status_code == 200


def test_client_identifier_prefers_forwarded_for() -> None:
    app = FastAPI()

    @app.get("/")
    async def root():
        return {"ok": True}

    client = TestClient(app)
    request = client.build_request(
        "GET",
        "http://testserver/",
        headers={"x-forwarded-for": "203.0.113.8, 127.0.0.1"},
    )

    assert client_identifier(request) == "203.0.113.8"

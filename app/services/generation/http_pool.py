from __future__ import annotations

import hashlib
import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.services.observability.latency_trace import get_current_latency_trace


RETRYABLE_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass
class PooledJsonResponse:
    payload: dict[str, Any]
    status_code: int
    elapsed_ms: float


class HttpJsonConnectionPool:
    def __init__(self) -> None:
        self._clients: dict[str, _PooledJsonClient] = {}
        self._sse_clients: dict[str, _PooledSseClient] = {}
        self._lock = threading.Lock()

    def request_json(
        self,
        request: urllib.request.Request,
        *,
        timeout: float,
        provider_name: str,
        model_name: str,
    ) -> PooledJsonResponse:
        parsed = urllib.parse.urlsplit(request.full_url)
        key = pool_key(
            parsed=parsed,
            provider_name=provider_name,
            model_name=model_name,
            request=request,
        )
        with self._lock:
            client = self._clients.get(key)
            if client is None:
                client = _PooledJsonClient(parsed=parsed, pool_key=key)
                self._clients[key] = client
        return client.request_json(request, timeout=timeout)

    def open_sse(
        self,
        request: urllib.request.Request,
        *,
        timeout: float,
        provider_name: str,
        model_name: str,
    ) -> "PooledSseLease":
        parsed = urllib.parse.urlsplit(request.full_url)
        key = pool_key(
            parsed=parsed,
            provider_name=provider_name,
            model_name=model_name,
            request=request,
        )
        with self._lock:
            client = self._sse_clients.get(key)
            if client is None:
                client = _PooledSseClient(parsed=parsed, pool_key=key)
                self._sse_clients[key] = client
        return client.open(request, timeout=timeout)


class _PooledJsonClient:
    def __init__(self, *, parsed: urllib.parse.SplitResult, pool_key: str) -> None:
        self._scheme = parsed.scheme
        self._host = parsed.hostname or ""
        self._port = parsed.port
        self._pool_key = pool_key
        self._connection: http.client.HTTPConnection | None = None
        self._lock = threading.Lock()

    def request_json(
        self,
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> PooledJsonResponse:
        with self._lock:
            return self._request_json_locked(request, timeout=timeout)

    def _request_json_locked(
        self,
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> PooledJsonResponse:
        started = time.perf_counter()
        parsed = urllib.parse.urlsplit(request.full_url)
        path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        body = request.data or b""
        headers = request_headers(request)
        reused = self._connection is not None
        try:
            connection = self._ensure_connection(timeout=timeout)
            connection.request(request.get_method(), path, body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read()
        except (OSError, http.client.HTTPException):
            self.close()
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        trace_pooled_http(
            pool_key=self._pool_key,
            reused=reused,
            elapsed_ms=elapsed_ms,
            status_code=response.status,
        )
        if response.status in RETRYABLE_HTTP_STATUS:
            raise urllib.error.HTTPError(
                request.full_url,
                response.status,
                response.reason,
                response.headers,
                _BytesErrorBody(response_body),
            )
        if response.status >= 400:
            raise urllib.error.HTTPError(
                request.full_url,
                response.status,
                response.reason,
                response.headers,
                _BytesErrorBody(response_body),
            )
        try:
            payload = json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("HTTP JSON response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("HTTP JSON response must be an object")
        return PooledJsonResponse(
            payload=payload,
            status_code=response.status,
            elapsed_ms=elapsed_ms,
        )

    def _ensure_connection(self, *, timeout: float) -> http.client.HTTPConnection:
        if self._connection is not None:
            self._connection.timeout = timeout
            return self._connection
        if self._scheme == "https":
            connection: http.client.HTTPConnection = http.client.HTTPSConnection(
                self._host,
                self._port,
                timeout=timeout,
            )
        else:
            connection = http.client.HTTPConnection(
                self._host,
                self._port,
                timeout=timeout,
            )
        self._connection = connection
        return connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


class PooledSseLease:
    """Own a pooled HTTP connection until an SSE response is fully consumed."""

    def __init__(self, client: "_PooledSseClient", response: http.client.HTTPResponse) -> None:
        self._client = client
        self._response = response
        self._completed = False
        self._closed = False

    def __iter__(self):
        return iter(self._response)

    def mark_complete(self) -> None:
        self._completed = True

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._client.release(self._response, clean=self._completed)


class _PooledSseClient:
    def __init__(self, *, parsed: urllib.parse.SplitResult, pool_key: str) -> None:
        self._scheme = parsed.scheme
        self._host = parsed.hostname or ""
        self._port = parsed.port
        self._pool_key = pool_key
        self._connection: http.client.HTTPConnection | None = None
        self._lock = threading.Lock()

    def open(self, request: urllib.request.Request, *, timeout: float) -> PooledSseLease:
        self._lock.acquire()
        started = time.perf_counter()
        reused = self._connection is not None
        try:
            parsed = urllib.parse.urlsplit(request.full_url)
            path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            connection = self._ensure_connection(timeout=timeout)
            connection.request(
                request.get_method(),
                path,
                body=request.data or b"",
                headers=request_headers(request),
            )
            response = connection.getresponse()
            trace_pooled_http(
                pool_key=self._pool_key,
                reused=reused,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                status_code=response.status,
            )
            if response.status >= 400:
                body = response.read()
                self.close()
                raise urllib.error.HTTPError(
                    request.full_url,
                    response.status,
                    response.reason,
                    response.headers,
                    _BytesErrorBody(body),
                )
            return PooledSseLease(self, response)
        except Exception:
            self.close()
            self._lock.release()
            raise

    def release(self, response: http.client.HTTPResponse, *, clean: bool) -> None:
        try:
            if clean:
                response.read()
            response.close()
        except (OSError, http.client.HTTPException):
            clean = False
        if not clean:
            self.close()
        self._lock.release()

    def _ensure_connection(self, *, timeout: float) -> http.client.HTTPConnection:
        if self._connection is not None:
            self._connection.timeout = timeout
            return self._connection
        if self._scheme == "https":
            connection: http.client.HTTPConnection = http.client.HTTPSConnection(
                self._host,
                self._port,
                timeout=timeout,
            )
        else:
            connection = http.client.HTTPConnection(self._host, self._port, timeout=timeout)
        self._connection = connection
        return connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


class _BytesErrorBody:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, *args: object, **kwargs: object) -> bytes:
        del args, kwargs
        return self._body

    def close(self) -> None:
        return None


def request_headers(request: urllib.request.Request) -> dict[str, str]:
    headers = dict(request.header_items())
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        canonical = "Content-Type" if key.casefold() == "content-type" else key
        normalized[canonical] = value
    normalized.setdefault("Connection", "keep-alive")
    return normalized


def pool_key(
    *,
    parsed: urllib.parse.SplitResult,
    provider_name: str,
    model_name: str,
    request: urllib.request.Request,
) -> str:
    headers = dict(request.header_items())
    secret = headers.get("Authorization") or headers.get("authorization") or headers.get("api-key") or ""
    fingerprint = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12] if secret else "no-key"
    netloc = parsed.netloc.casefold()
    return "|".join(
        [
            parsed.scheme.casefold(),
            netloc,
            provider_name.casefold(),
            model_name.casefold(),
            fingerprint,
        ]
    )


def trace_pooled_http(
    *,
    pool_key: str,
    reused: bool,
    elapsed_ms: float,
    status_code: int,
) -> None:
    trace = get_current_latency_trace()
    if trace is None:
        return
    trace.add_duration("provider_http_latency_ms", elapsed_ms)
    trace.set_value("provider_http_last_status", status_code)
    trace.set_value("provider_http_last_connection_reused", reused)
    trace.set_value("provider_http_last_pool_key_hash", hashlib.sha256(pool_key.encode("utf-8")).hexdigest()[:12])
    count = int(trace.values.get("provider_http_request_count", 0)) + 1
    trace.set_value("provider_http_request_count", count)
    if reused:
        reused_count = int(trace.values.get("provider_http_reused_connection_count", 0)) + 1
        trace.set_value("provider_http_reused_connection_count", reused_count)


HTTP_JSON_CONNECTION_POOL = HttpJsonConnectionPool()

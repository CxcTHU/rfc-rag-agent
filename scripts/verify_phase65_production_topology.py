"""Verify Phase 65 required production-topology evidence.

This module starts with the deterministic gate summary used by tests. The
executable probe path is intentionally fail-closed until real PostgreSQL,
pgvector, Redis, auth, checkpoint, and Agent SSE checks populate every required
component with ``pass``.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.session import create_database_engine
from app.services.cache.redis_client import RedisClientFactory


ComponentStatus = Literal["pass", "fail", "skip"]
REQUIRED_COMPONENTS = (
    "postgres",
    "pgvector",
    "redis",
    "auth",
    "checkpoint",
    "agent_sse",
)
ProbeFn = Callable[[], "ProbeResult"]
EngineFactory = Callable[[str], Any]
RedisFactory = Callable[..., Any]
HttpJsonFn = Callable[[str, str, dict[str, object] | None, str | None], dict[str, object]]
HttpSseFn = Callable[[str, str], set[str]]


@dataclass(frozen=True)
class ProbeResult:
    status: ComponentStatus
    category: str = "ok"

    def safe_detail(self) -> dict[str, str]:
        return {
            "status": normalize_status(self.status),
            "category": safe_category(self.category),
        }


def normalize_status(value: str | None) -> ComponentStatus:
    if value == "pass":
        return "pass"
    if value == "skip":
        return "skip"
    return "fail"


def build_topology_summary(**statuses: str) -> dict[str, object]:
    normalized = {
        name: normalize_status(statuses.get(name)) for name in REQUIRED_COMPONENTS
    }
    skipped = [name for name, status in normalized.items() if status == "skip"]
    failed = [name for name, status in normalized.items() if status != "pass"]
    return {
        "schema_version": "phase65-topology-v1",
        "gate": "pass" if not failed else "blocked",
        "components": normalized,
        "skipped_required": skipped,
        "failed_required": failed,
    }


def safe_category(value: str | None) -> str:
    candidate = "".join(
        character
        for character in str(value or "unknown").lower()
        if character.isalnum() or character in {"_", "-"}
    )
    return candidate[:80] or "unknown"


def is_postgres_database_url(database_url: str) -> bool:
    try:
        backend = make_url(database_url).get_backend_name()
    except Exception:
        return False
    return backend in {"postgresql", "postgres"}


def probe_postgres(
    *,
    database_url: str | None = None,
    engine_factory: EngineFactory = create_database_engine,
) -> ProbeResult:
    url = (database_url if database_url is not None else os.getenv("DATABASE_URL", "")).strip()
    if not url:
        return ProbeResult("skip", "missing_database_url")
    if not is_postgres_database_url(url):
        return ProbeResult("fail", "non_postgres_database_url")
    try:
        engine = engine_factory(url)
        with engine.begin() as connection:
            selected = connection.execute(text("SELECT 1")).scalar()
    except Exception:
        return ProbeResult("fail", "postgres_unavailable")
    if selected != 1:
        return ProbeResult("fail", "postgres_unexpected_result")
    return ProbeResult("pass")


def probe_pgvector(
    *,
    database_url: str | None = None,
    engine_factory: EngineFactory = create_database_engine,
) -> ProbeResult:
    url = (database_url if database_url is not None else os.getenv("DATABASE_URL", "")).strip()
    if not url:
        return ProbeResult("skip", "missing_database_url")
    if not is_postgres_database_url(url):
        return ProbeResult("fail", "non_postgres_database_url")
    try:
        engine = engine_factory(url)
        with engine.begin() as connection:
            selected = connection.execute(text("SELECT 1")).scalar()
            if selected != 1:
                return ProbeResult("fail", "postgres_unexpected_result")
            has_vector = bool(
                connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")
                ).scalar()
            )
    except Exception:
        return ProbeResult("fail", "pgvector_check_failed")
    if not has_vector:
        return ProbeResult("fail", "pgvector_extension_missing")
    return ProbeResult("pass")


def probe_redis(
    *,
    redis_url: str | None = None,
    socket_timeout_seconds: float = 1.0,
    redis_factory: RedisFactory = RedisClientFactory,
) -> ProbeResult:
    url = (redis_url if redis_url is not None else os.getenv("REDIS_URL", "")).strip()
    if not url:
        return ProbeResult("skip", "missing_redis_url")
    try:
        factory = redis_factory(
            url,
            socket_timeout_seconds=socket_timeout_seconds,
        )
        client = factory.create_client()
    except Exception:
        return ProbeResult("fail", "redis_exception")
    status = getattr(factory, "last_status", None)
    if client is None:
        reason = str(getattr(status, "reason", "redis_unavailable"))
        normalized_reason = safe_category(reason)
        if normalized_reason == "redis_url_not_configured":
            return ProbeResult("skip", "missing_redis_url")
        if normalized_reason == "redis_package_not_installed":
            return ProbeResult("skip", "redis_package_missing")
        return ProbeResult("fail", "redis_unavailable")
    return ProbeResult("pass")


def http_json_request(
    method: str,
    url: str,
    payload: dict[str, object] | None,
    token: str | None = None,
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            parsed: object = json.loads(body) if body else {}
            return {
                "status_code": int(response.status),
                "json": parsed if isinstance(parsed, dict) else {},
            }
    except urllib.error.HTTPError as exc:
        return {"status_code": int(exc.code), "json": {}}
    except Exception:
        return {"status_code": 0, "json": {}}


def join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def probe_auth(
    *,
    base_url: str | None = None,
    http_json: HttpJsonFn = http_json_request,
    token_sink: dict[str, str] | None = None,
) -> ProbeResult:
    base = (base_url or "").strip()
    if not base:
        return ProbeResult("skip", "missing_base_url")
    suffix = uuid.uuid4().hex[:12]
    username = f"phase65_topology_{suffix}"
    password = uuid.uuid4().hex + uuid.uuid4().hex
    email = f"{username}@example.com"
    register = http_json(
        "POST",
        join_url(base, "/auth/register"),
        {"username": username, "email": email, "password": password},
        None,
    )
    if int(register.get("status_code", 0) or 0) not in {200, 409}:
        return ProbeResult("fail", "auth_register_failed")
    login = http_json(
        "POST",
        join_url(base, "/auth/login"),
        {"username_or_email": username, "password": password},
        None,
    )
    if int(login.get("status_code", 0) or 0) != 200:
        return ProbeResult("fail", "auth_login_failed")
    login_json = login.get("json", {})
    token = str(login_json.get("access_token", "")) if isinstance(login_json, dict) else ""
    if not token:
        return ProbeResult("fail", "auth_token_missing")
    me = http_json("GET", join_url(base, "/auth/me"), None, token)
    if int(me.get("status_code", 0) or 0) != 200:
        return ProbeResult("fail", "auth_me_failed")
    if token_sink is not None:
        token_sink["token"] = token
    return ProbeResult("pass")


def http_sse_event_names(
    base_url: str,
    token: str,
    *,
    timeout_seconds: float = 30.0,
) -> set[str]:
    payload = {"question": "你用的什么模型？"}
    request = urllib.request.Request(
        join_url(base_url, "/agent/query/stream"),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    event_names: set[str] = set()
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("event:"):
                continue
            event_name = line.partition(":")[2].strip()
            if event_name:
                event_names.add(event_name)
            if event_name == "done":
                break
    return event_names


def probe_agent_sse(
    *,
    base_url: str | None = None,
    token_getter: Callable[[], str],
    http_sse: HttpSseFn = http_sse_event_names,
) -> ProbeResult:
    base = (base_url or "").strip()
    if not base:
        return ProbeResult("skip", "missing_base_url")
    token = token_getter().strip()
    if not token:
        return ProbeResult("skip", "missing_auth_token")
    try:
        event_names = http_sse(base, token)
    except Exception:
        return ProbeResult("fail", "agent_sse_unavailable")
    if "done" not in event_names:
        return ProbeResult("fail", "agent_sse_done_missing")
    if not ({"metadata", "agent_step", "token"} & event_names):
        return ProbeResult("fail", "agent_sse_events_missing")
    return ProbeResult("pass")


def probe_checkpoint(
    *,
    database_url: str | None = None,
    engine_factory: EngineFactory = create_database_engine,
) -> ProbeResult:
    url = (database_url if database_url is not None else os.getenv("DATABASE_URL", "")).strip()
    if not url:
        return ProbeResult("skip", "missing_database_url")
    if not is_postgres_database_url(url):
        return ProbeResult("fail", "non_postgres_database_url")
    run_id = f"phase65-topology-{uuid.uuid4().hex}"
    try:
        engine = engine_factory(url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO agent_runtime_runs "
                    "(run_id,status,current_node,last_completed_node,resume_token_hash,"
                    "request_question,canonical_task,state_json,created_at,updated_at) "
                    "VALUES (:run_id,'stopped','topology_probe','topology_probe',"
                    ":resume_token_hash,'topology_probe','topology_probe','{}',"
                    "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                ),
                {"run_id": run_id, "resume_token_hash": uuid.uuid4().hex},
            )
            selected = connection.execute(
                text("SELECT 1 FROM agent_runtime_runs WHERE run_id=:run_id"),
                {"run_id": run_id},
            ).scalar()
            connection.execute(
                text("DELETE FROM agent_runtime_runs WHERE run_id=:run_id"),
                {"run_id": run_id},
            )
    except Exception:
        return ProbeResult("fail", "checkpoint_unavailable")
    if selected != 1:
        return ProbeResult("fail", "checkpoint_roundtrip_failed")
    return ProbeResult("pass")


def run_topology_probes(probes: Mapping[str, ProbeFn]) -> dict[str, object]:
    results: dict[str, ProbeResult] = {}
    for name in REQUIRED_COMPONENTS:
        probe = probes.get(name)
        if probe is None:
            results[name] = ProbeResult("skip", "missing_probe")
            continue
        try:
            result = probe()
        except Exception:
            result = ProbeResult("fail", "exception")
        results[name] = ProbeResult(
            normalize_status(result.status),
            safe_category(result.category),
        )
    summary = build_topology_summary(
        **{name: result.status for name, result in results.items()}
    )
    summary["details"] = {
        name: result.safe_detail() for name, result in results.items()
    }
    return summary


def build_probe_summary(
    *,
    database_url: str | None = None,
    redis_url: str | None = None,
    base_url: str | None = None,
    engine_factory: EngineFactory = create_database_engine,
    redis_factory: RedisFactory = RedisClientFactory,
    http_json: HttpJsonFn = http_json_request,
    http_sse: HttpSseFn = http_sse_event_names,
) -> dict[str, object]:
    auth_state: dict[str, str] = {}
    return run_topology_probes(
        {
            "postgres": lambda: probe_postgres(
                database_url=database_url,
                engine_factory=engine_factory,
            ),
            "pgvector": lambda: probe_pgvector(
                database_url=database_url,
                engine_factory=engine_factory,
            ),
            "redis": lambda: probe_redis(
                redis_url=redis_url,
                redis_factory=redis_factory,
            ),
            "auth": lambda: probe_auth(
                base_url=base_url,
                http_json=http_json,
                token_sink=auth_state,
            ),
            "checkpoint": lambda: probe_checkpoint(
                database_url=database_url,
                engine_factory=engine_factory,
            ),
            "agent_sse": lambda: probe_agent_sse(
                base_url=base_url,
                token_getter=lambda: auth_state.get("token", ""),
                http_sse=http_sse,
            ),
        }
    )


def build_unprobed_summary() -> dict[str, object]:
    return run_topology_probes(
        {name: (lambda: ProbeResult("skip", "not_configured")) for name in REQUIRED_COMPONENTS}
    )


def write_summary(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("output/phase65-topology.json"),
        help="Safe topology summary output path.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("PHASE65_TOPOLOGY_BASE_URL", ""),
        help="Running app base URL for auth and Agent SSE probes.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", settings.database_url),
        help="PostgreSQL URL. The value is used only for probing and is never written.",
    )
    parser.add_argument(
        "--redis-url",
        default=os.getenv("REDIS_URL", settings.redis_url),
        help="Redis URL. The value is used only for probing and is never written.",
    )
    args = parser.parse_args(argv)
    summary = build_probe_summary(
        database_url=args.database_url,
        redis_url=args.redis_url,
        base_url=args.base_url,
    )
    write_summary(args.out, summary)
    print(
        "gate={gate} skipped_required={skipped_required} failed_required={failed_required}".format(
            **summary
        )
    )
    return 0 if summary["gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

from scripts.verify_phase65_production_topology import (
    ProbeResult,
    build_probe_summary,
    build_topology_summary,
    probe_agent_sse,
    probe_auth,
    probe_checkpoint,
    probe_pgvector,
    probe_postgres,
    probe_redis,
    run_topology_probes,
)


def test_required_integration_skip_blocks_gate() -> None:
    summary = build_topology_summary(
        postgres="pass",
        pgvector="pass",
        redis="skip",
        auth="pass",
        checkpoint="pass",
        agent_sse="pass",
    )

    assert summary["gate"] == "blocked"
    assert summary["skipped_required"] == ["redis"]
    assert summary["failed_required"] == ["redis"]


def test_required_integration_failure_blocks_gate() -> None:
    summary = build_topology_summary(
        postgres="pass",
        pgvector="fail",
        redis="pass",
        auth="pass",
        checkpoint="pass",
        agent_sse="pass",
    )

    assert summary["gate"] == "blocked"
    assert summary["skipped_required"] == []
    assert summary["failed_required"] == ["pgvector"]


def test_all_required_components_pass() -> None:
    summary = build_topology_summary(
        postgres="pass",
        pgvector="pass",
        redis="pass",
        auth="pass",
        checkpoint="pass",
        agent_sse="pass",
    )

    assert summary["gate"] == "pass"
    assert summary["skipped_required"] == []
    assert summary["failed_required"] == []


def test_probe_runner_collects_safe_pass_fail_and_skip_results() -> None:
    def postgres_probe() -> ProbeResult:
        return ProbeResult("pass")

    def redis_probe() -> ProbeResult:
        return ProbeResult("skip", "missing_env")

    def auth_probe() -> ProbeResult:
        raise RuntimeError("password=secret-value should never leak")

    summary = run_topology_probes(
        {
            "postgres": postgres_probe,
            "pgvector": lambda: ProbeResult("pass"),
            "redis": redis_probe,
            "auth": auth_probe,
            "checkpoint": lambda: ProbeResult("pass"),
            "agent_sse": lambda: ProbeResult("pass"),
        }
    )

    assert summary["gate"] == "blocked"
    assert summary["components"]["postgres"] == "pass"
    assert summary["components"]["redis"] == "skip"
    assert summary["components"]["auth"] == "fail"
    assert summary["skipped_required"] == ["redis"]
    assert summary["failed_required"] == ["redis", "auth"]
    assert summary["details"]["redis"] == {"status": "skip", "category": "missing_env"}
    assert summary["details"]["auth"] == {"status": "fail", "category": "exception"}
    assert "secret-value" not in str(summary)


class _FakeScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar(self) -> object:
        return self.value


class _FakeConnection:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute(
        self,
        _statement: object,
        _params: object | None = None,
    ) -> _FakeScalarResult:
        return _FakeScalarResult(self.values.pop(0))


class _FakeEngine:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self.values)


def test_postgres_probe_requires_postgres_url_and_selects_one() -> None:
    assert probe_postgres(database_url="").safe_detail() == {
        "status": "skip",
        "category": "missing_database_url",
    }
    assert probe_postgres(database_url="sqlite:///local.db").safe_detail() == {
        "status": "fail",
        "category": "non_postgres_database_url",
    }

    result = probe_postgres(
        database_url="postgresql://user:pass@localhost/db",
        engine_factory=lambda _url: _FakeEngine([1]),
    )

    assert result.safe_detail() == {"status": "pass", "category": "ok"}


def test_pgvector_probe_requires_vector_extension() -> None:
    missing = probe_pgvector(
        database_url="postgresql://user:pass@localhost/db",
        engine_factory=lambda _url: _FakeEngine([1, False]),
    )
    present = probe_pgvector(
        database_url="postgresql://user:pass@localhost/db",
        engine_factory=lambda _url: _FakeEngine([1, True]),
    )

    assert missing.safe_detail() == {
        "status": "fail",
        "category": "pgvector_extension_missing",
    }
    assert present.safe_detail() == {"status": "pass", "category": "ok"}


def test_redis_probe_uses_factory_status_without_leaking_url() -> None:
    class FakeUnavailableFactory:
        def __init__(self, _url: str, socket_timeout_seconds: float = 1.0) -> None:
            self.last_status = type(
                "Status",
                (),
                {
                    "configured": True,
                    "available": False,
                    "reason": "TimeoutError: redis://:secret@localhost unavailable",
                },
            )()

        def create_client(self) -> object | None:
            return None

    class FakeAvailableFactory:
        def __init__(self, _url: str, socket_timeout_seconds: float = 1.0) -> None:
            self.last_status = type(
                "Status",
                (),
                {"configured": True, "available": True, "reason": "ok"},
            )()

        def create_client(self) -> object:
            return object()

    missing = probe_redis(redis_url="")
    unavailable = probe_redis(
        redis_url="redis://:secret@localhost/0",
        redis_factory=FakeUnavailableFactory,
    )
    available = probe_redis(
        redis_url="redis://:secret@localhost/0",
        redis_factory=FakeAvailableFactory,
    )

    assert missing.safe_detail() == {
        "status": "skip",
        "category": "missing_redis_url",
    }
    assert unavailable.status == "fail"
    assert "secret" not in unavailable.category
    assert available.safe_detail() == {"status": "pass", "category": "ok"}


def test_auth_probe_registers_logs_in_and_keeps_token_out_of_summary() -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_json(method: str, url: str, payload: dict[str, object] | None, token: str | None = None) -> dict[str, object]:
        calls.append((method, url, payload))
        if url.endswith("/auth/register"):
            assert payload is not None
            assert str(payload["email"]).endswith("@example.com")
            return {"status_code": 200, "json": {"id": 1}}
        if url.endswith("/auth/login"):
            return {
                "status_code": 200,
                "json": {"access_token": "secret-token", "token_type": "bearer"},
            }
        if url.endswith("/auth/me") and token == "secret-token":
            return {"status_code": 200, "json": {"id": 1}}
        return {"status_code": 500, "json": {}}

    token_sink: dict[str, str] = {}
    result = probe_auth(
        base_url="http://127.0.0.1:8001",
        http_json=fake_json,
        token_sink=token_sink,
    )

    assert result.safe_detail() == {"status": "pass", "category": "ok"}
    assert token_sink == {"token": "secret-token"}
    assert [call[1].rsplit("/", 2)[-2:] for call in calls] == [
        ["auth", "register"],
        ["auth", "login"],
        ["auth", "me"],
    ]
    assert "secret-token" not in str(result.safe_detail())


def test_agent_sse_probe_requires_auth_token_and_done_event() -> None:
    assert probe_agent_sse(base_url="", token_getter=lambda: "token").safe_detail() == {
        "status": "skip",
        "category": "missing_base_url",
    }
    assert probe_agent_sse(
        base_url="http://127.0.0.1:8001",
        token_getter=lambda: "",
    ).safe_detail() == {"status": "skip", "category": "missing_auth_token"}

    result = probe_agent_sse(
        base_url="http://127.0.0.1:8001",
        token_getter=lambda: "secret-token",
        http_sse=lambda _base_url, _token: {"agent_step", "metadata", "done"},
    )

    assert result.safe_detail() == {"status": "pass", "category": "ok"}


def test_checkpoint_probe_writes_and_deletes_synthetic_run() -> None:
    statements: list[str] = []

    class CheckpointConnection(_FakeConnection):
        def execute(self, statement: object, _params: object | None = None) -> _FakeScalarResult:
            statements.append(str(statement))
            return _FakeScalarResult(1)

    class CheckpointEngine(_FakeEngine):
        def begin(self) -> CheckpointConnection:
            return CheckpointConnection(self.values)

    result = probe_checkpoint(
        database_url="postgresql://user:pass@localhost/db",
        engine_factory=lambda _url: CheckpointEngine([]),
    )

    assert result.safe_detail() == {"status": "pass", "category": "ok"}
    joined = "\n".join(statements).lower()
    assert "agent_runtime_runs" in joined
    assert "insert" in joined
    assert "delete" in joined


def test_default_probe_summary_runs_all_components_and_keeps_token_in_memory() -> None:
    class FakeAvailableFactory:
        def __init__(self, _url: str, socket_timeout_seconds: float = 1.0) -> None:
            self.last_status = type(
                "Status",
                (),
                {"configured": True, "available": True, "reason": "ok"},
            )()

        def create_client(self) -> object:
            return object()

    def fake_json(method: str, url: str, payload: dict[str, object] | None, token: str | None = None) -> dict[str, object]:
        if url.endswith("/auth/register"):
            return {"status_code": 200, "json": {"id": 1}}
        if url.endswith("/auth/login"):
            return {"status_code": 200, "json": {"access_token": "secret-token"}}
        if url.endswith("/auth/me") and token == "secret-token":
            return {"status_code": 200, "json": {"id": 1}}
        return {"status_code": 500, "json": {}}

    def fake_sse(_base_url: str, token: str) -> set[str]:
        assert token == "secret-token"
        return {"agent_step", "metadata", "done"}

    summary = build_probe_summary(
        database_url="postgresql://user:pass@localhost/db",
        redis_url="redis://:secret@localhost/0",
        base_url="http://127.0.0.1:8001",
        engine_factory=lambda _url: _FakeEngine([1, True, 1, 1]),
        redis_factory=FakeAvailableFactory,
        http_json=fake_json,
        http_sse=fake_sse,
    )

    assert summary["gate"] == "pass"
    assert set(summary["components"].values()) == {"pass"}
    assert "secret-token" not in str(summary)

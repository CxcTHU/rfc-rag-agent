from app.core.config import Settings


LATENCY_DEFAULT_ENV_KEYS = (
    "AGENT_SHORT_LOOP_ENABLED",
    "PHASE64_ROUTE_FIRST_ENABLED",
    "PHASE64_RETRIEVAL_FANOUT_ENABLED",
)


def test_phase66_promotes_latency_optimized_runtime_as_production_default(
    monkeypatch,
) -> None:
    for key in LATENCY_DEFAULT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.agent_short_loop_enabled is True
    assert settings.phase64_route_first_enabled is True
    assert settings.phase64_retrieval_fanout_enabled is True


def test_phase66_latency_defaults_keep_explicit_false_compatibility_override(
    monkeypatch,
) -> None:
    for key in LATENCY_DEFAULT_ENV_KEYS:
        monkeypatch.setenv(key, "false")

    settings = Settings(_env_file=None)

    assert settings.agent_short_loop_enabled is False
    assert settings.phase64_route_first_enabled is False
    assert settings.phase64_retrieval_fanout_enabled is False

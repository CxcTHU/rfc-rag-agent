from scripts.probe_phase65_runtime_recovery import (
    RecoveryProbeResult,
    build_recovery_summary,
    probe_cancel_marks_stopped_run,
    probe_resume_sse_from_checkpoint,
)


def test_recovery_summary_requires_cancel_and_resume_to_pass() -> None:
    summary = build_recovery_summary(
        cancel=RecoveryProbeResult("pass"),
        resume=RecoveryProbeResult("fail", "resume_metadata_missing"),
    )

    assert summary["schema_version"] == "phase65-runtime-recovery-v1"
    assert summary["gate"] == "blocked"
    assert summary["components"] == {
        "sse_cancel_marks_stopped": "pass",
        "resume_sse_from_checkpoint": "fail",
    }
    assert summary["failed_required"] == ["resume_sse_from_checkpoint"]
    assert "token" not in str(summary).casefold()


def test_cancel_probe_closes_stream_and_requires_stopped_run() -> None:
    calls: list[str] = []

    def fake_json(method, url, payload, token=None):
        calls.append(url)
        assert token == "secret-token"
        assert method == "POST"
        assert url.endswith("/conversations")
        assert payload == {"title": "Phase65 runtime recovery smoke"}
        return {"status_code": 200, "json": {"id": 42}}

    result = probe_cancel_marks_stopped_run(
        base_url="http://127.0.0.1:8011",
        token="secret-token",
        http_json=fake_json,
        cancel_sse=lambda _base, _token, conversation_id: {"agent_step"},
        latest_stopped_run=lambda conversation_id: "run-stopped"
        if conversation_id == 42
        else "",
    )

    assert result.safe_detail() == {"status": "pass", "category": "ok"}
    assert calls == ["http://127.0.0.1:8011/conversations"]


def test_cancel_probe_fails_closed_when_stopped_run_is_not_observed() -> None:
    result = probe_cancel_marks_stopped_run(
        base_url="http://127.0.0.1:8011",
        token="secret-token",
        http_json=lambda *_args, **_kwargs: {"status_code": 200, "json": {"id": 5}},
        cancel_sse=lambda *_args: {"agent_step"},
        latest_stopped_run=lambda _conversation_id: "",
    )

    assert result.safe_detail() == {
        "status": "fail",
        "category": "cancel_stopped_run_missing",
    }


def test_resume_probe_uses_checkpoint_and_requires_runtime_resume_metadata() -> None:
    inserted: list[int] = []

    def fake_sse(_base, _token, payload):
        assert payload["conversation_id"] == 7
        assert payload["resume_run_id"] == "run-synthetic"
        assert payload["resume_policy"] == "force"
        return {
            "event_names": {"agent_step", "metadata", "done"},
            "metadata": {
                "latency_trace": {
                    "runtime_resumed": True,
                    "runtime_resume_reason": "force",
                    "executed_tool_call_count": 0,
                }
            },
        }

    result = probe_resume_sse_from_checkpoint(
        base_url="http://127.0.0.1:8011",
        token="secret-token",
        conversation_id=7,
        insert_checkpoint=lambda conversation_id: inserted.append(conversation_id)
        or "run-synthetic",
        collect_sse=fake_sse,
    )

    assert result.safe_detail() == {"status": "pass", "category": "ok"}
    assert inserted == [7]


def test_resume_probe_fails_closed_on_tool_replay_or_missing_metadata() -> None:
    replay = probe_resume_sse_from_checkpoint(
        base_url="http://127.0.0.1:8011",
        token="secret-token",
        conversation_id=7,
        insert_checkpoint=lambda _conversation_id: "run-synthetic",
        collect_sse=lambda *_args: {
            "event_names": {"metadata", "done"},
            "metadata": {
                "latency_trace": {
                    "runtime_resumed": True,
                    "executed_tool_call_count": 1,
                }
            },
        },
    )
    missing = probe_resume_sse_from_checkpoint(
        base_url="http://127.0.0.1:8011",
        token="secret-token",
        conversation_id=7,
        insert_checkpoint=lambda _conversation_id: "run-synthetic",
        collect_sse=lambda *_args: {"event_names": {"done"}, "metadata": {}},
    )

    assert replay.safe_detail() == {
        "status": "fail",
        "category": "resume_replayed_tool_execution",
    }
    assert missing.safe_detail() == {
        "status": "fail",
        "category": "resume_metadata_missing",
    }

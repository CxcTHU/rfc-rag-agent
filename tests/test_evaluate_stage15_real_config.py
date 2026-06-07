from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.config import Settings
from scripts.evaluate_stage15_real_config import (
    SUITES,
    compact_error_summary,
    command_for_suite,
    evaluate_real_config,
    missing_chat_settings,
    missing_embedding_settings,
    redact_sensitive_text,
    update_embedding_comparison,
    write_status,
    read_status,
    merge_statuses_into_comparison,
)


def blank_settings() -> Settings:
    return Settings(
        embedding_provider="",
        embedding_model_name="",
        embedding_api_key="",
        embedding_base_url="",
        embedding_dimension=0,
        chat_model_provider="",
        chat_model_name="",
        chat_model_api_key="",
        chat_model_base_url="",
    )


def real_settings() -> Settings:
    return Settings(
        embedding_provider="openai-compatible",
        embedding_model_name="jina-embeddings-v3",
        embedding_api_key="embedding-secret",
        embedding_base_url="https://embedding.example/v1",
        embedding_dimension=1024,
        chat_model_provider="openai-compatible",
        chat_model_name="mimo-v2.5-pro",
        chat_model_api_key="chat-secret",
        chat_model_base_url="https://chat.example/v1",
    )


def test_missing_real_settings_are_reported() -> None:
    settings = blank_settings()

    assert "EMBEDDING_PROVIDER" in missing_embedding_settings(settings)
    assert "EMBEDDING_DIMENSION" in missing_embedding_settings(settings)
    assert "CHAT_MODEL_PROVIDER" in missing_chat_settings(settings)
    assert "CHAT_MODEL_API_KEY" in missing_chat_settings(settings)


def test_evaluate_real_config_skips_when_real_run_not_enabled(tmp_path) -> None:
    statuses = evaluate_real_config(settings=real_settings(), output_dir=tmp_path, run_real=False)

    assert len(statuses) == 7
    assert {status.status for status in statuses} == {"skipped"}
    assert all("--run-real" in status.skipped_reason for status in statuses)


def test_existing_real_result_files_are_marked_completed_without_runner(tmp_path) -> None:
    (tmp_path / "vector_results.csv").write_text("query_id,passed\nq1,yes\n", encoding="utf-8")

    statuses = evaluate_real_config(settings=real_settings(), output_dir=tmp_path, run_real=False)

    vector_status = next(status for status in statuses if status.suite == "vector")
    assert vector_status.status == "completed"
    assert vector_status.skipped_reason == ""


def test_run_real_uses_runner_and_writes_completed_status(tmp_path) -> None:
    def fake_runner(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        out_index = command.index("--out") + 1
        Path(command[out_index]).write_text("query_id,passed\nq1,yes\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    statuses = evaluate_real_config(
        settings=real_settings(),
        output_dir=tmp_path,
        run_real=True,
        runner=fake_runner,
        python_executable="python",
    )

    assert {status.status for status in statuses} == {"completed"}
    assert (tmp_path / "real_config_status.csv").exists() is False


def test_evaluate_real_config_can_write_incremental_status(tmp_path) -> None:
    status_path = tmp_path / "real_config_status.csv"

    statuses = evaluate_real_config(
        settings=real_settings(),
        output_dir=tmp_path,
        run_real=False,
        status_path=status_path,
    )

    assert len(statuses) == 7
    content = status_path.read_text(encoding="utf-8")
    assert "suite,status,output_file" in content
    assert "brain_workflow" in content


def test_runner_error_is_redacted(tmp_path) -> None:
    def failing_runner(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="bad key embedding-secret chat-secret")

    statuses = evaluate_real_config(
        settings=real_settings(),
        output_dir=tmp_path,
        run_real=True,
        runner=failing_runner,
        python_executable="python",
    )

    assert {status.status for status in statuses} == {"error"}
    assert all("embedding-secret" not in status.error_summary for status in statuses)
    assert all("chat-secret" not in status.error_summary for status in statuses)
    assert all("[REDACTED]" in status.error_summary for status in statuses)


def test_write_status_omits_secret_values(tmp_path) -> None:
    statuses = evaluate_real_config(settings=real_settings(), output_dir=tmp_path, run_real=False)
    out = tmp_path / "real_config_status.csv"

    write_status(out, statuses)

    content = out.read_text(encoding="utf-8")
    assert "suite,status,output_file" in content
    assert "embedding-secret" not in content
    assert "chat-secret" not in content


def test_command_for_suite_uses_existing_evaluation_scripts(tmp_path) -> None:
    settings = real_settings()
    command = command_for_suite(
        suite=next(status_suite for status_suite in SUITES if status_suite.name == "brain_workflow"),
        settings=settings,
        output_path=tmp_path / "brain_workflow_results.csv",
        output_dir=tmp_path,
        python_executable="python",
        batch_size=16,
    )

    assert "scripts/evaluate_brain_workflow.py" in command
    assert "--embedding-provider" in command
    assert "--chat-provider" in command
    assert "openai-compatible" in command


def test_redact_sensitive_text_replaces_known_keys() -> None:
    redacted = redact_sensitive_text("embedding-secret and chat-secret failed", real_settings())

    assert redacted == "[REDACTED] and [REDACTED] failed"


def test_compact_error_summary_preserves_head_and_tail() -> None:
    long_error = "Traceback start " + ("middle " * 200) + "SSL: UNEXPECTED_EOF_WHILE_READING"

    compact = compact_error_summary(long_error, limit=120)

    assert compact.startswith("Traceback start")
    assert "..." in compact
    assert compact.endswith("SSL: UNEXPECTED_EOF_WHILE_READING")


def test_update_embedding_comparison_returns_error_when_output_path_is_directory(tmp_path) -> None:
    comparison_dir = tmp_path / "comparison.csv"
    comparison_dir.mkdir()

    error = update_embedding_comparison(
        settings=blank_settings(),
        output_dir=tmp_path,
        comparison_out=comparison_dir,
    )

    assert "Embedding comparison update skipped" in error


def test_merge_statuses_into_comparison_preserves_real_config_error(tmp_path) -> None:
    from scripts.evaluate_stage14_embedding_comparison import EmbeddingComparisonSummary

    comparison = [
        EmbeddingComparisonSummary(
            config_name="real_config",
            suite="decompose",
            status="missing_results",
            passed=0,
            total=0,
            embedding_provider="openai-compatible",
            embedding_model_name="jina",
            embedding_dimension=1024,
            chat_provider="openai-compatible",
            chat_model_name="mimo",
            source_file="missing.csv",
            skipped_reason="Missing result file",
            notes="",
        )
    ]
    statuses = [
        next(status for status in evaluate_real_config(settings=real_settings(), output_dir=tmp_path, run_real=False) if status.suite == "decompose")
    ]
    statuses = [
        type(statuses[0])(
            **{**statuses[0].to_row(), "embedding_dimension": 1024, "status": "error", "error_summary": "SSL failed"}
        )
    ]

    merged = merge_statuses_into_comparison(comparison, statuses)

    assert merged[0].status == "error"
    assert merged[0].skipped_reason == "SSL failed"


def test_read_status_round_trips_written_rows(tmp_path) -> None:
    statuses = evaluate_real_config(settings=real_settings(), output_dir=tmp_path, run_real=False)
    out = tmp_path / "real_config_status.csv"
    write_status(out, statuses)

    loaded = read_status(out)

    assert len(loaded) == 7
    assert loaded[0].suite == statuses[0].suite

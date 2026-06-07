from pathlib import Path

from scripts.analyze_stage16_decompose_diagnostics import (
    build_decompose_diagnostic,
    classify_error_text,
    extract_progress_decompose_context,
    sanitize_evidence,
    write_diagnostics,
)


def write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_classify_ssl_eof_as_provider_network_error() -> None:
    result = classify_error_text(
        "error",
        "RuntimeError: Embedding model request failed: SSL: UNEXPECTED_EOF_WHILE_READING",
    )

    assert result["error_type"] == "ssl_eof"
    assert result["root_cause"] == "provider_network_ssl_eof"
    assert result["safe_to_retry"] == "yes"


def test_classify_timeout_as_provider_timeout() -> None:
    result = classify_error_text("error", "The read operation timed out")

    assert result["error_type"] == "timeout"
    assert result["root_cause"] == "provider_timeout"


def test_classify_truncated_traceback_as_script_orchestration() -> None:
    result = classify_error_text("error", "Traceback File evaluate_decompose.py Command failed with exit code 1")

    assert result["error_type"] == "script_orchestration"
    assert result["root_cause"] == "script_timeout_or_partial_output"


def test_build_diagnostic_uses_progress_context_when_status_is_truncated(tmp_path) -> None:
    status = tmp_path / "real_config_status.csv"
    comparison = tmp_path / "stage14_embedding_comparison.csv"
    progress = tmp_path / "progress.md"
    write_csv(
        status,
        "suite,status,output_file,embedding_provider,embedding_model_name,embedding_dimension,chat_provider,chat_model_name,skipped_reason,error_summary,notes\n"
        "decompose,error,out.csv,openai-compatible,jina,1024,openai-compatible,mimo,,Traceback truncated,Command failed\n",
    )
    write_csv(
        comparison,
        "config_name,suite,status,passed,total,failed,pass_rate,embedding_provider,embedding_model_name,embedding_dimension,chat_provider,chat_model_name,source_file,failed_queries,skipped_reason,notes\n"
        "real_config,decompose,error,0,0,0,,openai-compatible,jina,1024,openai-compatible,mimo,out.csv,,Traceback truncated,\n",
    )
    progress.write_text("阶段 15 real decompose SSL EOF: SSL: UNEXPECTED_EOF_WHILE_READING\n", encoding="utf-8")

    diagnostic = build_decompose_diagnostic(
        real_status_path=status,
        comparison_path=comparison,
        progress_doc_path=progress,
        retry_results_path=tmp_path / "missing_retry_results.csv",
    )

    assert diagnostic.root_cause == "provider_network_ssl_eof"
    assert diagnostic.status_after == "classified_external_provider_error"


def test_build_diagnostic_marks_successful_retry_not_blocking(tmp_path) -> None:
    status = tmp_path / "real_config_status.csv"
    comparison = tmp_path / "stage14_embedding_comparison.csv"
    progress = tmp_path / "progress.md"
    retry = tmp_path / "stage16_decompose_real_retry_results.csv"
    write_csv(
        status,
        "suite,status,output_file,embedding_provider,embedding_model_name,embedding_dimension,chat_provider,chat_model_name,skipped_reason,error_summary,notes\n"
        "decompose,error,out.csv,openai-compatible,jina,1024,openai-compatible,mimo,,SSL EOF,Command failed\n",
    )
    write_csv(comparison, "config_name,suite,status\nreal_config,decompose,error\n")
    progress.write_text("阶段 15 real decompose SSL EOF\n", encoding="utf-8")
    write_csv(
        retry,
        "query_id,passed,decompose_applied,brain_refused,source_hit_matched\n"
        "q1,true,true,false,true\n"
        "q2,true,false,true,true\n",
    )

    diagnostic = build_decompose_diagnostic(
        real_status_path=status,
        comparison_path=comparison,
        progress_doc_path=progress,
        retry_results_path=retry,
    )

    assert diagnostic.status_after == "retry_completed"
    assert diagnostic.root_cause == "embedding_header_compatibility_and_chat_timeout"
    assert diagnostic.blocking_status == "not_blocking"


def test_write_diagnostics_outputs_expected_schema(tmp_path) -> None:
    status = tmp_path / "real_config_status.csv"
    comparison = tmp_path / "stage14_embedding_comparison.csv"
    progress = tmp_path / "progress.md"
    write_csv(
        status,
        "suite,status,output_file,embedding_provider,embedding_model_name,embedding_dimension,chat_provider,chat_model_name,skipped_reason,error_summary,notes\n"
        "decompose,skipped,out.csv,openai-compatible,jina,1024,openai-compatible,mimo,Real configuration appears complete but --run-real was not passed,,\n",
    )
    write_csv(comparison, "config_name,suite,status\nreal_config,decompose,skipped\n")
    progress.write_text("", encoding="utf-8")
    diagnostic = build_decompose_diagnostic(
        real_status_path=status,
        comparison_path=comparison,
        progress_doc_path=progress,
        retry_results_path=tmp_path / "missing_retry_results.csv",
    )
    out = tmp_path / "diagnostics.csv"

    write_diagnostics(out, [diagnostic])

    content = out.read_text(encoding="utf-8")
    assert "diagnostic_id,suite,status_before,status_after" in content
    assert "stage16_decompose_001,decompose,skipped" in content


def test_sanitize_evidence_redacts_token_like_values() -> None:
    sanitized = sanitize_evidence("Bearer abc.secret sk-1234567890 tp-1234567890")

    assert "sk-1234567890" not in sanitized
    assert "tp-1234567890" not in sanitized
    assert "Bearer [REDACTED]" in sanitized


def test_extract_progress_context_prioritizes_ssl_eof_lines() -> None:
    context = extract_progress_decompose_context(
        "old decompose design line\n"
        "阶段 15 real decompose SSL EOF: SSL: UNEXPECTED_EOF_WHILE_READING\n"
        "another decompose line\n"
    )

    assert context.splitlines()[0].startswith("阶段 15 real decompose SSL EOF")

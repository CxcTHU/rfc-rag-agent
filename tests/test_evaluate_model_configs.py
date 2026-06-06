from pathlib import Path

from app.core.config import Settings
from scripts.evaluate_model_configs import (
    build_model_config_summaries,
    format_pass_rate,
    real_config_skipped_reason,
    summarize_passed_csv,
    write_results,
)


def write_passed_csv(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "query_id,passed\n"
        + "\n".join(f"q{index},{value}" for index, value in enumerate(values, start=1))
        + "\n",
        encoding="utf-8",
    )


def seed_suite_results(directory: Path) -> None:
    for filename in [
        "keyword_results.csv",
        "vector_results.csv",
        "hybrid_results.csv",
        "chat_results.csv",
        "agent_results.csv",
        "brain_workflow_results.csv",
    ]:
        write_passed_csv(directory / filename, ["yes", "no", "yes"])


def test_summarize_passed_csv_counts_yes_values(tmp_path) -> None:
    path = tmp_path / "results.csv"
    write_passed_csv(path, ["yes", "no", "true", "0"])

    assert summarize_passed_csv(path) == (2, 4)


def test_format_pass_rate_handles_completed_and_empty_suites() -> None:
    assert format_pass_rate(3, 4) == "0.750"
    assert format_pass_rate(0, 0) == ""


def test_build_model_config_summaries_outputs_deterministic_baseline(tmp_path) -> None:
    seed_suite_results(tmp_path)
    settings = Settings()

    results = build_model_config_summaries(settings=settings, evaluation_dir=tmp_path)

    assert len(results) == 6
    assert {result.suite for result in results} == {
        "keyword",
        "vector",
        "hybrid",
        "chat",
        "agent",
        "brain_workflow",
    }
    assert all(result.config_name == "deterministic_baseline" for result in results)
    assert all(result.status == "completed" for result in results)
    assert all(result.passed == 2 and result.total == 3 for result in results)


def test_build_model_config_summaries_skips_incomplete_real_config(tmp_path) -> None:
    seed_suite_results(tmp_path)
    settings = Settings(
        chat_model_provider="",
        chat_model_name="",
        chat_model_api_key="",
        chat_model_base_url="",
        embedding_provider="",
        embedding_model_name="",
        embedding_api_key="",
        embedding_base_url="",
        embedding_dimension=0,
    )

    results = build_model_config_summaries(
        settings=settings,
        evaluation_dir=tmp_path,
        include_real_config=True,
    )

    real_results = [result for result in results if result.config_name == "real_config"]
    assert len(real_results) == 6
    assert all(result.status == "skipped" for result in real_results)
    assert "CHAT_MODEL_PROVIDER" in real_results[0].skipped_reason
    assert "EMBEDDING_DIMENSION" in real_results[0].skipped_reason


def test_build_model_config_summaries_reads_real_results_when_configured(tmp_path) -> None:
    deterministic_dir = tmp_path / "deterministic"
    real_dir = tmp_path / "real"
    seed_suite_results(deterministic_dir)
    seed_suite_results(real_dir)
    settings = Settings(
        chat_model_provider="openai-compatible",
        chat_model_name="chat-test",
        chat_model_api_key="chat-key",
        chat_model_base_url="https://chat.example/v1",
        embedding_provider="openai-compatible",
        embedding_model_name="embedding-test",
        embedding_api_key="embedding-key",
        embedding_base_url="https://embedding.example/v1",
        embedding_dimension=3,
    )

    results = build_model_config_summaries(
        settings=settings,
        evaluation_dir=deterministic_dir,
        include_real_config=True,
        real_results_dir=real_dir,
    )

    real_results = [result for result in results if result.config_name == "real_config"]
    assert len(real_results) == 6
    assert all(result.status == "completed" for result in real_results)
    assert all(result.embedding_model_name == "embedding-test" for result in real_results)
    assert all(result.embedding_dimension == 3 for result in real_results)


def test_real_config_skipped_reason_is_empty_when_real_settings_complete() -> None:
    settings = Settings(
        chat_model_provider="openai-compatible",
        chat_model_name="chat-test",
        chat_model_api_key="chat-key",
        chat_model_base_url="https://chat.example/v1",
        embedding_provider="openai-compatible",
        embedding_model_name="embedding-test",
        embedding_api_key="embedding-key",
        embedding_base_url="https://embedding.example/v1",
        embedding_dimension=3,
    )

    assert real_config_skipped_reason(settings) == ""


def test_write_results_outputs_explorable_csv(tmp_path) -> None:
    seed_suite_results(tmp_path)
    results = build_model_config_summaries(settings=Settings(), evaluation_dir=tmp_path)
    out = tmp_path / "model_config_results.csv"

    write_results(out, results)

    content = out.read_text(encoding="utf-8")
    assert "config_name,suite,status,passed,total,failed,pass_rate" in content
    assert "deterministic_baseline,keyword,completed,2,3,1,0.667" in content

from pathlib import Path

from app.core.config import Settings
from scripts.evaluate_stage14_embedding_comparison import (
    build_embedding_comparison,
    real_embedding_skipped_reason,
    summarize_passed_csv,
    write_results,
)


def write_passed_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "query_id,config_name,passed\n"
        + "\n".join(f"{query_id},{config_name},{passed}" for query_id, config_name, passed in rows)
        + "\n",
        encoding="utf-8",
    )


def seed_stage14_suite_results(directory: Path) -> None:
    for filename in [
        "vector_results.csv",
        "hybrid_results.csv",
        "user_question_results.csv",
        "stage13_decompose_results.csv",
        "chat_results.csv",
        "agent_results.csv",
        "brain_workflow_results.csv",
    ]:
        write_passed_csv(
            directory / filename,
            [("q1", "default", "yes"), ("q2", "default", "no"), ("q3", "default", "true")],
        )


def test_summarize_passed_csv_tracks_failed_queries(tmp_path) -> None:
    path = tmp_path / "vector_results.csv"
    write_passed_csv(path, [("q1", "vector", "yes"), ("q2", "vector", "no")])

    assert summarize_passed_csv(path) == (1, 2, ("vector:q2",))


def test_build_embedding_comparison_outputs_deterministic_baseline(tmp_path) -> None:
    seed_stage14_suite_results(tmp_path)

    results = build_embedding_comparison(settings=Settings(), evaluation_dir=tmp_path)

    assert len(results) == 7
    assert {result.suite for result in results} == {
        "vector",
        "hybrid",
        "user_questions",
        "decompose",
        "chat",
        "agent",
        "brain_workflow",
    }
    assert all(result.config_name == "deterministic_baseline" for result in results)
    assert all(result.status == "completed" for result in results)
    assert all(result.failed_queries == ("default:q2",) for result in results)


def test_build_embedding_comparison_skips_incomplete_real_embedding(tmp_path) -> None:
    seed_stage14_suite_results(tmp_path)

    results = build_embedding_comparison(
        settings=Settings(
            embedding_provider="",
            embedding_model_name="",
            embedding_api_key="",
            embedding_base_url="",
            embedding_dimension=0,
        ),
        evaluation_dir=tmp_path,
        include_real_config=True,
    )

    real_results = [result for result in results if result.config_name == "real_config"]
    assert len(real_results) == 7
    assert all(result.status == "skipped" for result in real_results)
    assert "EMBEDDING_PROVIDER" in real_results[0].skipped_reason
    assert "EMBEDDING_DIMENSION" in real_results[0].skipped_reason


def test_build_embedding_comparison_reads_real_results_when_configured(tmp_path) -> None:
    deterministic_dir = tmp_path / "deterministic"
    real_dir = tmp_path / "real"
    seed_stage14_suite_results(deterministic_dir)
    seed_stage14_suite_results(real_dir)

    results = build_embedding_comparison(
        settings=Settings(
            embedding_provider="openai-compatible",
            embedding_model_name="jina-embeddings-v3",
            embedding_api_key="embedding-key",
            embedding_base_url="https://embedding.example/v1",
            embedding_dimension=1024,
        ),
        evaluation_dir=deterministic_dir,
        include_real_config=True,
        real_results_dir=real_dir,
    )

    real_results = [result for result in results if result.config_name == "real_config"]
    assert len(real_results) == 7
    assert all(result.status == "completed" for result in real_results)
    assert all(result.embedding_model_name == "jina-embeddings-v3" for result in real_results)
    assert all(result.embedding_dimension == 1024 for result in real_results)


def test_real_embedding_skipped_reason_is_empty_when_embedding_settings_complete() -> None:
    settings = Settings(
        embedding_provider="openai-compatible",
        embedding_model_name="embedding-test",
        embedding_api_key="embedding-key",
        embedding_base_url="https://embedding.example/v1",
        embedding_dimension=3,
    )

    assert real_embedding_skipped_reason(settings) == ""


def test_write_results_outputs_stage14_embedding_comparison_csv(tmp_path) -> None:
    seed_stage14_suite_results(tmp_path)
    results = build_embedding_comparison(settings=Settings(), evaluation_dir=tmp_path)
    out = tmp_path / "stage14_embedding_comparison.csv"

    write_results(out, results)

    content = out.read_text(encoding="utf-8")
    assert "config_name,suite,status,passed,total,failed,pass_rate" in content
    assert "deterministic_baseline,vector,completed,2,3,1,0.667" in content
    assert "default:q2" in content

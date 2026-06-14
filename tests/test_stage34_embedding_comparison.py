from pathlib import Path

from scripts.evaluate_stage33_embedding_migration import read_dotenv_value, summarize


def test_stage34_embedding_comparison_reads_provider_specific_dotenv_without_logging_secret(
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# local provider settings",
                "JINA_API_KEY='secret-value'",
                'JINA_BASE_URL="https://api.jina.ai/v1"',
                "PARATERA_API_KEY=glm-secret",
            ]
        ),
        encoding="utf-8",
    )

    assert read_dotenv_value(env_file, "JINA_API_KEY") == "secret-value"
    assert read_dotenv_value(env_file, "JINA_BASE_URL") == "https://api.jina.ai/v1"
    assert read_dotenv_value(env_file, "PARATERA_API_KEY") == "glm-secret"
    assert read_dotenv_value(Path("missing.env"), "JINA_API_KEY") == ""


def test_stage34_embedding_comparison_completed_summary_uses_stage34_decision_candidates() -> None:
    rows = []
    for candidate, provider, model, dimension, p3, p5, coverage in [
        ("jina_baseline", "jina", "jina-embeddings-v3", "1024", "false", "true", "0.700"),
        ("glm_candidate", "paratera", "GLM-Embedding-3", "2048", "true", "true", "0.650"),
    ]:
        rows.append(
            {
                "query_id": "q1",
                "category": "quality",
                "expected_refused": "false",
                "candidate": candidate,
                "provider": provider,
                "model_name": model,
                "dimension": dimension,
                "top_k": "5",
                "precision_at_1": "false",
                "precision_at_3": p3,
                "precision_at_5": p5,
                "hit_at_5": p5,
                "coverage_ratio": coverage,
                "source_type_distribution": "",
                "top1_source_type": "",
                "top1_document_title": "",
                "latency_ms": "1000.00",
                "status": "completed",
                "error": "",
            }
        )

    summaries = summarize(rows)

    assert {summary["decision"] for summary in summaries} == {"keep_glm"}
    assert all("quota sustainability risk" in summary["next_action"] for summary in summaries)

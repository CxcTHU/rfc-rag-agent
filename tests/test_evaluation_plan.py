from pathlib import Path


def test_stage_6_evaluation_plan_documents_core_metrics_and_inputs() -> None:
    plan = Path("docs/evaluation_plan.md").read_text(encoding="utf-8")

    for metric in [
        "Recall@K",
        "Citation Accuracy",
        "Faithfulness",
        "Answer Coverage",
        "Refusal Quality",
    ]:
        assert metric in plan

    for path in [
        "data/evaluation/keyword_queries.csv",
        "data/evaluation/keyword_results.csv",
        "data/evaluation/vector_results.csv",
        "data/evaluation/chat_queries.csv",
        "data/evaluation/chat_results.csv",
        "data/evaluation/retrieval_error_cases.csv",
    ]:
        assert path in plan


def test_stage_6_evaluation_plan_keeps_optimization_comparable() -> None:
    plan = Path("docs/evaluation_plan.md").read_text(encoding="utf-8")

    assert "keyword baseline" in plan
    assert "vector baseline" in plan
    assert "hybrid search" in plan
    assert "优化前后指标" in plan

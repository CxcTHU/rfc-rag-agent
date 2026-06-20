from scripts.evaluate_phase46_image_retrieval import (
    DEFAULT_QUESTIONS_CSV,
    EvaluationQuestion,
    read_questions,
    run_deterministic_evaluation,
    summarize_records,
)


def test_phase46_image_retrieval_questions_cover_required_categories() -> None:
    questions = read_questions(DEFAULT_QUESTIONS_CSV)

    categories = {question.category for question in questions}
    assert len(questions) >= 30
    assert categories == {"must_have_image", "image_helpful", "text_only", "no_image"}
    assert sum(1 for question in questions if question.expected_has_image) >= 12
    assert sum(1 for question in questions if not question.expected_has_image) >= 12


def test_phase46_image_retrieval_evaluation_runs_without_real_api(tmp_path) -> None:
    questions = [
        EvaluationQuestion(
            query_id="must_fixture",
            question="Show the interface microstructure figure.",
            category="must_have_image",
            expected_has_image=True,
            expected_image_keywords=["interface", "microstructure"],
            notes="positive fixture",
        ),
        EvaluationQuestion(
            query_id="help_fixture",
            question="Explain thermal control with a temperature figure if useful.",
            category="image_helpful",
            expected_has_image=True,
            expected_image_keywords=["thermal", "temperature"],
            notes="positive fixture",
        ),
        EvaluationQuestion(
            query_id="text_fixture",
            question="Define rock-filled concrete without figures.",
            category="text_only",
            expected_has_image=False,
            expected_image_keywords=[],
            notes="negative fixture",
        ),
        EvaluationQuestion(
            query_id="none_fixture",
            question="Write a recipe for tomato eggs.",
            category="no_image",
            expected_has_image=False,
            expected_image_keywords=[],
            notes="negative fixture",
        ),
    ]

    records = run_deterministic_evaluation(
        questions=questions,
        database_url=f"sqlite:///{(tmp_path / 'eval.sqlite').as_posix()}",
        top_k=4,
    )
    summary = summarize_records(records, elapsed_seconds=0.0)

    assert summary["image_recall"] == "1.0000"
    assert summary["image_suppression"] == "1.0000"
    assert summary["image_quality_rate"] == "1.0000"
    assert summary["caption_coverage"] == "1.0000"
    assert summary["page_number_coverage"] == "1.0000"

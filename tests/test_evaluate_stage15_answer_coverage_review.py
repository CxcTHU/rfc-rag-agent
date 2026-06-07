from pathlib import Path

from scripts.evaluate_stage15_answer_coverage_review import (
    answer_covers_expected_points,
    build_stage15_reviews,
    score_real_row,
    summarize_answer,
    write_results,
)


def write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed_stage14_review(path: Path) -> None:
    write_csv(
        path,
        "review_id,query_id,config_name,question,expected_answer_points,answer,evidence_titles,"
        "evidence_source_ids,faithfulness,answer_coverage,citation_quality,risk_level,review_method,"
        "decompose_applied,provenance_summary,skipped_reason,recommendation,notes\n"
        "stage14_det_001,q1,default_hybrid,What is RFC?,Explain filling quality,Deterministic,"
        "Source A,1,pass,review,pass,medium,deterministic_rule_review,yes,prov,,review,note\n"
        "stage14_det_002,q2,default_hybrid,Unsupported?,Should refuse,Refuse,"
        ",,pass,pass,pass,low,deterministic_rule_review,no,,,,note\n"
        "stage14_real_skipped_001,q1,real_config,What is RFC?,Explain filling quality,"
        ",,,skipped,skipped,skipped,skipped,real_model_review,,,,note\n",
    )


def seed_real_user_results(path: Path) -> None:
    write_csv(
        path,
        "config_name,query_id,question,language_type,passed,returned_answer,expected_refused,refused,"
        "refusal_matched,expected_source_hit,actual_source_hit,source_hit_matched,source_count,citations,"
        "citations_valid,forbidden_terms_absent,expected_answer_points,configured_retrieval_mode,"
        "actual_retrieval_mode,top_k,workflow_steps,workflow_succeeded,model_provider,model_name,"
        "answer,top_source_titles,failed_reason,error,notes\n"
        "default_hybrid,q1,What is RFC?,en,yes,yes,no,no,yes,yes,yes,yes,1,1,yes,yes,"
        "Explain filling quality,hybrid,hybrid,5,steps,yes,openai-compatible,mimo,"
        "The answer explains filling quality using cited evidence [1].,Source A,,,note\n"
        "default_hybrid,q3,Timeout?,en,no,no,no,no,no,yes,no,no,0,,yes,yes,"
        "Explain timeout,hybrid,none,5,,no,openai-compatible,mimo,,,"
        "error,The read operation timed out,note\n",
    )


def test_score_real_row_marks_passing_real_answer_as_low_risk_components() -> None:
    row = {
        "expected_refused": "no",
        "refused": "no",
        "returned_answer": "yes",
        "workflow_succeeded": "yes",
        "source_hit_matched": "yes",
        "citations_valid": "yes",
        "forbidden_terms_absent": "yes",
        "answer": "This explains filling quality.",
        "error": "",
    }

    assert score_real_row(row, "Explain filling quality") == ("pass", "pass", "pass")


def test_score_real_row_marks_errors_as_high_risk_components() -> None:
    row = {
        "expected_refused": "no",
        "refused": "no",
        "returned_answer": "no",
        "workflow_succeeded": "no",
        "source_hit_matched": "no",
        "citations_valid": "yes",
        "forbidden_terms_absent": "yes",
        "answer": "",
        "error": "timeout",
    }

    assert score_real_row(row, "Explain timeout") == ("fail", "fail", "review")


def test_build_stage15_reviews_uses_real_default_hybrid_rows(tmp_path) -> None:
    stage14 = tmp_path / "stage14_answer_coverage_review.csv"
    real = tmp_path / "user_question_results.csv"
    seed_stage14_review(stage14)
    seed_real_user_results(real)

    reviews = build_stage15_reviews(stage14_review_path=stage14, real_user_results_path=real)

    assert len(reviews) == 1
    assert reviews[0].source_review_id == "stage14_det_001"
    assert reviews[0].config_name == "real_config"
    assert reviews[0].review_method == "real_model_summary"
    assert reviews[0].risk_level == "low"
    assert "filling quality" in reviews[0].answer_summary


def test_build_stage15_reviews_records_missing_real_answer_as_skipped(tmp_path) -> None:
    stage14 = tmp_path / "stage14_answer_coverage_review.csv"
    real = tmp_path / "missing.csv"
    seed_stage14_review(stage14)

    reviews = build_stage15_reviews(stage14_review_path=stage14, real_user_results_path=real)

    assert len(reviews) == 1
    assert reviews[0].risk_level == "skipped"
    assert "Missing real default_hybrid result" in reviews[0].skipped_reason


def test_write_results_outputs_stage15_review_csv(tmp_path) -> None:
    stage14 = tmp_path / "stage14_answer_coverage_review.csv"
    real = tmp_path / "user_question_results.csv"
    seed_stage14_review(stage14)
    seed_real_user_results(real)
    reviews = build_stage15_reviews(stage14_review_path=stage14, real_user_results_path=real)
    out = tmp_path / "stage15_answer_coverage_review.csv"

    write_results(out, reviews)

    content = out.read_text(encoding="utf-8")
    assert "review_id,source_review_id,query_id,config_name" in content
    assert "faithfulness,answer_coverage,citation_quality" in content
    assert "stage15_review_001,stage14_det_001,q1,real_config" in content


def test_answer_summary_is_bounded() -> None:
    summary = summarize_answer("word " * 300, limit=60)

    assert len(summary) <= 60
    assert summary.endswith("...")


def test_answer_covers_expected_points_uses_meaningful_terms() -> None:
    assert answer_covers_expected_points("This covers filling quality and detection.", "Explain filling quality")

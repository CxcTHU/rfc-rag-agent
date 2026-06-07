from pathlib import Path

from app.core.config import Settings
from scripts.evaluate_stage14_answer_coverage import (
    build_answer_coverage_reviews,
    real_chat_skipped_reason,
    score_row,
    write_results,
)


def write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed_questions(path: Path) -> None:
    write_csv(
        path,
        "query_id,question,language_type,top_k,retrieval_mode,expected_source_hit,expected_refused,"
        "expected_source_title_terms,expected_source_content_terms,expected_answer_points,forbidden_answer_terms,notes\n"
        "q1,What is RFC?,en,5,hybrid,yes,no,Rock-filled,concrete,Explain RFC,,note one\n"
        "q2,zqxjvblorptasticprotocol,unsupported,5,hybrid,no,yes,,,,Should refuse,hallucination,note two\n",
    )


def seed_user_results(path: Path) -> None:
    write_csv(
        path,
        "config_name,query_id,question,language_type,passed,returned_answer,expected_refused,refused,"
        "refusal_matched,expected_source_hit,actual_source_hit,source_hit_matched,source_count,citations,"
        "citations_valid,forbidden_terms_absent,expected_answer_points,configured_retrieval_mode,"
        "actual_retrieval_mode,top_k,workflow_steps,workflow_succeeded,model_provider,model_name,"
        "answer,top_source_titles,failed_reason,error,notes\n"
        "default_hybrid,q1,What is RFC?,en,yes,yes,no,no,yes,yes,yes,yes,1,1,yes,yes,"
        "Explain RFC,hybrid,hybrid,5,steps,yes,deterministic,rule-based-chat-v1,"
        "Answer [1],Rock-filled Concrete,,,note one\n"
        "default_hybrid,q2,zqxjvblorptasticprotocol,unsupported,yes,yes,yes,yes,yes,no,no,yes,0,,yes,yes,"
        "Should refuse,hybrid,none,5,steps,yes,deterministic,rule-based-chat-v1,"
        "Refuse,,,,note two\n"
        "vector_only,q1,What is RFC?,en,no,yes,no,no,yes,yes,no,no,1,1,yes,yes,"
        "Explain RFC,vector,vector,5,steps,yes,deterministic,rule-based-chat-v1,"
        "Answer [1],Wrong Source,source_hit_mismatch,,note one\n",
    )


def seed_decompose(path: Path) -> None:
    write_csv(
        path,
        "query_id,decompose_applied,sub_queries,deduplicated_count,provenance_present,rerank_explanations\n"
        "q1,yes,sub one || sub two,3,yes,topic_terms=rfc; final_score=1.2\n",
    )


def test_score_row_marks_deterministic_source_hit_as_review() -> None:
    row = {
        "expected_refused": "no",
        "refused": "no",
        "returned_answer": "yes",
        "source_hit_matched": "yes",
        "citations_valid": "yes",
        "forbidden_terms_absent": "yes",
        "workflow_succeeded": "yes",
        "model_provider": "deterministic",
    }

    assert score_row(row) == ("pass", "review", "pass")


def test_build_answer_coverage_reviews_outputs_default_hybrid_rows(tmp_path) -> None:
    questions = tmp_path / "user_questions.csv"
    user_results = tmp_path / "user_question_results.csv"
    decompose = tmp_path / "stage13_decompose_results.csv"
    seed_questions(questions)
    seed_user_results(user_results)
    seed_decompose(decompose)

    reviews = build_answer_coverage_reviews(
        user_results_path=user_results,
        questions_path=questions,
        decompose_results_path=decompose,
    )

    assert len(reviews) == 2
    assert reviews[0].answer_coverage == "review"
    assert reviews[0].risk_level == "medium"
    assert reviews[0].decompose_applied == "yes"
    assert "sub one" in reviews[0].provenance_summary
    assert reviews[1].answer_coverage == "pass"
    assert reviews[1].risk_level == "low"


def test_build_answer_coverage_reviews_can_include_vector_failures(tmp_path) -> None:
    questions = tmp_path / "user_questions.csv"
    user_results = tmp_path / "user_question_results.csv"
    seed_questions(questions)
    seed_user_results(user_results)

    reviews = build_answer_coverage_reviews(
        user_results_path=user_results,
        questions_path=questions,
        decompose_results_path=None,
        include_configs=("vector_only",),
    )

    assert len(reviews) == 1
    assert reviews[0].answer_coverage == "fail"
    assert reviews[0].risk_level == "high"


def test_build_answer_coverage_reviews_skips_missing_real_chat_config(tmp_path) -> None:
    questions = tmp_path / "user_questions.csv"
    user_results = tmp_path / "user_question_results.csv"
    seed_questions(questions)
    seed_user_results(user_results)

    reviews = build_answer_coverage_reviews(
        user_results_path=user_results,
        questions_path=questions,
        decompose_results_path=None,
        include_real_config=True,
        settings=Settings(
            chat_model_provider="",
            chat_model_name="",
            chat_model_api_key="",
            chat_model_base_url="",
        ),
    )

    real_reviews = [review for review in reviews if review.config_name == "real_config"]
    assert len(real_reviews) == 2
    assert all(review.answer_coverage == "skipped" for review in real_reviews)
    assert "CHAT_MODEL_PROVIDER" in real_reviews[0].skipped_reason


def test_real_chat_skipped_reason_is_empty_when_chat_settings_complete() -> None:
    settings = Settings(
        chat_model_provider="openai-compatible",
        chat_model_name="chat-test",
        chat_model_api_key="chat-key",
        chat_model_base_url="https://chat.example/v1",
    )

    assert real_chat_skipped_reason(settings) == ""


def test_write_results_outputs_answer_coverage_review_csv(tmp_path) -> None:
    questions = tmp_path / "user_questions.csv"
    user_results = tmp_path / "user_question_results.csv"
    seed_questions(questions)
    seed_user_results(user_results)
    reviews = build_answer_coverage_reviews(user_results_path=user_results, questions_path=questions)
    out = tmp_path / "stage14_answer_coverage_review.csv"

    write_results(out, reviews)

    content = out.read_text(encoding="utf-8")
    assert "review_id,query_id,config_name,question,expected_answer_points" in content
    assert "faithfulness,answer_coverage,citation_quality" in content
    assert "stage14_det_001,q1,default_hybrid" in content

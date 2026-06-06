import csv
from pathlib import Path


USER_QUESTIONS_PATH = Path("data/evaluation/user_questions.csv")


REQUIRED_FIELDS = {
    "query_id",
    "question",
    "language_type",
    "top_k",
    "retrieval_mode",
    "expected_source_hit",
    "expected_refused",
    "expected_source_title_terms",
    "expected_source_content_terms",
    "expected_answer_points",
    "forbidden_answer_terms",
    "notes",
}


def read_user_questions() -> list[dict[str, str]]:
    with USER_QUESTIONS_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        assert set(reader.fieldnames or []) == REQUIRED_FIELDS
        return list(reader)


def test_stage_11_user_questions_schema_and_required_fields() -> None:
    rows = read_user_questions()

    assert len(rows) >= 10
    for row in rows:
        assert row["query_id"].strip()
        assert row["question"].strip()
        assert row["language_type"].strip()
        assert row["top_k"].isdigit()
        assert row["retrieval_mode"] in {"auto", "keyword", "vector", "hybrid"}
        assert row["expected_source_hit"] in {"yes", "no"}
        assert row["expected_refused"] in {"yes", "no"}
        assert row["notes"].strip()


def test_stage_11_user_questions_cover_required_language_types() -> None:
    rows = read_user_questions()
    language_types = {row["language_type"] for row in rows}

    assert {
        "zh_colloquial",
        "en",
        "mixed",
        "engineering_cn",
        "unsupported",
    }.issubset(language_types)


def test_stage_11_user_questions_record_answer_points_and_refusal_boundary() -> None:
    rows = read_user_questions()
    unsupported_rows = [row for row in rows if row["expected_refused"] == "yes"]
    supported_rows = [row for row in rows if row["expected_refused"] == "no"]

    assert unsupported_rows
    assert all(row["expected_source_hit"] == "no" for row in unsupported_rows)
    assert all(row["forbidden_answer_terms"].strip() for row in unsupported_rows)
    assert all(row["expected_source_hit"] == "yes" for row in supported_rows)
    assert all(row["expected_answer_points"].strip() for row in supported_rows)

import csv
from pathlib import Path


QUERY_PATH = Path("data/evaluation/stage29_new_corpus_queries.csv")


def test_stage29_new_corpus_queries_cover_required_categories() -> None:
    with QUERY_PATH.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert 15 <= len(rows) <= 20
    assert {row["category"] for row in rows} == {"wikipedia", "standard", "web", "refusal"}
    assert sum(row["expected_refused"] == "true" for row in rows) >= 2


def test_stage29_new_corpus_queries_have_required_fields() -> None:
    with QUERY_PATH.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    allowed_source_types = {"wikipedia", "standard_document", "web_page", "any"}
    for row in rows:
        assert row["query_id"].startswith("stage29_")
        assert row["question"].strip()
        assert row["expected_source_type"] in allowed_source_types
        assert row["expected_answer_points"].strip()
        assert row["expected_refused"] in {"true", "false"}

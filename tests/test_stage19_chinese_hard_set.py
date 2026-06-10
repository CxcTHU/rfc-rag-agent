"""阶段 19 中文难评测集结构与设计文档断言测试。"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "evaluation" / "stage19_chinese_hard_queries.csv"
DESIGN_DOC_PATH = ROOT / "docs" / "stage19_chinese_analysis_retrieval_tuning.md"


REQUIRED_FIELDS = {
    "query_id",
    "query",
    "difficulty_type",
    "language_type",
    "expected_source_hit",
    "expected_source_type",
    "expected_refused",
    "expected_answer_points",
    "distractor_topics",
    "notes",
}

ALLOWED_DIFFICULTY = {"cross_passage", "confusable", "parameter_detail", "refusal"}
ALLOWED_SOURCE_TYPE = {
    "open_access_pdf",
    "institutional_access_pdf",
    "metadata_record",
    "any",
}
ALLOWED_REFUSED = {"true", "false"}


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def test_csv_exists():
    assert CSV_PATH.exists(), f"missing {CSV_PATH}"


def test_csv_schema():
    rows = load_rows()
    assert rows, "stage19 chinese hard queries CSV must not be empty"
    fieldnames = set(rows[0].keys())
    missing = REQUIRED_FIELDS - fieldnames
    assert not missing, f"missing fields: {sorted(missing)}"


def test_query_ids_unique():
    rows = load_rows()
    query_ids = [row["query_id"] for row in rows]
    assert len(query_ids) == len(set(query_ids)), "query_id must be unique"


def test_difficulty_values():
    rows = load_rows()
    for row in rows:
        assert row["difficulty_type"] in ALLOWED_DIFFICULTY, row


def test_expected_source_type_values():
    rows = load_rows()
    for row in rows:
        assert row["expected_source_type"] in ALLOWED_SOURCE_TYPE, row


def test_expected_refused_values():
    rows = load_rows()
    for row in rows:
        assert row["expected_refused"] in ALLOWED_REFUSED, row


def test_covers_all_four_difficulty_types():
    rows = load_rows()
    seen = {row["difficulty_type"] for row in rows}
    assert seen == ALLOWED_DIFFICULTY, f"must cover all 4 types; got {seen}"


def test_refusal_share_at_least_20_percent():
    rows = load_rows()
    refusal = sum(1 for row in rows if row["difficulty_type"] == "refusal")
    assert refusal / len(rows) >= 0.20, (
        f"refusal share must be >= 20%; got {refusal}/{len(rows)}"
    )


def test_refusal_rows_have_no_expected_keywords_and_no_answer_points():
    rows = load_rows()
    for row in rows:
        if row["difficulty_type"] == "refusal":
            assert row["expected_refused"] == "true", row
            assert not row["expected_source_hit"].strip(), row
            assert not row["expected_answer_points"].strip(), row


def test_non_refusal_rows_have_answer_points():
    rows = load_rows()
    for row in rows:
        if row["difficulty_type"] != "refusal":
            assert row["expected_refused"] == "false", row
            assert row["expected_answer_points"].strip(), row


def test_design_doc_exists_and_mentions_core_concepts():
    assert DESIGN_DOC_PATH.exists(), f"missing {DESIGN_DOC_PATH}"
    content = DESIGN_DOC_PATH.read_text(encoding="utf-8")
    for keyword in (
        "中文难评测集",
        "source_type_reweight",
        "deep_fulltext_top1_rate",
        "keep_existing_hybrid",
        "precision@1",
        "hybrid_fulltext_boost",
        "hybrid_metadata_demote",
        "hybrid_topic_anchor_strict",
    ):
        assert keyword in content, f"design doc missing keyword: {keyword}"

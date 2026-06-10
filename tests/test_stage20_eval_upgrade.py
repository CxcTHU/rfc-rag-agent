"""阶段 20 coverage_ratio 评测升级测试。"""

from __future__ import annotations

from scripts.evaluate_stage20_eval_upgrade import (
    ChineseHardQuery,
    RESULT_FIELDS,
    apply_decisions,
    coverage_ratio_for_points,
    real_embedding_missing_settings,
    skipped_rows,
)
from app.core.config import Settings


def test_coverage_ratio_matches_exact_and_chinese_fragments() -> None:
    coverage = coverage_ratio_for_points(
        ("自密实流动度", "堆石粒径级配", "不存在要点"),
        "自密实混凝土具有较高流动度；堆石粒径和级配会影响填充效果。",
    )

    assert coverage.ratio == 0.667
    assert coverage.covered_points == ("自密实流动度", "堆石粒径级配")
    assert coverage.missing_points == ("不存在要点",)


def test_coverage_ratio_empty_points_is_zero() -> None:
    coverage = coverage_ratio_for_points((), "anything")

    assert coverage.ratio == 0.0
    assert coverage.covered_points == ()
    assert coverage.missing_points == ()


def test_apply_decisions_uses_stage20_switch_gate() -> None:
    rows = [
        {"config": "hybrid_baseline", "decision": "", "next_action": ""},
        {"config": "candidate_good", "decision": "", "next_action": ""},
        {"config": "candidate_low_p1", "decision": "", "next_action": ""},
    ]
    summary_lookup = {
        "hybrid_baseline": {
            "precision_at_1": "0.400",
            "deep_fulltext_top1_rate": "0.000",
            "refusal_accuracy": "0.750",
            "decision": "",
            "next_action": "",
        },
        "candidate_good": {
            "precision_at_1": "0.500",
            "deep_fulltext_top1_rate": "0.333",
            "refusal_accuracy": "0.750",
            "decision": "",
            "next_action": "",
        },
        "candidate_low_p1": {
            "precision_at_1": "0.467",
            "deep_fulltext_top1_rate": "0.333",
            "refusal_accuracy": "0.750",
            "decision": "",
            "next_action": "",
        },
    }

    overall = apply_decisions(summary_lookup, rows)

    assert overall == "switch_default_to:candidate_good"
    assert summary_lookup["candidate_good"]["decision"] == "promote_candidate"
    assert summary_lookup["candidate_low_p1"]["decision"] == "keep_existing_hybrid"
    assert "delta_precision_at_1" in summary_lookup["candidate_low_p1"]["next_action"]


def test_stage20_results_table_contains_required_fields() -> None:
    for field in (
        "query_id",
        "config",
        "judge_mode",
        "hit",
        "coverage_ratio",
        "deep_fulltext_top1",
        "refusal_matched",
        "decision",
        "next_action",
    ):
        assert field in RESULT_FIELDS


def test_real_jina_missing_settings_are_recorded_as_skipped() -> None:
    settings = Settings(
        embedding_provider="",
        embedding_model_name="",
        embedding_api_key="",
        embedding_base_url="",
        embedding_dimension=0,
    )
    missing = real_embedding_missing_settings(settings)
    query = ChineseHardQuery(
        query_id="q1",
        query="堆石混凝土填充能力？",
        difficulty_type="cross_passage",
        language_type="zh",
        expected_source_hit=(),
        expected_source_type="any",
        expected_refused=False,
        expected_answer_points=("填充能力",),
        distractor_topics="",
        notes="",
    )

    rows = skipped_rows([query], missing, threshold=0.60)

    assert "EMBEDDING_PROVIDER" in missing
    assert rows
    assert {row["real_config_status"] for row in rows} == {"skipped"}
    assert {row["decision"] for row in rows} == {"real_jina_skipped"}
    assert all("missing real embedding settings" in row["error"] for row in rows)

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL_REVIEW_PATH = ROOT / "data" / "evaluation" / "stage17_retrieval_upgrade_manual_review.csv"

REQUIRED_FIELDS = [
    "query_id",
    "query",
    "baseline_hit",
    "upgraded_hit",
    "source_match",
    "rank_before",
    "rank_after",
    "review_decision",
    "retrieval_risk",
    "evidence",
    "acceptance_reason",
    "tuning_suggestion",
    "default_chain_recommendation",
    "notes",
]

ALLOWED_DECISIONS = {"acceptable", "needs_tuning", "regression", "defer"}
ALLOWED_RISK = {"low", "medium", "high"}
ALLOWED_DEFAULT_CHAIN = {"candidate_ok", "keep_default_hybrid"}


def _load_rows() -> list[dict[str, str]]:
    with MANUAL_REVIEW_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def test_manual_review_has_required_columns() -> None:
    with MANUAL_REVIEW_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        header = next(csv.reader(file))
    assert header == REQUIRED_FIELDS


def test_manual_review_covers_every_evaluated_query() -> None:
    results_path = ROOT / "data" / "evaluation" / "stage17_retrieval_upgrade_results.csv"
    with results_path.open("r", encoding="utf-8-sig", newline="") as file:
        evaluated_ids = {row["query_id"] for row in csv.DictReader(file)}
    reviewed_ids = {row["query_id"] for row in _load_rows()}
    assert evaluated_ids == reviewed_ids


def test_manual_review_uses_controlled_vocabulary() -> None:
    for row in _load_rows():
        assert row["review_decision"] in ALLOWED_DECISIONS
        assert row["retrieval_risk"] in ALLOWED_RISK
        assert row["default_chain_recommendation"] in ALLOWED_DEFAULT_CHAIN


def test_non_acceptable_rows_carry_evidence_and_tuning() -> None:
    # No unverified sample may be passed off as a clean accept: anything other than
    # "acceptable" must record concrete evidence and an explicit tuning suggestion.
    for row in _load_rows():
        if row["review_decision"] != "acceptable":
            assert row["evidence"].strip()
            assert row["tuning_suggestion"].strip()
            assert row["tuning_suggestion"].strip().lower() != "none"


def test_source_mismatch_rows_explain_the_swap() -> None:
    for row in _load_rows():
        if row["source_match"].strip().lower() == "no":
            assert row["evidence"].strip()
            assert row["acceptance_reason"].strip() or row["tuning_suggestion"].strip()


def test_known_rank_regression_is_flagged_for_tuning() -> None:
    # mesoscopic_modeling degraded from rank 2 to rank 7 in the upgraded retrieval;
    # the honest review must keep it as needs_tuning and block the default switch.
    rows = {row["query_id"]: row for row in _load_rows()}
    mesoscopic = rows["mesoscopic_modeling"]
    assert mesoscopic["review_decision"] == "needs_tuning"
    assert mesoscopic["default_chain_recommendation"] == "keep_default_hybrid"

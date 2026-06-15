from argparse import Namespace
from pathlib import Path

from scripts.judge_stage36_strategy_ab import (
    RESULT_FIELDS,
    STRATEGIES,
    Stage36JudgeQuery,
    load_stage36_queries,
    parse_bool,
    split_points,
    summarize,
    write_csv,
    build_rows,
    apply_runtime_fallbacks,
)


def test_stage36_query_loader_provides_at_least_20_real_questions() -> None:
    queries = load_stage36_queries(limit=20)

    assert len(queries) == 20
    assert all(query.query_id for query in queries)
    assert all(query.question for query in queries)


def test_stage36_judge_dry_run_builds_three_strategy_rows_per_query() -> None:
    args = Namespace(
        execute=False,
        judge_provider="judge",
        judge_model="judge-model",
        judge_base_url="",
        judge_api_key="",
        ab_answer_provider="openai-compatible",
        ab_answer_model="DeepSeek-V3.2-Thinking",
    )
    rows = build_rows(args, load_stage36_queries(limit=2))

    assert len(rows) == 2 * len(STRATEGIES)
    assert {row["strategy"] for row in rows} == set(STRATEGIES)
    assert {row["status"] for row in rows} == {"dry_run"}
    assert all(set(row) == set(RESULT_FIELDS) for row in rows)


def test_stage36_summary_marks_passing_and_review_required_strategies() -> None:
    rows = [
        {
            "strategy": "baseline",
            "status": "completed",
            "answer_coverage": "0.810",
            "citation_support": "0.820",
            "safety_leak_check": "0.900",
            "risk_level": "low",
        },
        {
            "strategy": "outline_first",
            "status": "completed",
            "answer_coverage": "0.700",
            "citation_support": "0.820",
            "safety_leak_check": "0.900",
            "risk_level": "medium",
        },
        {
            "strategy": "answer_provider_ab",
            "status": "dry_run",
            "answer_coverage": "",
            "citation_support": "",
            "safety_leak_check": "",
            "risk_level": "",
        },
    ]

    by_strategy = {row["strategy"]: row for row in summarize(rows)}

    assert by_strategy["baseline"]["judge_gate"] == "pass"
    assert by_strategy["outline_first"]["judge_gate"] == "review_required"
    assert by_strategy["answer_provider_ab"]["judge_gate"] == "not_run"


def test_stage36_judge_helpers_parse_expected_fields() -> None:
    assert parse_bool("yes")
    assert parse_bool("true")
    assert not parse_bool("no")
    assert split_points("a;b|c") == ("a", "b", "c")


def test_stage36_judge_csv_omits_raw_sensitive_content(tmp_path: Path) -> None:
    path = tmp_path / "judge.csv"
    query = Stage36JudgeQuery(
        query_id="q",
        question="What affects filling capacity?",
        expected_refused=False,
        expected_answer_points=("flowability",),
        category="test",
    )
    args = Namespace(
        execute=False,
        judge_provider="judge",
        judge_model="judge-model",
        judge_base_url="",
        judge_api_key="",
        ab_answer_provider="",
        ab_answer_model="DeepSeek-V3.2-Thinking",
    )
    rows = build_rows(args, [query])

    write_csv(path, RESULT_FIELDS, rows)
    text = path.read_text(encoding="utf-8")

    assert "raw_response" not in text
    assert "reasoning_content" not in text
    assert "Bearer " not in text


def test_stage36_judge_runtime_fallbacks_use_default_settings(monkeypatch) -> None:
    from scripts import judge_stage36_strategy_ab as module

    class FakeSettings:
        chat_model_provider = "openai-compatible"
        chat_model_name = "default-chat"
        chat_model_base_url = "https://example.test"
        chat_model_api_key = "secret"

    monkeypatch.setattr(module, "get_settings", lambda: FakeSettings())
    args = Namespace(
        judge_provider="",
        judge_model="",
        judge_base_url="",
        judge_api_key="",
        ab_answer_provider="",
        ab_answer_model="DeepSeek-V3.2-Thinking",
        ab_answer_base_url="",
        ab_answer_api_key="",
    )

    apply_runtime_fallbacks(args)

    assert args.judge_provider == "openai-compatible"
    assert args.judge_model == "default-chat"
    assert args.judge_base_url == "https://example.test"
    assert args.judge_api_key == "secret"
    assert args.ab_answer_provider == "openai-compatible"
    assert args.ab_answer_base_url == "https://example.test"
    assert args.ab_answer_api_key == "secret"

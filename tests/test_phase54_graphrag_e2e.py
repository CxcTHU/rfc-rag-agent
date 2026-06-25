import csv
from pathlib import Path
from types import SimpleNamespace

from app.core.config import get_settings
from scripts.evaluate_phase54_graphrag_e2e import (
    dry_run_rows,
    existing_result_rows,
    filter_cases,
    main,
    load_cases,
    preflight_report,
    resume_result_rows,
    summarize,
    write_csv,
)


def test_phase54_eval_cases_have_expected_coverage_and_are_sanitized() -> None:
    cases = load_cases(Path("data/evaluation/phase54_graphrag_eval_cases.csv"))

    assert len(cases) == 47
    assert sum(1 for case in cases if case.expected_graph_intent) >= 30
    assert sum(1 for case in cases if case.category == "negative_offtopic") == 5
    serialized = "\n".join(case.question for case in cases).casefold()
    for forbidden in ["api_key", "bearer", "authorization", "raw_response", "reasoning_content"]:
        assert forbidden not in serialized


def test_phase54_e2e_dry_run_outputs_sanitized_rows(tmp_path) -> None:
    cases = load_cases(Path("data/evaluation/phase54_graphrag_eval_cases.csv"))
    results, ablation = dry_run_rows(cases)
    summary = summarize(results)

    assert len(results) == 47
    assert len(ablation) == 47
    assert any(row["expected_graph_intent"] == "true" for row in results)
    assert any(row["graph_strategy"] == "graph_enhanced_search" for row in ablation)
    serialized = "\n".join(str(row) for row in [*results, *summary, *ablation]).casefold()
    for forbidden in ["chunk content", "raw_response", "reasoning_content", "authorization"]:
        assert forbidden not in serialized

    output_path = tmp_path / "phase54_summary.csv"
    write_csv(output_path, summary)
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["metric"] == "total_cases"
    assert rows[0]["value"] == "47"


def test_phase54_resume_reads_existing_csv_rows(tmp_path) -> None:
    output_path = tmp_path / "results.csv"
    rows = [
        {
            "case_id": "dry",
            "category": "standard_reference_chain",
            "status": "dry_run",
            "expected_graph_intent": "true",
            "expected_relation_focus": "standard_defines",
            "baseline_top_chunk_ids": "",
            "graph_top_chunk_ids": "",
            "baseline_top_title_hashes": "",
            "graph_top_title_hashes": "",
            "graph_candidate_chunk_count": "",
            "baseline_answer_chars": "",
            "graph_answer_chars": "",
            "baseline_accuracy": "",
            "graph_accuracy": "",
            "baseline_completeness": "",
            "graph_completeness": "",
            "baseline_citation_quality": "",
            "graph_citation_quality": "",
            "judge_reason": "",
            "error": "",
        },
        {
            "case_id": "retrieved",
            "category": "standard_reference_chain",
            "status": "retrieval_only",
            "expected_graph_intent": "true",
            "expected_relation_focus": "standard_defines",
            "baseline_top_chunk_ids": "1",
            "graph_top_chunk_ids": "1",
            "baseline_top_title_hashes": "abc",
            "graph_top_title_hashes": "abc",
            "graph_candidate_chunk_count": "1",
            "baseline_answer_chars": "",
            "graph_answer_chars": "",
            "baseline_accuracy": "",
            "graph_accuracy": "",
            "baseline_completeness": "",
            "graph_completeness": "",
            "baseline_citation_quality": "",
            "graph_citation_quality": "",
            "judge_reason": "",
            "error": "",
        },
        {
            "case_id": "answered",
            "category": "standard_reference_chain",
            "status": "answer_only",
            "expected_graph_intent": "true",
            "expected_relation_focus": "standard_defines",
            "baseline_top_chunk_ids": "2",
            "graph_top_chunk_ids": "2",
            "baseline_top_title_hashes": "def",
            "graph_top_title_hashes": "def",
            "graph_candidate_chunk_count": "1",
            "graph_used_match_count": "1",
            "baseline_answer_chars": "120",
            "graph_answer_chars": "140",
            "baseline_accuracy": "",
            "graph_accuracy": "",
            "baseline_completeness": "",
            "graph_completeness": "",
            "baseline_citation_quality": "",
            "graph_citation_quality": "",
            "judge_reason": "",
            "error": "",
        },
    ]
    write_csv(output_path, rows)

    loaded = existing_result_rows(output_path)
    resumable = resume_result_rows(output_path)

    assert [row["case_id"] for row in loaded] == ["dry", "retrieved", "answered"]
    assert [row["case_id"] for row in resumable] == ["retrieved", "answered"]

    summary = summarize(loaded)
    answer_only = next(row for row in summary if row["metric"] == "answer_only_rows")
    assert answer_only["value"] == "1"


def test_phase54_filter_cases_by_id_and_category() -> None:
    cases = load_cases(Path("data/evaluation/phase54_graphrag_eval_cases.csv"))

    by_category = filter_cases(cases, case_ids=[], categories=["negative_offtopic"])
    by_id = filter_cases(cases, case_ids=["p54_std_001"], categories=[])
    by_both = filter_cases(
        cases,
        case_ids=["p54_std_001", "p54_neg_001"],
        categories=["negative_offtopic"],
    )

    assert len(by_category) == 5
    assert [case.case_id for case in by_id] == ["p54_std_001"]
    assert [case.case_id for case in by_both] == ["p54_neg_001"]


def test_phase54_preflight_reports_judge_readiness(tmp_path) -> None:
    cases = load_cases(Path("data/evaluation/phase54_graphrag_eval_cases.csv"))
    graph_path = tmp_path / "domain_graph.json"
    graph_path.write_text("{}", encoding="utf-8")
    settings_without_judge = SimpleNamespace(
        chat_model_provider="openai-compatible",
        chat_model_name="answer-model",
        chat_model_api_key="answer-key",
        chat_model_base_url="https://example.invalid",
        judge_model_provider="openai-compatible",
        judge_model_name="judge-model",
        judge_model_api_key="",
        judge_model_base_url="https://example.invalid",
        embedding_provider="openai-compatible",
        embedding_model_name="embedding-model",
        embedding_api_key="embedding-key",
        embedding_base_url="https://example.invalid",
        reranking_enabled=False,
    )

    rows = preflight_report(cases, graph_path=graph_path, settings=settings_without_judge)
    by_check = {row["check"]: row for row in rows}

    assert by_check["judge_provider_configured"]["status"] == "fail"
    assert by_check["judge_model_provider_configured"]["status"] == "pass"
    assert by_check["judge_model_name_configured"]["status"] == "pass"
    assert by_check["judge_model_api_key_configured"]["status"] == "fail"
    assert by_check["judge_model_base_url_configured"]["status"] == "pass"
    assert by_check["judge_model_missing_fields"]["value"] == "JUDGE_MODEL_API_KEY"
    assert by_check["formal_judge_ready"]["status"] == "fail"

    settings_with_judge = SimpleNamespace(
        **{
            **settings_without_judge.__dict__,
            "judge_model_api_key": "judge-key",
        }
    )
    rows = preflight_report(cases, graph_path=graph_path, settings=settings_with_judge)
    by_check = {row["check"]: row for row in rows}

    assert by_check["judge_provider_configured"]["status"] == "pass"
    assert by_check["judge_model_provider_configured"]["status"] == "pass"
    assert by_check["judge_model_name_configured"]["status"] == "pass"
    assert by_check["judge_model_api_key_configured"]["status"] == "pass"
    assert by_check["judge_model_base_url_configured"]["status"] == "pass"
    assert by_check["judge_model_missing_fields"]["status"] == "pass"
    assert by_check["judge_model_missing_fields"]["value"] == ""
    assert by_check["formal_judge_ready"]["status"] == "pass"


def test_phase54_preflight_require_judge_returns_nonzero(tmp_path, monkeypatch) -> None:
    summary_path = tmp_path / "preflight.csv"
    for key in (
        "JUDGE_MODEL_PROVIDER",
        "JUDGE_MODEL_NAME",
        "JUDGE_MODEL_API_KEY",
        "JUDGE_MODEL_BASE_URL",
        "STAGE34_JUDGE_PROVIDER",
        "STAGE34_JUDGE_MODEL",
        "STAGE34_JUDGE_API_KEY",
        "STAGE34_JUDGE_BASE_URL",
    ):
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_phase54_graphrag_e2e.py",
            "--preflight",
            "--require-judge",
            "--summary-output",
            str(summary_path),
        ],
    )

    try:
        assert main() == 2
    finally:
        get_settings.cache_clear()
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        rows = {row["check"]: row for row in csv.DictReader(handle)}
    assert rows["formal_judge_ready"]["status"] == "fail"


def test_phase54_formal_gate_decision_pass_and_review_required() -> None:
    pass_rows = [
        phase54_scored_row(
            "g1",
            "standard_reference_chain",
            "true",
            baseline_accuracy="3",
            graph_accuracy="4",
            baseline_completeness="3",
            graph_completeness="4",
            baseline_citation_quality="3",
            graph_citation_quality="4",
            graph_candidate_chunk_count="10",
        ),
        phase54_scored_row(
            "o1",
            "ordinary_baseline",
            "false",
            baseline_accuracy="4",
            graph_accuracy="4",
            baseline_completeness="4",
            graph_completeness="4",
            baseline_citation_quality="4",
            graph_citation_quality="4",
            graph_candidate_chunk_count="0",
        ),
        phase54_scored_row(
            "n1",
            "negative_offtopic",
            "false",
            baseline_accuracy="5",
            graph_accuracy="5",
            baseline_completeness="5",
            graph_completeness="5",
            baseline_citation_quality="5",
            graph_citation_quality="5",
            graph_candidate_chunk_count="0",
        ),
    ]

    summary = {row["metric"]: row["value"] for row in summarize(pass_rows)}

    assert summary["graph_intent_accuracy_delta"] == "1.0000"
    assert summary["graph_intent_completeness_delta"] == "1.0000"
    assert summary["formal_judge_gate_decision"] == "pass"

    review_rows = [
        {
            **row,
            "graph_accuracy": row["baseline_accuracy"],
            "graph_completeness": row["baseline_completeness"],
        }
        for row in pass_rows
    ]
    review_rows[-1]["graph_candidate_chunk_count"] = "2"
    summary = {row["metric"]: row["value"] for row in summarize(review_rows)}

    assert summary["formal_judge_gate_decision"] == "review_required"
    assert "graph_intent_completeness_delta<0.3" in summary["formal_judge_gate_reason"]
    assert "negative_graph_false_positive_count>0" in summary["formal_judge_gate_reason"]


def test_phase54_formal_gate_pending_until_all_rows_completed() -> None:
    rows = [
        phase54_scored_row(
            "g1",
            "standard_reference_chain",
            "true",
            baseline_accuracy="3",
            graph_accuracy="4",
            baseline_completeness="3",
            graph_completeness="4",
            baseline_citation_quality="3",
            graph_citation_quality="4",
            graph_candidate_chunk_count="10",
        ),
        {
            **phase54_scored_row(
                "g2",
                "standard_reference_chain",
                "true",
                baseline_accuracy="3",
                graph_accuracy="4",
                baseline_completeness="3",
                graph_completeness="4",
                baseline_citation_quality="3",
                graph_citation_quality="4",
                graph_candidate_chunk_count="10",
            ),
            "status": "answer_only",
        },
    ]

    summary = {row["metric"]: row["value"] for row in summarize(rows)}

    assert summary["formal_judge_gate_decision"] == "pending"
    assert summary["formal_judge_gate_reason"] == "completed_judge_rows=1/2"


def test_phase54_formal_gate_pending_until_completed_rows_have_scores() -> None:
    rows = [
        phase54_scored_row(
            "g1",
            "standard_reference_chain",
            "true",
            baseline_accuracy="3",
            graph_accuracy="4",
            baseline_completeness="3",
            graph_completeness="4",
            baseline_citation_quality="3",
            graph_citation_quality="4",
            graph_candidate_chunk_count="10",
        ),
        phase54_scored_row(
            "g2",
            "standard_reference_chain",
            "true",
            baseline_accuracy="",
            graph_accuracy="4",
            baseline_completeness="3",
            graph_completeness="4",
            baseline_citation_quality="3",
            graph_citation_quality="4",
            graph_candidate_chunk_count="10",
        ),
    ]

    summary = {row["metric"]: row["value"] for row in summarize(rows)}

    assert summary["formal_judge_completed_rows"] == "2"
    assert summary["formal_judge_scored_rows"] == "1"
    assert summary["formal_judge_gate_decision"] == "pending"
    assert summary["formal_judge_gate_reason"] == "complete_judge_score_rows=1/2"


def test_phase54_summarize_existing_rebuilds_summary_without_provider_calls(tmp_path, monkeypatch) -> None:
    results_path = tmp_path / "results.csv"
    summary_path = tmp_path / "summary.csv"
    ablation_path = tmp_path / "ablation.csv"
    rows = [
        phase54_scored_row(
            "g1",
            "standard_reference_chain",
            "true",
            baseline_accuracy="3",
            graph_accuracy="4",
            baseline_completeness="3",
            graph_completeness="4",
            baseline_citation_quality="3",
            graph_citation_quality="4",
            graph_candidate_chunk_count="10",
        ),
        phase54_scored_row(
            "o1",
            "ordinary_baseline",
            "false",
            baseline_accuracy="4",
            graph_accuracy="4",
            baseline_completeness="4",
            graph_completeness="4",
            baseline_citation_quality="4",
            graph_citation_quality="4",
            graph_candidate_chunk_count="0",
        ),
    ]
    write_csv(results_path, rows)
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_phase54_graphrag_e2e.py",
            "--summarize-existing",
            "--case-id",
            "p54_std_001",
            "--results-output",
            str(results_path),
            "--summary-output",
            str(summary_path),
            "--ablation-output",
            str(ablation_path),
        ],
    )

    assert main() == 0
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        summary = {row["metric"]: row["value"] for row in csv.DictReader(handle)}
    with ablation_path.open("r", encoding="utf-8", newline="") as handle:
        ablation_rows = list(csv.DictReader(handle))

    assert summary["formal_judge_gate_decision"] == "pass"
    assert summary["total_cases"] == "2"
    assert len(ablation_rows) == 1


def phase54_scored_row(
    case_id: str,
    category: str,
    expected_graph_intent: str,
    *,
    baseline_accuracy: str,
    graph_accuracy: str,
    baseline_completeness: str,
    graph_completeness: str,
    baseline_citation_quality: str,
    graph_citation_quality: str,
    graph_candidate_chunk_count: str,
) -> dict[str, str]:
    return {
        "case_id": case_id,
        "category": category,
        "status": "completed",
        "expected_graph_intent": expected_graph_intent,
        "expected_relation_focus": "",
        "baseline_top_chunk_ids": "1",
        "graph_top_chunk_ids": "1",
        "baseline_top_title_hashes": "aaa",
        "graph_top_title_hashes": "aaa",
        "graph_candidate_chunk_count": graph_candidate_chunk_count,
        "graph_used_match_count": graph_candidate_chunk_count,
        "baseline_answer_chars": "100",
        "graph_answer_chars": "100",
        "baseline_accuracy": baseline_accuracy,
        "graph_accuracy": graph_accuracy,
        "baseline_completeness": baseline_completeness,
        "graph_completeness": graph_completeness,
        "baseline_citation_quality": baseline_citation_quality,
        "graph_citation_quality": graph_citation_quality,
        "judge_reason": "synthetic",
        "error": "",
    }

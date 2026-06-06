import csv

from scripts.analyze_real_rag_failures import (
    RealRagFailureCase,
    analyze_real_rag_failures,
    brain_failure_type,
    write_failure_cases,
)


def write_csv(path, fieldnames, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_analyze_real_rag_failures_records_brain_under_refusal_and_vector_gap(tmp_path) -> None:
    brain_results = tmp_path / "brain.csv"
    vector_results = tmp_path / "vector.csv"

    write_csv(
        brain_results,
        [
            "config_name",
            "query_id",
            "question",
            "passed",
            "expected_refused",
            "refused",
            "refusal_matched",
            "expected_source_hit",
            "citations_valid",
            "forbidden_terms_absent",
            "configured_retrieval_mode",
            "actual_retrieval_mode",
            "source_count",
            "citations",
            "top_source_titles",
            "notes",
        ],
        [
            {
                "config_name": "default_hybrid",
                "query_id": "unsupported",
                "question": "nonsense",
                "passed": "no",
                "expected_refused": "yes",
                "refused": "no",
                "refusal_matched": "no",
                "expected_source_hit": "yes",
                "citations_valid": "yes",
                "forbidden_terms_absent": "yes",
                "configured_retrieval_mode": "hybrid",
                "actual_retrieval_mode": "hybrid",
                "source_count": "5",
                "citations": "1|2",
                "top_source_titles": "Wrong Topic",
                "notes": "Synthetic out-of-corpus token should be refused.",
            }
        ],
    )
    write_csv(
        vector_results,
        [
            "query_id",
            "query",
            "passed",
            "comparison",
            "result_count",
            "best_score",
            "top_titles",
            "notes",
        ],
        [
            {
                "query_id": "mesoscopic_modeling",
                "query": "细观 数值 模拟 堆石混凝土",
                "passed": "no",
                "comparison": "keyword_only_pass",
                "result_count": "8",
                "best_score": "0.71",
                "top_titles": "Broad RFC",
                "notes": "检查中文细观/数值/模拟到英文 mesoscopic/simulation 的召回",
            }
        ],
    )

    cases = analyze_real_rag_failures(brain_results, vector_results)

    assert len(cases) == 2
    assert cases[0].failure_type == "under_refusal"
    assert cases[0].failure_mode == "unsupported_low_evidence"
    assert "low-evidence refusal" in cases[0].suggested_fix
    assert cases[1].failure_type == "vector_expected_source_miss"
    assert cases[1].failure_mode == "cross_language_topic_gap"
    assert "query expansion" in cases[1].suggested_fix


def test_brain_failure_type_prefers_refusal_mismatch() -> None:
    assert (
        brain_failure_type(
            {
                "expected_refused": "yes",
                "refused": "no",
                "refusal_matched": "no",
                "expected_source_hit": "no",
            }
        )
        == "under_refusal"
    )


def test_write_failure_cases_uses_stable_schema(tmp_path) -> None:
    output_path = tmp_path / "real_failures.csv"

    write_failure_cases(
        output_path,
        [
            RealRagFailureCase(
                case_id="case",
                source_file="source.csv",
                query_id="q",
                config_name="vector_only",
                question="question",
                expected_refused="yes",
                refused="no",
                configured_retrieval_mode="vector",
                actual_retrieval_mode="vector",
                source_count="5",
                citations="1|2",
                failure_type="under_refusal",
                failure_mode="unsupported_low_evidence",
                expected_evidence="none",
                actual_top_titles="title",
                likely_reason="reason",
                suggested_fix="fix",
                before_status="failed",
            )
        ],
    )

    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["case_id"] == "case"
    assert rows[0]["after_status"] == "pending_stage_10"

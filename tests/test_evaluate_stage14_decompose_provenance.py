from pathlib import Path

from scripts.evaluate_stage14_decompose_provenance import (
    build_provenance_review,
    parse_rerank_explanation,
    write_results,
)


def seed_decompose_results(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "query_id,question,language_type,passed,expected_refused,brain_refused,refusal_matched,"
        "decompose_applied,sub_query_count,sub_queries,raw_result_count,merged_result_count,"
        "deduplicated_count,provenance_present,expected_source_hit,actual_source_hit,"
        "source_hit_matched,answer_coverage_proxy,top_source_titles,rerank_explanations,"
        "failed_reason,notes\n"
        "q1,Question?,en,yes,no,no,yes,yes,2,sub one || sub two,10,2,8,yes,yes,yes,yes,yes,"
        "Title One || Title Two,"
        "\"sub_queries=2; topic_terms=rfc,fill; both_match=True; source_type=local_file; raw_score=1.0000; final_score=1.5000 || "
        "sub_queries=1; topic_terms=compactness; both_match=False; source_type=metadata_record; raw_score=0.8000; final_score=1.1000\",,"
        "note\n",
        encoding="utf-8",
    )


def test_parse_rerank_explanation_extracts_named_fields() -> None:
    parsed = parse_rerank_explanation(
        "sub_queries=2; topic_terms=rfc,fill; both_match=True; source_type=local_file; raw_score=1.0000; final_score=1.5000"
    )

    assert parsed["sub_queries"] == "2"
    assert parsed["topic_terms"] == "rfc,fill"
    assert parsed["both_match"] == "True"
    assert parsed["source_type"] == "local_file"
    assert parsed["final_score"] == "1.5000"


def test_build_provenance_review_outputs_one_row_per_evidence(tmp_path) -> None:
    path = tmp_path / "stage13_decompose_results.csv"
    seed_decompose_results(path)

    rows = build_provenance_review(path)

    assert len(rows) == 2
    assert rows[0].query_id == "q1"
    assert rows[0].evidence_rank == 1
    assert rows[0].evidence_title == "Title One"
    assert rows[0].evidence_sub_query_count == "2"
    assert rows[0].both_match == "True"
    assert "provenance present" in rows[0].review_note
    assert rows[1].evidence_title == "Title Two"
    assert rows[1].topic_terms == "compactness"


def test_write_results_outputs_decompose_provenance_review_csv(tmp_path) -> None:
    path = tmp_path / "stage13_decompose_results.csv"
    seed_decompose_results(path)
    rows = build_provenance_review(path)
    out = tmp_path / "stage14_decompose_provenance_review.csv"

    write_results(out, rows)

    content = out.read_text(encoding="utf-8")
    assert "query_id,question,language_type,decompose_applied" in content
    assert "q1,Question?,en,yes,2,sub one || sub two,1,Title One" in content

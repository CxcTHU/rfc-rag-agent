from pathlib import Path

from scripts.evaluate_stage16_answer_coverage_closure import (
    build_stage16_closures,
    classify_root_cause,
    close_stage15_row,
    stage16_answer_covers_expected,
    write_results,
)


def write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_classify_timeout_high_risk_root_cause() -> None:
    row = {
        "answer_summary": "",
        "evidence_titles": "Source A",
        "review_note": "Real result failed with error: The read operation timed out",
    }

    assert classify_root_cause(row) == "provider_timeout"


def test_close_stage15_row_keeps_timeout_as_high_blocking() -> None:
    row = {
        "review_id": "stage15_review_002",
        "query_id": "user_mixed_itz_strength",
        "risk_level": "high",
        "question": "RFC 里 rock 和 SCC 的界面 ITZ 会怎样影响强度？",
        "expected_answer_points": "说明 rock/SCC 界面或 ITZ 对强度和破坏的影响",
        "answer_summary": "",
        "evidence_titles": "ITZ source",
        "faithfulness": "fail",
        "answer_coverage": "fail",
        "citation_quality": "review",
        "review_note": "Real result failed with error: The read operation timed out",
    }

    closure = close_stage15_row(index=1, row=row)

    assert closure.risk_before == "high"
    assert closure.risk_after == "high"
    assert closure.root_cause == "provider_timeout"
    assert closure.decision == "blocking"


def test_close_stage15_row_lowers_clear_medium_to_low() -> None:
    row = {
        "review_id": "stage15_review_006",
        "query_id": "user_cn_porosity_compression",
        "risk_level": "medium",
        "question": "孔隙率会怎么影响堆石混凝土抗压表现？",
        "expected_answer_points": "说明孔隙率或初始孔洞对抗压行为的影响",
        "answer_summary": "孔隙率和初始孔洞会影响抗压行为，孔隙率增加会降低抗压强度。",
        "evidence_titles": "Porosity source",
        "faithfulness": "pass",
        "answer_coverage": "review",
        "citation_quality": "pass",
        "review_note": "Real model answer has matched sources.",
    }

    closure = close_stage15_row(index=1, row=row)

    assert closure.risk_after == "low"
    assert closure.answer_coverage == "pass"
    assert closure.decision == "accepted"


def test_close_stage15_row_keeps_limited_evidence_as_medium() -> None:
    row = {
        "review_id": "stage15_review_008",
        "query_id": "user_cn_shear_key",
        "risk_level": "medium",
        "question": "岩石剪力键会影响冷缝剪切性能吗？",
        "expected_answer_points": "说明岩石剪力键和冷缝剪切性能关系",
        "answer_summary": "当前知识库仅提供元数据，证据尚不充分，无法说明具体机理。",
        "evidence_titles": "Shear key source",
        "faithfulness": "pass",
        "answer_coverage": "review",
        "citation_quality": "pass",
        "review_note": "Real model answer has matched sources.",
    }

    closure = close_stage15_row(index=1, row=row)

    assert closure.risk_after == "medium"
    assert closure.root_cause == "source_detail_limited"
    assert closure.decision == "accepted_with_review"


def test_build_stage16_closures_filters_high_and_medium_rows(tmp_path) -> None:
    review = tmp_path / "stage15_answer_coverage_review.csv"
    write_csv(
        review,
        "review_id,source_review_id,query_id,config_name,question,expected_answer_points,answer_summary,evidence_titles,faithfulness,answer_coverage,citation_quality,risk_level,review_method,review_note,next_action,skipped_reason\n"
        "r1,s1,q1,real_config,Q1,说明 filling quality,This explains filling quality.,Source A,pass,review,pass,medium,real,note,next,\n"
        "r2,s2,q2,real_config,Q2,说明 timeout,,Source B,fail,fail,review,high,real,Real result failed with error: The read operation timed out,next,\n"
        "r3,s3,q3,real_config,Q3,说明 low,Answer,Source C,pass,pass,pass,low,real,note,next,\n",
    )

    closures = build_stage16_closures(stage15_review_path=review)

    assert len(closures) == 2
    assert {closure.risk_before for closure in closures} == {"medium", "high"}


def test_write_results_outputs_stage16_closure_csv(tmp_path) -> None:
    review = tmp_path / "stage15_answer_coverage_review.csv"
    write_csv(
        review,
        "review_id,source_review_id,query_id,config_name,question,expected_answer_points,answer_summary,evidence_titles,faithfulness,answer_coverage,citation_quality,risk_level,review_method,review_note,next_action,skipped_reason\n"
        "r1,s1,q1,real_config,Q1,说明 filling quality,This explains filling quality.,Source A,pass,review,pass,medium,real,note,next,\n",
    )
    closures = build_stage16_closures(stage15_review_path=review)
    out = tmp_path / "stage16_answer_coverage_closure.csv"

    write_results(out, closures)

    content = out.read_text(encoding="utf-8")
    assert "closure_id,source_review_id,query_id,risk_before,risk_after" in content
    assert "stage16_closure_001,r1,q1,medium" in content


def test_stage16_answer_covers_expected_handles_chinese_domain_terms() -> None:
    assert stage16_answer_covers_expected(
        "孔隙率和初始孔洞会影响抗压行为，孔隙率增加会降低抗压强度。",
        "说明孔隙率或初始孔洞对抗压行为的影响",
    )

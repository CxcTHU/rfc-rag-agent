import csv

from scripts.judge_stage30_semantic_quality import (
    build_dry_run_rows,
    parse_judge_payload,
    read_stage29_rows,
    run_judge_rows,
    write_rows,
)


def test_stage30_semantic_judge_dry_run_does_not_fake_scores(tmp_path) -> None:
    rows = [
        {"query_id": "q1", "expected_refused": "false"},
        {"query_id": "q2", "expected_refused": "true"},
    ]

    judge_rows = build_dry_run_rows(
        rows,
        judge_provider="",
        judge_model="",
        execute_requested=False,
    )

    assert judge_rows[0]["manual_run"] == "false"
    assert judge_rows[0]["faithfulness_score"] == ""
    assert judge_rows[0]["answer_relevancy_score"] == ""
    assert judge_rows[0]["groundedness_score"] == ""
    assert "dry_run_no_model_call" in judge_rows[0]["judge_reason"]


def test_stage30_semantic_judge_filters_refusal_rows_and_writes_csv(tmp_path) -> None:
    source = tmp_path / "stage29.csv"
    source.write_text(
        "\n".join(
            [
                "query_id,expected_refused",
                "q1,false",
                "q2,true",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "judge.csv"

    rows = read_stage29_rows(source)
    judge_rows = build_dry_run_rows(
        rows,
        judge_provider="mimo",
        judge_model="manual",
        execute_requested=True,
    )
    write_rows(output, judge_rows)

    with output.open("r", encoding="utf-8", newline="") as file:
        written = list(csv.DictReader(file))
    assert [row["query_id"] for row in written] == ["q1"]
    assert written[0]["manual_run"] == "true"
    assert written[0]["error_summary"] == "missing_env:STAGE30_JUDGE_API_KEY"


def test_stage30_semantic_judge_execute_requires_env_key_and_does_not_call_client() -> None:
    class FailingClient:
        def judge(self, row):  # pragma: no cover - should never be reached
            raise AssertionError("client should not be called without an API key")

    judge_rows = run_judge_rows(
        [{"query_id": "q1", "expected_refused": "false"}],
        judge_provider="deepseek",
        judge_model="deepseek-chat",
        execute_requested=True,
        env={},
        client=FailingClient(),
    )

    assert judge_rows[0]["manual_run"] == "true"
    assert judge_rows[0]["faithfulness_score"] == ""
    assert judge_rows[0]["error_summary"] == "missing_env:STAGE30_JUDGE_API_KEY"


def test_stage30_semantic_judge_execute_with_fake_client_writes_scores() -> None:
    class FakeClient:
        def judge(self, row):
            assert row["query_id"] == "q1"
            return {
                "faithfulness_score": "0.810",
                "answer_relevancy_score": "0.730",
                "groundedness_score": "0.660",
                "judge_reason": "Evidence partially supports the answer.",
            }

    judge_rows = run_judge_rows(
        [{"query_id": "q1", "expected_refused": "false"}],
        judge_provider="deepseek",
        judge_model="deepseek-chat",
        execute_requested=True,
        env={"STAGE30_JUDGE_API_KEY": "test-key"},
        client=FakeClient(),
    )

    assert judge_rows[0]["manual_run"] == "true"
    assert judge_rows[0]["faithfulness_score"] == "0.810"
    assert judge_rows[0]["answer_relevancy_score"] == "0.730"
    assert judge_rows[0]["groundedness_score"] == "0.660"
    assert judge_rows[0]["error_summary"] == ""


def test_stage30_semantic_judge_parses_and_sanitizes_payload() -> None:
    parsed = parse_judge_payload(
        """```json
        {
          "faithfulness_score": 1.4,
          "answer_relevancy_score": 0.5,
          "groundedness_score": -0.2,
          "judge_reason": "ok raw_response Bearer sk-testsecret123456"
        }
        ```"""
    )

    assert parsed["faithfulness_score"] == "1.000"
    assert parsed["answer_relevancy_score"] == "0.500"
    assert parsed["groundedness_score"] == "0.000"
    assert "raw_response" not in parsed["judge_reason"]
    assert "Bearer" not in parsed["judge_reason"]
    assert "sk-testsecret123456" not in parsed["judge_reason"]

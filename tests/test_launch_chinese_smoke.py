from scripts.run_launch_chinese_smoke import (
    CASES,
    decode_escape,
    parse_stream_metadata,
    run_smoke,
)


def test_launch_chinese_smoke_dry_run_rows_are_planned() -> None:
    rows = run_smoke(
        base_url="http://127.0.0.1:8044",
        execute=False,
        auth_enabled=True,
        username="launch_cn_test",
        password="local-smoke-only-password",
        timeout_seconds=1,
        max_tool_calls=2,
        use_stream=True,
    )

    assert len(rows) == len(CASES)
    assert {row["status"] for row in rows} == {"planned"}
    assert rows[-1]["case_id"] == "table_evidence"


def test_launch_chinese_smoke_decodes_domain_questions_without_source_encoding() -> None:
    decoded = decode_escape(CASES[0].question_escape)

    assert decoded == "堆石混凝土有哪些优点？"


def test_launch_chinese_smoke_parses_stream_metadata() -> None:
    body = (
        'event: heartbeat\n'
        'data: {"elapsed_ms":10000}\n\n'
        'event: metadata\n'
        'data: {"refused":false,"citations":[1],"sources":[{"chunk_type":"text"}]}\n\n'
        'event: done\n'
        'data: {}\n\n'
    )

    metadata = parse_stream_metadata(body)

    assert metadata["refused"] is False
    assert metadata["citations"] == [1]

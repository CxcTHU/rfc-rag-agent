from scripts import benchmark_stage33_chat_providers as benchmark


def test_stage33_chat_provider_benchmark_dry_run_writes_mimo_and_deepseek(tmp_path, monkeypatch) -> None:
    output = tmp_path / "stage33_chat_provider_benchmark.csv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark_stage33_chat_providers.py",
            "--output",
            str(output),
        ],
    )

    benchmark.main()

    content = output.read_text(encoding="utf-8")
    assert "mimo_baseline" in content
    assert "deepseek_candidate" in content
    assert "dry_run" in content
    assert "reasoning_content_leak_risk" in content


def test_stage33_chat_provider_benchmark_dry_run_has_no_leak_risk() -> None:
    rows = benchmark.run_dry()

    assert rows
    assert {row["candidate"] for row in rows} == {"mimo_baseline", "deepseek_candidate"}
    assert all(row["reasoning_content_leak_risk"] == "false" for row in rows)

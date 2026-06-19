import csv
import json

from scripts.analyze_phase45_throughput import compute_concurrency_peak, main, percentile


def test_percentile_interpolates_latency_values() -> None:
    assert percentile([100, 200, 300, 400], 50) == 250
    assert percentile([100, 200, 300, 400], 90) == 370


def test_compute_concurrency_peak_from_describe_intervals() -> None:
    rows = [
        {
            "started_at": "2026-06-19T00:00:00+00:00",
            "ended_at": "2026-06-19T00:00:05+00:00",
        },
        {
            "started_at": "2026-06-19T00:00:02+00:00",
            "ended_at": "2026-06-19T00:00:06+00:00",
        },
        {
            "started_at": "2026-06-19T00:00:06+00:00",
            "ended_at": "2026-06-19T00:00:07+00:00",
        },
    ]

    assert compute_concurrency_peak(rows) == 2


def test_analyze_phase45_throughput_writes_summary(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "probe" / "official_a"
    run_dir.mkdir(parents=True)
    timing_path = run_dir / "multimodal_timing.csv"
    with timing_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "event_type",
                "document_id",
                "provider",
                "model_name",
                "source_image_path",
                "page_num",
                "status",
                "elapsed_ms",
                "started_at",
                "ended_at",
                "image_count",
                "width",
                "height",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "event_type": "extract_document",
                "document_id": "1",
                "provider": "official_a",
                "model_name": "GLM-4.6V",
                "status": "ok",
                "elapsed_ms": "1000",
                "started_at": "2026-06-19T00:00:00+00:00",
                "ended_at": "2026-06-19T00:00:01+00:00",
                "image_count": "2",
            }
        )
        writer.writerow(
            {
                "event_type": "describe_image",
                "document_id": "1",
                "provider": "official_a",
                "model_name": "GLM-4.6V",
                "source_image_path": "data/images/1/a.png",
                "page_num": "1",
                "status": "described",
                "elapsed_ms": "2000",
                "started_at": "2026-06-19T00:00:01+00:00",
                "ended_at": "2026-06-19T00:00:03+00:00",
            }
        )
    (run_dir / "multimodal_staging_summary.json").write_text(
        json.dumps(
            {
                "extracted_images": 2,
                "described_images": 1,
                "skipped_existing_images": 1,
                "failed_images": 0,
                "elapsed_seconds": 3,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "summary.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "analyze_phase45_throughput.py",
            "--input-dir",
            str(tmp_path / "probe"),
            "--output",
            str(output),
        ],
    )

    main()

    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["extracted_images"] == 2
    assert summary["api_attempted_images"] == 1
    assert summary["successful_descriptions"] == 1
    assert summary["pdf_extract_total_seconds"] == 1
    assert summary["api_call_total_seconds"] == 2
    assert summary["concurrency_peak"] == 1

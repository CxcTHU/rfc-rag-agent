import csv
from pathlib import Path

from scripts.summarize_phase46_redescribe_staging import summarize_staging


def test_summarize_staging_deduplicates_described_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    write_csv(
        manifest,
        ["source_image_path", "status"],
        [
            {"source_image_path": "a.png", "status": "pending"},
            {"source_image_path": "b.png", "status": "pending"},
        ],
    )
    staging_a = tmp_path / "staging_a" / "route"
    staging_b = tmp_path / "staging_b" / "route"
    staging_a.mkdir(parents=True)
    staging_b.mkdir(parents=True)
    fields = [
        "document_id",
        "document_title",
        "page_num",
        "source_image_path",
        "width",
        "height",
        "status",
        "description",
        "error",
    ]
    write_csv(
        staging_a / "multimodal_staging.csv",
        fields,
        [
            {"source_image_path": "a.png", "status": "described", "description": "old"},
            {"source_image_path": "b.png", "status": "failed", "error": "timeout"},
        ],
    )
    write_csv(
        staging_b / "multimodal_staging.csv",
        fields,
        [
            {"source_image_path": "a.png", "status": "described", "description": "new"},
            {"source_image_path": "b.png", "status": "described", "description": "ok"},
        ],
    )

    rows, summary = summarize_staging(manifest_path=manifest, staging_dirs=[tmp_path / "staging_a", tmp_path / "staging_b"])

    assert summary == {
        "expected_images": 2,
        "described_images": 2,
        "missing_images": 0,
        "failed_rows_seen": 1,
        "duplicate_described_rows": 1,
    }
    assert {row["source_image_path"] for row in rows} == {"a.png", "b.png"}
    assert next(row for row in rows if row["source_image_path"] == "a.png")["description"] == "new"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

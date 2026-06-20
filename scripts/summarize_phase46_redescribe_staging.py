"""Summarize and de-duplicate Phase 46 redescription staging outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


DEFAULT_MANIFEST = Path("data/evaluation/phase46_rendered_image_manifest.csv")
DEFAULT_OUTPUT_CSV = Path("data/evaluation/phase46_redescribe_report.csv")
DEFAULT_OUTPUT_SUMMARY = Path("data/evaluation/phase46_redescribe_summary.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Phase 46 redescription staging outputs.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--staging-dir", action="append", required=True)
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--summary-json", default=str(DEFAULT_OUTPUT_SUMMARY))
    args = parser.parse_args()

    rows, summary = summarize_staging(
        manifest_path=Path(args.manifest),
        staging_dirs=[Path(path) for path in args.staging_dir],
    )
    write_report(Path(args.output_csv), rows)
    Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("summary:", " ".join(f"{key}={value}" for key, value in summary.items()))
    print(f"wrote {args.output_csv}")
    print(f"wrote {args.summary_json}")


def summarize_staging(
    *,
    manifest_path: Path,
    staging_dirs: list[Path],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    expected_paths = read_manifest_paths(manifest_path)
    latest_by_path: dict[str, dict[str, str]] = {}
    duplicate_described = 0
    failed_rows = 0
    for staging_dir in staging_dirs:
        for csv_path in sorted(staging_dir.glob("*/multimodal_staging.csv")):
            route = csv_path.parent.name
            with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                for row in csv.DictReader(file):
                    source_image_path = normalize_path(row.get("source_image_path") or "")
                    if not source_image_path:
                        continue
                    row = dict(row)
                    row["route"] = route
                    row["staging_csv"] = csv_path.as_posix()
                    if row.get("status") == "described":
                        if source_image_path in latest_by_path:
                            duplicate_described += 1
                        latest_by_path[source_image_path] = row
                    elif row.get("status") == "failed":
                        failed_rows += 1
    missing_paths = sorted(expected_paths - set(latest_by_path))
    rows = [latest_by_path[path] for path in sorted(latest_by_path)]
    summary = {
        "expected_images": len(expected_paths),
        "described_images": len(latest_by_path),
        "missing_images": len(missing_paths),
        "failed_rows_seen": failed_rows,
        "duplicate_described_rows": duplicate_described,
    }
    return rows, summary


def read_manifest_paths(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {
            normalize_path(row.get("source_image_path") or "")
            for row in csv.DictReader(file)
            if (row.get("status") or "").strip() == "pending"
        }


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "document_id",
        "document_title",
        "page_num",
        "source_image_path",
        "width",
        "height",
        "status",
        "description",
        "error",
        "route",
        "staging_csv",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


if __name__ == "__main__":
    main()

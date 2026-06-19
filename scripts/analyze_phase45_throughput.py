"""Aggregate Phase 45 multimodal throughput timing files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean


@dataclass(frozen=True)
class ProviderThroughput:
    provider: str
    attempted_images: int
    successful_images: int
    failed_images: int
    success_rate: float
    avg_api_ms: float
    p50_api_ms: float
    p90_api_ms: float
    p95_api_ms: float


@dataclass(frozen=True)
class ThroughputSummary:
    timing_files: int
    staging_summary_files: int
    import_summary_files: int
    embedding_summary_files: int
    extracted_images: int
    api_attempted_images: int
    successful_descriptions: int
    failed_descriptions: int
    skipped_existing_images: int
    avg_api_ms: float
    p50_api_ms: float
    p90_api_ms: float
    p95_api_ms: float
    pdf_extract_total_seconds: float
    api_call_total_seconds: float
    embedding_total_seconds: float
    staging_total_seconds: float
    import_total_seconds: float
    concurrency_peak: int
    providers: list[ProviderThroughput]


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Phase 45 multimodal throughput.")
    parser.add_argument("--input-dir", action="append", required=True)
    parser.add_argument("--embedding-summary", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_dirs = [Path(value) for value in args.input_dir]
    timing_paths = find_named_files(input_dirs, "multimodal_timing.csv")
    staging_summary_paths = find_named_files(input_dirs, "multimodal_staging_summary.json")
    import_summary_paths = find_named_files(input_dirs, "import_multimodal_staging_summary.json")
    embedding_summary_paths = [Path(value) for value in args.embedding_summary]

    timing_rows = [row for path in timing_paths for row in read_csv(path)]
    staging_summaries = [read_json(path) for path in staging_summary_paths]
    import_summaries = [read_json(path) for path in import_summary_paths]
    embedding_summaries = [read_json(path) for path in embedding_summary_paths if path.exists()]

    describe_rows = [row for row in timing_rows if row.get("event_type") == "describe_image"]
    extract_rows = [row for row in timing_rows if row.get("event_type") == "extract_document"]
    api_ms = [float_value(row.get("elapsed_ms")) for row in describe_rows]
    successful_rows = [row for row in describe_rows if row.get("status") == "described"]
    failed_rows = [row for row in describe_rows if row.get("status") != "described"]
    provider_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in describe_rows:
        provider_rows[row.get("provider") or "unknown"].append(row)

    summary = ThroughputSummary(
        timing_files=len(timing_paths),
        staging_summary_files=len(staging_summary_paths),
        import_summary_files=len(import_summary_paths),
        embedding_summary_files=len(embedding_summaries),
        extracted_images=sum_int(staging_summaries, "extracted_images"),
        api_attempted_images=len(describe_rows),
        successful_descriptions=len(successful_rows),
        failed_descriptions=len(failed_rows),
        skipped_existing_images=sum_int(staging_summaries, "skipped_existing_images"),
        avg_api_ms=round(mean(api_ms), 3) if api_ms else 0.0,
        p50_api_ms=percentile(api_ms, 50),
        p90_api_ms=percentile(api_ms, 90),
        p95_api_ms=percentile(api_ms, 95),
        pdf_extract_total_seconds=round(sum(float_value(row.get("elapsed_ms")) for row in extract_rows) / 1000, 3),
        api_call_total_seconds=round(sum(api_ms) / 1000, 3),
        embedding_total_seconds=round(sum(float_value(item.get("elapsed_seconds")) for item in embedding_summaries), 3),
        staging_total_seconds=round(sum(float_value(item.get("elapsed_seconds")) for item in staging_summaries), 3),
        import_total_seconds=round(sum(float_value(item.get("elapsed_seconds")) for item in import_summaries), 3),
        concurrency_peak=compute_concurrency_peak(describe_rows),
        providers=[
            summarize_provider(provider, rows)
            for provider, rows in sorted(provider_rows.items(), key=lambda item: item[0])
        ],
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))


def find_named_files(input_dirs: list[Path], file_name: str) -> list[Path]:
    paths: list[Path] = []
    for directory in input_dirs:
        if directory.is_file() and directory.name == file_name:
            paths.append(directory)
        elif directory.exists():
            paths.extend(sorted(directory.glob(f"**/{file_name}")))
    return paths


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sum_int(items: list[dict[str, object]], key: str) -> int:
    return sum(int(float_value(item.get(key))) for item in items)


def float_value(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * (percent / 100)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
    return round(value, 3)


def summarize_provider(provider: str, rows: list[dict[str, str]]) -> ProviderThroughput:
    durations = [float_value(row.get("elapsed_ms")) for row in rows]
    success = sum(1 for row in rows if row.get("status") == "described")
    failed = len(rows) - success
    return ProviderThroughput(
        provider=provider,
        attempted_images=len(rows),
        successful_images=success,
        failed_images=failed,
        success_rate=round(success / len(rows), 4) if rows else 0.0,
        avg_api_ms=round(mean(durations), 3) if durations else 0.0,
        p50_api_ms=percentile(durations, 50),
        p90_api_ms=percentile(durations, 90),
        p95_api_ms=percentile(durations, 95),
    )


def compute_concurrency_peak(rows: list[dict[str, str]]) -> int:
    events: list[tuple[datetime, int]] = []
    for row in rows:
        start = parse_datetime(row.get("started_at"))
        end = parse_datetime(row.get("ended_at"))
        if start is None or end is None:
            continue
        events.append((start, 1))
        events.append((end, -1))
    active = peak = 0
    for _moment, delta in sorted(events, key=lambda item: (item[0], -item[1])):
        active += delta
        peak = max(peak, active)
    return peak


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


if __name__ == "__main__":
    main()

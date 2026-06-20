"""Describe PDF images into staging files without writing SQLite chunks."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.generation.vision_model import create_vision_model_provider  # noqa: E402
from app.services.ingestion.image_extractor import PdfImageExtractionConfig, PdfImageExtractor  # noqa: E402
from scripts.process_multimodal import read_document_ids_file, sanitize_error  # noqa: E402


STAGING_FIELDS = [
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

TIMING_FIELDS = [
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
]


@dataclass(frozen=True)
class StagingImageRow:
    document_id: int
    document_title: str
    page_num: int
    source_image_path: str
    width: int
    height: int
    status: str
    description: str = ""
    error: str = ""


@dataclass(frozen=True)
class StagingSummary:
    selected_documents: int
    processed_documents: int
    failed_documents: int
    extracted_images: int
    described_images: int
    skipped_existing_images: int
    failed_images: int
    elapsed_seconds: float
    provider: str
    model_name: str


@dataclass(frozen=True)
class TimingEvent:
    event_type: str
    document_id: int
    provider: str
    model_name: str
    source_image_path: str
    page_num: int
    status: str
    elapsed_ms: float
    started_at: str
    ended_at: str
    image_count: int = 0
    width: int = 0
    height: int = 0
    error: str = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Describe PDF images into staging CSV/JSON.")
    parser.add_argument("--document-ids-file", default="")
    parser.add_argument("--image-manifest", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--db-path", default=str(ROOT / "data" / "app.sqlite"))
    parser.add_argument("--image-output-dir", default="data/images")
    parser.add_argument("--min-width", type=int, default=100)
    parser.add_argument("--min-height", type=int, default=100)
    parser.add_argument(
        "--max-new-images-per-document",
        type=int,
        default=0,
        help="Limit newly described images per document; capped documents are written as partial.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    parser.add_argument("--provider-label", default="", help="Optional safe label used in timing summaries.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent vision API workers for image-manifest mode.")
    parser.add_argument("--vision-provider", default="", help="Override VISION_MODEL_PROVIDER for this run.")
    parser.add_argument("--vision-model-name", default="", help="Override VISION_MODEL_NAME for this run.")
    parser.add_argument("--vision-api-key-env", default="", help="Read the vision API key from this env var.")
    parser.add_argument("--vision-api-key", default="", help="Direct API key override; prefer --vision-api-key-env.")
    parser.add_argument("--vision-base-url", default="", help="Override VISION_MODEL_BASE_URL for this run.")
    parser.add_argument("--vision-timeout-seconds", type=float, default=0.0)
    args = parser.parse_args()

    settings = get_settings()
    vision_provider = build_vision_provider(settings, args)
    provider_label = args.provider_label.strip() or vision_provider.provider_name
    if args.image_manifest:
        rows, timing_events, summary = process_image_manifests(
            manifest_paths=[Path(value) for value in args.image_manifest],
            vision_provider=vision_provider,
            provider_label=provider_label,
            output_dir=Path(args.output_dir),
            checkpoint_every=args.checkpoint_every,
            workers=args.workers,
            limit=args.limit,
            offset=args.offset,
        )
        write_outputs(rows, timing_events, summary, Path(args.output_dir))
        write_document_status_outputs(
            Path(args.output_dir),
            processed_document_ids=processed_document_ids_from_rows(rows),
            failed_document_ids=[],
            no_image_document_ids=[],
            partial_document_ids=[],
        )
        return

    if not args.document_ids_file:
        raise ValueError("--document-ids-file is required when --image-manifest is not provided")

    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=Path(args.image_output_dir),
            min_width=args.min_width,
            min_height=args.min_height,
        )
    )
    document_ids = read_document_ids_file(Path(args.document_ids_file))
    if args.offset:
        document_ids = document_ids[args.offset :]
    if args.limit:
        document_ids = document_ids[: args.limit]
    rows: list[StagingImageRow] = []
    timing_events: list[TimingEvent] = []
    processed_document_ids: list[int] = []
    failed_document_ids: list[int] = []
    no_image_document_ids: list[int] = []
    partial_document_ids: list[int] = []
    processed_documents = failed_documents = 0
    run_started = time.perf_counter()
    run_started_at = utc_now()
    with sqlite3.connect(args.db_path, timeout=10) as connection:
        documents = read_documents(connection, document_ids)
        existing_image_paths = read_existing_image_paths(connection)

    for document_id in document_ids:
        document = documents.get(document_id)
        if document is None:
            failed_documents += 1
            failed_document_ids.append(document_id)
            rows.append(
                StagingImageRow(
                    document_id=document_id,
                    document_title="",
                    page_num=0,
                    source_image_path="",
                    width=0,
                    height=0,
                    status="failed",
                    error="document_not_found_or_not_pdf",
                )
            )
            maybe_write_outputs(
                rows,
                timing_events,
                selected_documents=len(document_ids),
                output_dir=args.output_dir,
                checkpoint_every=args.checkpoint_every,
                run_started=run_started,
                provider=provider_label,
                model_name=vision_provider.model_name,
            )
            continue
        title, raw_path = document
        extract_started = time.perf_counter()
        extract_started_at = utc_now()
        try:
            images = extractor.extract_images(raw_path, document_id=document_id)
        except Exception as exc:  # noqa: BLE001 - staging keeps batch alive
            extract_ended_at = utc_now()
            sanitized_error = sanitize_error(exc)
            timing_events.append(
                TimingEvent(
                    event_type="extract_document",
                    document_id=document_id,
                    provider=provider_label,
                    model_name=vision_provider.model_name,
                    source_image_path="",
                    page_num=0,
                    status="failed",
                    elapsed_ms=elapsed_ms(extract_started),
                    started_at=extract_started_at,
                    ended_at=extract_ended_at,
                    error=sanitized_error,
                )
            )
            failed_documents += 1
            failed_document_ids.append(document_id)
            rows.append(
                StagingImageRow(
                    document_id=document_id,
                    document_title=title,
                    page_num=0,
                    source_image_path="",
                    width=0,
                    height=0,
                    status="failed",
                    error=sanitized_error,
                )
            )
            maybe_write_outputs(
                rows,
                timing_events,
                selected_documents=len(document_ids),
                output_dir=args.output_dir,
                checkpoint_every=args.checkpoint_every,
                run_started=run_started,
                provider=provider_label,
                model_name=vision_provider.model_name,
            )
            continue
        extract_ended_at = utc_now()
        timing_events.append(
            TimingEvent(
                event_type="extract_document",
                document_id=document_id,
                provider=provider_label,
                model_name=vision_provider.model_name,
                source_image_path="",
                page_num=0,
                status="ok",
                elapsed_ms=elapsed_ms(extract_started),
                started_at=extract_started_at,
                ended_at=extract_ended_at,
                image_count=len(images),
            )
        )

        processed_documents += 1
        if not images:
            no_image_document_ids.append(document_id)
            processed_document_ids.append(document_id)
            maybe_write_outputs(
                rows,
                timing_events,
                selected_documents=len(document_ids),
                output_dir=args.output_dir,
                checkpoint_every=args.checkpoint_every,
                run_started=run_started,
                provider=provider_label,
                model_name=vision_provider.model_name,
            )
            continue
        new_images = [image for image in images if image.image_path not in existing_image_paths]
        max_new_images = max(0, args.max_new_images_per_document)
        limited = bool(max_new_images and len(new_images) > max_new_images)
        attempted_new_images = 0
        for image in images:
            if image.image_path in existing_image_paths:
                rows.append(
                    StagingImageRow(
                        document_id=document_id,
                        document_title=title,
                        page_num=image.page_num,
                        source_image_path=image.image_path,
                        width=image.width,
                        height=image.height,
                        status="skipped_existing",
                    )
                )
                continue
            if max_new_images and attempted_new_images >= max_new_images:
                continue
            attempted_new_images += 1
            describe_started = time.perf_counter()
            describe_started_at = utc_now()
            try:
                description = vision_provider.describe_image(image.image_path)
            except Exception as exc:  # noqa: BLE001 - keep describing other images
                describe_ended_at = utc_now()
                sanitized_error = sanitize_error(exc)
                timing_events.append(
                    TimingEvent(
                        event_type="describe_image",
                        document_id=document_id,
                        provider=provider_label,
                        model_name=vision_provider.model_name,
                        source_image_path=image.image_path,
                        page_num=image.page_num,
                        status="failed",
                        elapsed_ms=elapsed_ms(describe_started),
                        started_at=describe_started_at,
                        ended_at=describe_ended_at,
                        width=image.width,
                        height=image.height,
                        error=sanitized_error,
                    )
                )
                rows.append(
                    StagingImageRow(
                        document_id=document_id,
                        document_title=title,
                        page_num=image.page_num,
                        source_image_path=image.image_path,
                        width=image.width,
                        height=image.height,
                        status="failed",
                        error=sanitized_error,
                    )
                )
                continue
            describe_ended_at = utc_now()
            timing_events.append(
                TimingEvent(
                    event_type="describe_image",
                    document_id=document_id,
                    provider=provider_label,
                    model_name=vision_provider.model_name,
                    source_image_path=image.image_path,
                    page_num=image.page_num,
                    status="described",
                    elapsed_ms=elapsed_ms(describe_started),
                    started_at=describe_started_at,
                    ended_at=describe_ended_at,
                    width=image.width,
                    height=image.height,
                )
            )
            rows.append(
                StagingImageRow(
                    document_id=document_id,
                    document_title=title,
                    page_num=image.page_num,
                    source_image_path=image.image_path,
                    width=image.width,
                    height=image.height,
                    status="described",
                    description=description,
                )
            )
        if limited:
            partial_document_ids.append(document_id)
        else:
            processed_document_ids.append(document_id)
        maybe_write_outputs(
            rows,
            timing_events,
            selected_documents=len(document_ids),
            output_dir=args.output_dir,
            checkpoint_every=args.checkpoint_every,
            run_started=run_started,
            provider=provider_label,
            model_name=vision_provider.model_name,
        )

    timing_events.append(
        TimingEvent(
            event_type="staging_run",
            document_id=0,
            provider=provider_label,
            model_name=vision_provider.model_name,
            source_image_path="",
            page_num=0,
            status="ok",
            elapsed_ms=elapsed_ms(run_started),
            started_at=run_started_at,
            ended_at=utc_now(),
        )
    )
    write_outputs(
        rows,
        timing_events,
        summarize(
            rows,
            len(document_ids),
            processed_documents,
            failed_documents,
            run_started=run_started,
            provider=provider_label,
            model_name=vision_provider.model_name,
        ),
        Path(args.output_dir),
    )


def process_image_manifests(
    *,
    manifest_paths: list[Path],
    vision_provider,
    provider_label: str,
    output_dir: Path,
    checkpoint_every: int,
    workers: int,
    limit: int,
    offset: int,
) -> tuple[list[StagingImageRow], list[TimingEvent], StagingSummary]:
    manifest_rows = read_image_manifest_rows(manifest_paths)
    if offset:
        manifest_rows = manifest_rows[offset:]
    if limit:
        manifest_rows = manifest_rows[:limit]
    run_started = time.perf_counter()
    run_started_at = utc_now()
    rows: list[StagingImageRow] = []
    timing_events: list[TimingEvent] = []
    jobs: list[StagingImageRow] = []
    for row in manifest_rows:
        status = (row.get("status") or "").strip()
        staging_row = StagingImageRow(
            document_id=int(row.get("document_id") or 0),
            document_title=row.get("document_title") or "",
            page_num=int(row.get("page_num") or 0),
            source_image_path=row.get("source_image_path") or "",
            width=int(row.get("width") or 0),
            height=int(row.get("height") or 0),
            status="skipped_existing" if status == "existing" else "failed",
            error=row.get("error") or "",
        )
        if status == "pending":
            jobs.append(
                StagingImageRow(
                    document_id=staging_row.document_id,
                    document_title=staging_row.document_title,
                    page_num=staging_row.page_num,
                    source_image_path=staging_row.source_image_path,
                    width=staging_row.width,
                    height=staging_row.height,
                    status="pending",
                )
            )
        elif status == "existing":
            rows.append(staging_row)
        else:
            rows.append(staging_row)

    worker_count = max(1, workers)
    if jobs:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    describe_manifest_image,
                    job,
                    vision_provider,
                    provider_label,
                )
                for job in jobs
            ]
            for future in as_completed(futures):
                row, event = future.result()
                rows.append(row)
                timing_events.append(event)
                maybe_write_outputs(
                    rows,
                    timing_events,
                    selected_documents=count_unique_documents(manifest_rows),
                    output_dir=str(output_dir),
                    checkpoint_every=checkpoint_every,
                    run_started=run_started,
                    provider=provider_label,
                    model_name=vision_provider.model_name,
                )

    timing_events.append(
        TimingEvent(
            event_type="staging_run",
            document_id=0,
            provider=provider_label,
            model_name=vision_provider.model_name,
            source_image_path="",
            page_num=0,
            status="ok",
            elapsed_ms=elapsed_ms(run_started),
            started_at=run_started_at,
            ended_at=utc_now(),
        )
    )
    summary = summarize(
        rows,
        selected_documents=count_unique_documents(manifest_rows),
        processed_documents=count_unique_documents(manifest_rows),
        failed_documents=0,
        run_started=run_started,
        provider=provider_label,
        model_name=vision_provider.model_name,
    )
    return rows, timing_events, summary


def read_image_manifest_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows.extend(csv.DictReader(file))
    return rows


def describe_manifest_image(row: StagingImageRow, vision_provider, provider_label: str) -> tuple[StagingImageRow, TimingEvent]:
    describe_started = time.perf_counter()
    describe_started_at = utc_now()
    try:
        description = vision_provider.describe_image(row.source_image_path)
    except Exception as exc:  # noqa: BLE001 - keep other workers alive
        sanitized_error = sanitize_error(exc)
        return (
            StagingImageRow(
                document_id=row.document_id,
                document_title=row.document_title,
                page_num=row.page_num,
                source_image_path=row.source_image_path,
                width=row.width,
                height=row.height,
                status="failed",
                error=sanitized_error,
            ),
            TimingEvent(
                event_type="describe_image",
                document_id=row.document_id,
                provider=provider_label,
                model_name=vision_provider.model_name,
                source_image_path=row.source_image_path,
                page_num=row.page_num,
                status="failed",
                elapsed_ms=elapsed_ms(describe_started),
                started_at=describe_started_at,
                ended_at=utc_now(),
                width=row.width,
                height=row.height,
                error=sanitized_error,
            ),
        )
    return (
        StagingImageRow(
            document_id=row.document_id,
            document_title=row.document_title,
            page_num=row.page_num,
            source_image_path=row.source_image_path,
            width=row.width,
            height=row.height,
            status="described",
            description=description,
        ),
        TimingEvent(
            event_type="describe_image",
            document_id=row.document_id,
            provider=provider_label,
            model_name=vision_provider.model_name,
            source_image_path=row.source_image_path,
            page_num=row.page_num,
            status="described",
            elapsed_ms=elapsed_ms(describe_started),
            started_at=describe_started_at,
            ended_at=utc_now(),
            width=row.width,
            height=row.height,
        ),
    )


def count_unique_documents(rows: list[dict[str, str]]) -> int:
    return len({int(row.get("document_id") or 0) for row in rows if row.get("document_id")})


def processed_document_ids_from_rows(rows: list[StagingImageRow]) -> list[int]:
    failed = {row.document_id for row in rows if row.status == "failed" and row.document_id}
    described_or_existing = {
        row.document_id
        for row in rows
        if row.document_id and row.status in {"described", "skipped_existing"}
    }
    return sorted(described_or_existing - failed)
    write_document_status_outputs(
        Path(args.output_dir),
        processed_document_ids=processed_document_ids,
        failed_document_ids=failed_document_ids,
        no_image_document_ids=no_image_document_ids,
        partial_document_ids=partial_document_ids,
    )


def read_documents(connection: sqlite3.Connection, document_ids: list[int]) -> dict[int, tuple[str, str]]:
    if not document_ids:
        return {}
    placeholders = ",".join("?" for _ in document_ids)
    rows = connection.execute(
        f"select id, title, raw_path from documents where file_extension = '.pdf' and id in ({placeholders})",
        document_ids,
    ).fetchall()
    return {int(row[0]): (str(row[1] or ""), str(row[2] or "")) for row in rows if row[2]}


def read_existing_image_paths(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "select source_image_path from chunks where chunk_type = 'image_description' and source_image_path is not null"
    ).fetchall()
    return {str(row[0]) for row in rows}


def summarize(
    rows: list[StagingImageRow],
    selected_documents: int,
    processed_documents: int,
    failed_documents: int,
    *,
    run_started: float,
    provider: str,
    model_name: str,
) -> StagingSummary:
    return StagingSummary(
        selected_documents=selected_documents,
        processed_documents=processed_documents,
        failed_documents=failed_documents,
        extracted_images=sum(1 for row in rows if row.source_image_path),
        described_images=sum(1 for row in rows if row.status == "described"),
        skipped_existing_images=sum(1 for row in rows if row.status == "skipped_existing"),
        failed_images=sum(1 for row in rows if row.status == "failed" and row.source_image_path),
        elapsed_seconds=round(time.perf_counter() - run_started, 3),
        provider=provider,
        model_name=model_name,
    )


def maybe_write_outputs(
    rows: list[StagingImageRow],
    timing_events: list[TimingEvent],
    *,
    selected_documents: int,
    output_dir: str,
    checkpoint_every: int,
    run_started: float,
    provider: str,
    model_name: str,
) -> None:
    if checkpoint_every <= 0 or len(rows) % checkpoint_every != 0:
        return
    write_outputs(
        rows,
        timing_events,
        summarize(
            rows,
            selected_documents,
            processed_documents=0,
            failed_documents=0,
            run_started=run_started,
            provider=provider,
            model_name=model_name,
        ),
        Path(output_dir),
        announce=False,
    )


def write_outputs(
    rows: list[StagingImageRow],
    timing_events: list[TimingEvent],
    summary: StagingSummary,
    output_dir: Path,
    *,
    announce: bool = True,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "multimodal_staging.csv"
    summary_path = output_dir / "multimodal_staging_summary.json"
    timing_path = output_dir / "multimodal_timing.csv"
    atomic_write_csv(csv_path, STAGING_FIELDS, [asdict(row) for row in rows])
    atomic_write_csv(timing_path, TIMING_FIELDS, [asdict(event) for event in timing_events])
    atomic_write_text(summary_path, json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n")
    if announce:
        print(f"wrote {csv_path}")
        print(f"wrote {timing_path}")
        print(f"wrote {summary_path}")
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))


def build_vision_provider(settings, args):
    api_key = args.vision_api_key or settings.vision_model_api_key
    if args.vision_api_key_env:
        api_key = os.environ.get(args.vision_api_key_env, "")
    return create_vision_model_provider(
        provider_name=args.vision_provider or settings.vision_model_provider,
        model_name=args.vision_model_name or settings.vision_model_name,
        api_key=api_key,
        base_url=args.vision_base_url or settings.vision_model_base_url,
        timeout_seconds=args.vision_timeout_seconds or settings.vision_model_timeout_seconds,
    )


def atomic_write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    def write_temp(temp_path: Path) -> None:
        with temp_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    atomic_write(path, write_temp)


def atomic_write_text(path: Path, text: str) -> None:
    def write_temp(temp_path: Path) -> None:
        temp_path.write_text(text, encoding="utf-8")

    atomic_write(path, write_temp)


def atomic_write(path: Path, write_temp) -> None:
    last_error: OSError | None = None
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 6):
        temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{attempt}")
        try:
            write_temp(temp_path)
            temp_path.replace(path)
            return
        except OSError as exc:
            last_error = exc
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(0.2 * attempt)
    if last_error is not None:
        raise last_error


def write_document_status_outputs(
    output_dir: Path,
    *,
    processed_document_ids: list[int],
    failed_document_ids: list[int],
    no_image_document_ids: list[int],
    partial_document_ids: list[int],
) -> None:
    write_ids_file(output_dir / "processed_document_ids.txt", processed_document_ids)
    write_ids_file(output_dir / "failed_document_ids.txt", failed_document_ids)
    write_ids_file(output_dir / "no_image_document_ids.txt", no_image_document_ids)
    write_ids_file(output_dir / "partial_document_ids.txt", partial_document_ids)


def write_ids_file(path: Path, document_ids: list[int]) -> None:
    path.write_text(
        "\n".join(str(document_id) for document_id in document_ids) + ("\n" if document_ids else ""),
        encoding="utf-8",
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


if __name__ == "__main__":
    main()

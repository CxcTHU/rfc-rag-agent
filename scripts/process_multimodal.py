from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.models import Document  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.generation.vision_model import create_vision_model_provider  # noqa: E402
from app.services.ingestion.image_extractor import (  # noqa: E402
    PdfImageExtractionConfig,
    PdfImageExtractor,
)
from app.services.ingestion.multimodal_pipeline import MultimodalIngestionPipeline  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402


RESULT_FIELDS = [
    "document_id",
    "status",
    "extracted_images",
    "created_chunks",
    "skipped_images",
    "error",
]


@dataclass(frozen=True)
class ProcessMultimodalRow:
    document_id: int
    status: str
    extracted_images: int = 0
    created_chunks: int = 0
    skipped_images: int = 0
    error: str = ""


@dataclass(frozen=True)
class ProcessMultimodalSummary:
    selected_documents: int
    processed_documents: int
    failed_documents: int
    extracted_images: int
    created_chunks: int
    skipped_images: int


def main() -> None:
    parser = argparse.ArgumentParser(description="Process PDF images into image_description chunks.")
    parser.add_argument("--document-id", type=int, default=0, help="Process one document. 0 means all PDFs.")
    parser.add_argument("--document-ids-file", default="", help="Optional text file with one document id per line.")
    parser.add_argument("--image-output-dir", default="data/images")
    parser.add_argument("--min-width", type=int, default=100)
    parser.add_argument("--min-height", type=int, default=100)
    parser.add_argument("--max-page-area-ratio", type=float, default=0.70)
    parser.add_argument("--max-aspect-ratio", type=float, default=8.0)
    parser.add_argument(
        "--render-displayed-images",
        action="store_true",
        help="Render images from their displayed PDF page region to avoid raw-image rotation/orientation issues.",
    )
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of PDFs to process. 0 means no limit.")
    parser.add_argument("--offset", type=int, default=0, help="Skip this many PDFs from the ordered selection.")
    parser.add_argument("--only-existing-files", action="store_true", help="Skip DB rows whose raw_path is missing.")
    parser.add_argument("--output-dir", default="", help="Optional directory for CSV/JSON summary outputs.")
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=1,
        help="When --output-dir is set, refresh CSV/JSON after this many processed rows. 0 disables checkpoints.",
    )
    args = parser.parse_args()

    settings = get_settings()
    vision_provider = create_vision_model_provider(
        provider_name=settings.vision_model_provider,
        model_name=settings.vision_model_name,
        api_key=settings.vision_model_api_key,
        base_url=settings.vision_model_base_url,
        timeout_seconds=settings.vision_model_timeout_seconds,
    )
    embedding_provider = None
    if not args.skip_embeddings:
        embedding_provider = create_embedding_provider(
            provider_name=settings.embedding_provider or "deterministic",
            model_name=settings.embedding_model_name,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            dimension=settings.embedding_dimension or None,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=Path(args.image_output_dir),
            min_width=args.min_width,
            min_height=args.min_height,
            max_page_area_ratio=args.max_page_area_ratio,
            max_aspect_ratio=args.max_aspect_ratio,
            render_displayed_images=args.render_displayed_images,
        )
    )

    init_db()
    rows: list[ProcessMultimodalRow] = []
    with SessionLocal() as db:
        if args.document_ids_file:
            document_ids = read_document_ids_file(Path(args.document_ids_file))
        else:
            document_ids = select_document_ids(
                db,
                args.document_id,
                limit=args.limit,
                offset=args.offset,
                only_existing_files=args.only_existing_files,
            )
        for document_id in document_ids:
            try:
                result = MultimodalIngestionPipeline(
                    db=db,
                    image_extractor=extractor,
                    vision_provider=vision_provider,
                    embedding_provider=embedding_provider,
                ).process_document(document_id, build_embeddings=not args.skip_embeddings)
            except Exception as exc:  # noqa: BLE001 - keep batch processing alive
                db.rollback()
                error = sanitize_error(exc)
                rows.append(
                    ProcessMultimodalRow(
                        document_id=document_id,
                        status="failed",
                        error=error,
                    )
                )
                print(f"multimodal failed\tdocument_id={document_id}\terror={error}")
                maybe_write_checkpoint(rows, len(document_ids), args.output_dir, args.checkpoint_every)
                continue
            rows.append(
                ProcessMultimodalRow(
                    document_id=document_id,
                    status="processed",
                    extracted_images=result.extracted_images,
                    created_chunks=result.created_chunks,
                    skipped_images=result.skipped_images,
                )
            )
            print(
                "multimodal processed\t"
                f"document_id={result.document_id}\t"
                f"extracted_images={result.extracted_images}\t"
                f"created_chunks={result.created_chunks}\t"
                    f"skipped_images={result.skipped_images}"
            )
            maybe_write_checkpoint(rows, len(document_ids), args.output_dir, args.checkpoint_every)
    summary = summarize(rows, selected_documents=len(document_ids))
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))
    if args.output_dir:
        write_outputs(rows, summary, Path(args.output_dir))


def select_document_ids(
    db,
    document_id: int,
    *,
    limit: int = 0,
    offset: int = 0,
    only_existing_files: bool = False,
) -> list[int]:
    if document_id:
        return [document_id]
    statement = (
        select(Document.id, Document.raw_path)
        .where(Document.file_extension == ".pdf")
        .order_by(Document.id)
    )
    rows = db.execute(statement).all()
    document_ids: list[int] = []
    for value, raw_path in rows:
        if only_existing_files and not Path(str(raw_path or "")).exists():
            continue
        document_ids.append(int(value))
    if offset:
        document_ids = document_ids[offset:]
    if limit:
        document_ids = document_ids[:limit]
    return document_ids


def read_document_ids_file(path: Path) -> list[int]:
    ids: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lstrip("\ufeff")
        if not stripped or stripped.startswith("#"):
            continue
        ids.append(int(stripped))
    return ids


def summarize(rows: list[ProcessMultimodalRow], selected_documents: int) -> ProcessMultimodalSummary:
    return ProcessMultimodalSummary(
        selected_documents=selected_documents,
        processed_documents=sum(1 for row in rows if row.status == "processed"),
        failed_documents=sum(1 for row in rows if row.status == "failed"),
        extracted_images=sum(row.extracted_images for row in rows),
        created_chunks=sum(row.created_chunks for row in rows),
        skipped_images=sum(row.skipped_images for row in rows),
    )


def maybe_write_checkpoint(
    rows: list[ProcessMultimodalRow],
    selected_documents: int,
    output_dir: str,
    checkpoint_every: int,
) -> None:
    if not output_dir or checkpoint_every <= 0:
        return
    if len(rows) % checkpoint_every != 0:
        return
    write_outputs(
        rows,
        summarize(rows, selected_documents=selected_documents),
        Path(output_dir),
        announce=False,
    )


def sanitize_error(exc: Exception) -> str:
    text = str(exc)
    exc_name = type(exc).__name__
    if "余额不足" in text or "无可用资源包" in text:
        return f"{exc_name}: provider_quota_exhausted"
    if "HTTP 429" in text or "RateLimitError" in text:
        return f"{exc_name}: provider_rate_limited"
    if "timed out" in text.casefold() or "timeout" in text.casefold() or "WinError 10060" in text:
        return f"{exc_name}: provider_timeout"
    if "pixmap" in text.casefold():
        return f"{exc_name}: image_pixmap_conversion_failed"
    return f"{exc_name}: {text[:160]}"


def write_outputs(
    rows: list[ProcessMultimodalRow],
    summary: ProcessMultimodalSummary,
    output_dir: Path,
    *,
    announce: bool = True,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "process_multimodal_results.csv"
    summary_path = output_dir / "process_multimodal_summary.json"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    summary_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if announce:
        print(f"wrote {csv_path}")
        print(f"wrote {summary_path}")
    return csv_path, summary_path


if __name__ == "__main__":
    main()

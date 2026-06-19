"""Process Phase 45 cloud-candidate PDFs into image_description chunks."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.generation.vision_model import create_vision_model_provider  # noqa: E402
from app.services.ingestion.image_extractor import PdfImageExtractionConfig, PdfImageExtractor  # noqa: E402
from app.services.ingestion.multimodal_pipeline import MultimodalIngestionPipeline  # noqa: E402


DEFAULT_AUDIT_PATH = ROOT / "data" / "incoming" / "phase45_literature" / "phase12_quality_audit.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "incoming" / "phase45_literature"
RESULT_FIELDS = [
    "document_id",
    "title",
    "status",
    "extracted_images",
    "created_chunks",
    "skipped_images",
    "error",
]


@dataclass(frozen=True)
class Phase45MultimodalResult:
    document_id: int
    title: str
    status: str
    extracted_images: int = 0
    created_chunks: int = 0
    skipped_images: int = 0
    error: str = ""


@dataclass(frozen=True)
class Phase45MultimodalSummary:
    candidate_documents: int
    processed_documents: int
    failed_documents: int
    extracted_images: int
    created_chunks: int
    skipped_images: int


def read_candidate_rows(audit_path: Path) -> list[dict[str, str]]:
    with audit_path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            row
            for row in csv.DictReader(file)
            if row.get("review_status") == "cloud_candidate" and row.get("document_id")
        ]


def process_candidates(
    candidate_rows: list[dict[str, str]],
    image_output_dir: Path,
    min_width: int = 100,
    min_height: int = 100,
) -> tuple[Phase45MultimodalSummary, list[Phase45MultimodalResult]]:
    settings = get_settings()
    vision_provider = create_vision_model_provider(
        provider_name=settings.vision_model_provider,
        model_name=settings.vision_model_name,
        api_key=settings.vision_model_api_key,
        base_url=settings.vision_model_base_url,
        timeout_seconds=settings.vision_model_timeout_seconds,
    )
    extractor = PdfImageExtractor(
        PdfImageExtractionConfig(
            output_dir=image_output_dir,
            min_width=min_width,
            min_height=min_height,
        )
    )

    results: list[Phase45MultimodalResult] = []
    init_db()
    with SessionLocal() as db:
        pipeline = MultimodalIngestionPipeline(
            db=db,
            image_extractor=extractor,
            vision_provider=vision_provider,
            embedding_provider=None,
        )
        for row in candidate_rows:
            document_id = int(row["document_id"])
            title = row.get("title", "")
            try:
                result = pipeline.process_document(document_id, build_embeddings=False)
            except Exception as exc:  # noqa: BLE001 - keep batch alive
                results.append(
                    Phase45MultimodalResult(
                        document_id=document_id,
                        title=title,
                        status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            results.append(
                Phase45MultimodalResult(
                    document_id=document_id,
                    title=title,
                    status="processed",
                    extracted_images=result.extracted_images,
                    created_chunks=result.created_chunks,
                    skipped_images=result.skipped_images,
                )
            )

    summary = Phase45MultimodalSummary(
        candidate_documents=len(candidate_rows),
        processed_documents=sum(1 for result in results if result.status == "processed"),
        failed_documents=sum(1 for result in results if result.status == "failed"),
        extracted_images=sum(result.extracted_images for result in results),
        created_chunks=sum(result.created_chunks for result in results),
        skipped_images=sum(result.skipped_images for result in results),
    )
    return summary, results


def write_outputs(
    summary: Phase45MultimodalSummary,
    results: list[Phase45MultimodalResult],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "phase14_multimodal_summary.json"
    results_path = output_dir / "phase14_multimodal_results.csv"
    summary_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with results_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)
    return summary_path, results_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Process Phase 45 cloud-candidate PDF images.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--image-output-dir", default=str(ROOT / "data" / "images"))
    parser.add_argument("--min-width", type=int, default=100)
    parser.add_argument("--min-height", type=int, default=100)
    args = parser.parse_args()

    summary, results = process_candidates(
        read_candidate_rows(Path(args.audit)),
        image_output_dir=Path(args.image_output_dir),
        min_width=args.min_width,
        min_height=args.min_height,
    )
    summary_path, results_path = write_outputs(summary, results, Path(args.output_dir))
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))
    print(f"wrote {summary_path}")
    print(f"wrote {results_path}")


if __name__ == "__main__":
    main()

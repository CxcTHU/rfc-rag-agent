"""Audit Phase 45 orientation repair residuals before Phase 46 caption work."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.fix_phase45_orientation_images import fix_row
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_ALL_REVIEW_REPORT = (
    ROOT
    / "data"
    / "incoming"
    / "phase45_literature"
    / "phase45_orientation_fix_all_review"
    / "orientation_fix_report.csv"
)
DEFAULT_RETRY_REPORT = (
    ROOT
    / "data"
    / "incoming"
    / "phase45_literature"
    / "phase45_orientation_fix_doc1318_retry"
    / "orientation_fix_report.csv"
)
DEFAULT_MANIFEST = ROOT / "data" / "evaluation" / "phase46_image_quality_manifest.csv"
DEFAULT_CLEANUP_REPORT = ROOT / "data" / "evaluation" / "phase46_cleanup_report.csv"
DEFAULT_OUTPUT_CSV = ROOT / "data" / "evaluation" / "phase46_orientation_residual_candidates.csv"
DEFAULT_SUMMARY_JSON = ROOT / "data" / "evaluation" / "phase46_orientation_residual_summary.json"
DEFAULT_APPLY_OUTPUT_DIR = ROOT / "data" / "evaluation" / "phase46_orientation_residual_apply"
TYPE_AC = {"type_a", "type_c"}

REPORT_FIELDS = [
    "document_id",
    "chunk_id",
    "source_image_path",
    "phase45_status",
    "phase45_reason",
    "phase45_report",
    "phase46_classification",
    "cleanup_status",
    "current_chunk_id",
    "current_chunk_count",
    "current_embedding_count",
    "final_status",
    "audit_reason",
    "apply_status",
    "apply_error",
]


@dataclass(frozen=True)
class Phase45OrientationRow:
    document_id: int
    chunk_id: int
    source_image_path: str
    phase45_status: str
    phase45_reason: str
    phase45_report: str


@dataclass(frozen=True)
class ManifestInfo:
    classification: str
    chunk_id: int
    embedding_count: int


@dataclass(frozen=True)
class CleanupInfo:
    status: str
    deleted_chunk: int
    deleted_embeddings: int


@dataclass(frozen=True)
class DbImageInfo:
    chunk_ids: tuple[int, ...]
    embedding_count: int


@dataclass(frozen=True)
class AuditRow:
    document_id: int
    chunk_id: int
    source_image_path: str
    phase45_status: str
    phase45_reason: str
    phase45_report: str
    phase46_classification: str
    cleanup_status: str
    current_chunk_id: int
    current_chunk_count: int
    current_embedding_count: int
    final_status: str
    audit_reason: str
    apply_status: str = ""
    apply_error: str = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Phase 46 residual orientation candidates.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--all-review-report", default=str(DEFAULT_ALL_REVIEW_REPORT))
    parser.add_argument("--retry-report", action="append", default=[str(DEFAULT_RETRY_REPORT)])
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--cleanup-report", default=str(DEFAULT_CLEANUP_REPORT))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON))
    parser.add_argument("--apply-output-dir", default=str(DEFAULT_APPLY_OUTPUT_DIR))
    parser.add_argument("--zoom", type=float, default=2.0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    rows = load_phase45_rows(Path(args.all_review_report), [Path(path) for path in args.retry_report])
    manifest = load_manifest(Path(args.manifest))
    cleanup = load_cleanup_report(Path(args.cleanup_report))
    with sqlite3.connect(args.db_path, timeout=30) as connection:
        db_images = load_db_image_info(connection)
        audit_rows = audit_orientation_rows(rows, manifest, cleanup, db_images)
        if args.apply:
            audit_rows = apply_repairs(
                audit_rows,
                connection,
                output_dir=Path(args.apply_output_dir),
                zoom=args.zoom,
            )

    summary = summarize(audit_rows)
    write_audit(Path(args.output_csv), audit_rows)
    write_summary(Path(args.summary_json), summary)
    print("summary:", " ".join(f"{key}={value}" for key, value in summary.items()))
    print(f"wrote {args.output_csv}")
    print(f"wrote {args.summary_json}")


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def load_phase45_rows(all_review_report: Path, retry_reports: list[Path]) -> list[Phase45OrientationRow]:
    rows: dict[str, Phase45OrientationRow] = {}
    for row in read_phase45_report(all_review_report, "all_review"):
        rows[normalize_path(row.source_image_path)] = row
    for report_path in retry_reports:
        if report_path.exists():
            for row in read_phase45_report(report_path, report_path.parent.name):
                rows[normalize_path(row.source_image_path)] = row
    return list(rows.values())


def read_phase45_report(path: Path, label: str) -> list[Phase45OrientationRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            Phase45OrientationRow(
                document_id=int(row.get("document_id") or 0),
                chunk_id=int(row.get("chunk_id") or 0),
                source_image_path=normalize_path(row.get("source_image_path") or ""),
                phase45_status=row.get("status") or "",
                phase45_reason=row.get("reason") or "",
                phase45_report=label,
            )
            for row in csv.DictReader(file)
        ]


def load_manifest(path: Path) -> dict[str, ManifestInfo]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {
            normalize_path(row.get("source_image_path") or ""): ManifestInfo(
                classification=row.get("classification") or "",
                chunk_id=int(row.get("chunk_id") or 0),
                embedding_count=int(row.get("embedding_count") or 0),
            )
            for row in csv.DictReader(file)
        }


def load_cleanup_report(path: Path) -> dict[str, CleanupInfo]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {
            normalize_path(row.get("source_image_path") or ""): CleanupInfo(
                status=row.get("status") or "",
                deleted_chunk=int(row.get("deleted_chunk") or 0),
                deleted_embeddings=int(row.get("deleted_embeddings") or 0),
            )
            for row in csv.DictReader(file)
        }


def load_db_image_info(connection: sqlite3.Connection) -> dict[str, DbImageInfo]:
    db_rows = connection.execute(
        """
        select c.source_image_path, c.id, count(e.id)
        from chunks c
        left join chunk_embeddings e on e.chunk_id = c.id
        where c.chunk_type = 'image_description'
          and c.source_image_path is not null
          and c.source_image_path != ''
        group by c.source_image_path, c.id
        order by c.source_image_path, c.id
        """
    ).fetchall()
    grouped: dict[str, list[tuple[int, int]]] = {}
    for source_image_path, chunk_id, embedding_count in db_rows:
        grouped.setdefault(normalize_path(str(source_image_path)), []).append(
            (int(chunk_id), int(embedding_count or 0))
        )
    return {
        path: DbImageInfo(
            chunk_ids=tuple(chunk_id for chunk_id, _ in values),
            embedding_count=sum(embedding_count for _, embedding_count in values),
        )
        for path, values in grouped.items()
    }


def audit_orientation_rows(
    rows: list[Phase45OrientationRow],
    manifest: dict[str, ManifestInfo],
    cleanup: dict[str, CleanupInfo],
    db_images: dict[str, DbImageInfo],
) -> list[AuditRow]:
    return [
        audit_orientation_row(row, manifest.get(row.source_image_path), cleanup.get(row.source_image_path), db_images.get(row.source_image_path))
        for row in rows
    ]


def audit_orientation_row(
    row: Phase45OrientationRow,
    manifest_info: ManifestInfo | None,
    cleanup_info: CleanupInfo | None,
    db_info: DbImageInfo | None,
) -> AuditRow:
    classification = manifest_info.classification if manifest_info else ""
    cleanup_status = cleanup_info.status if cleanup_info else ""
    chunk_ids = db_info.chunk_ids if db_info else ()
    current_chunk_count = len(chunk_ids)
    current_embedding_count = db_info.embedding_count if db_info else 0
    current_chunk_id = chunk_ids[0] if chunk_ids else 0

    if row.phase45_status == "fixed":
        final_status = "fixed"
        audit_reason = "phase45_repair_fixed"
    elif current_chunk_count > 0 and current_embedding_count > 0 and classification not in TYPE_AC:
        final_status = "still_candidate"
        audit_reason = "failed_phase45_repair_still_has_chunk_embedding_and_not_type_a_c"
    elif classification in TYPE_AC and current_chunk_count == 0 and current_embedding_count == 0:
        final_status = "resolved_by_cleanup"
        audit_reason = f"phase46_{classification}_cleanup_removed_chunk_embedding"
    elif current_chunk_count == 0 and current_embedding_count == 0:
        final_status = "resolved_by_cleanup"
        audit_reason = "no_current_image_chunk_embedding"
    else:
        final_status = "failed"
        audit_reason = "unresolved_inconsistent_cleanup_state"

    return AuditRow(
        document_id=row.document_id,
        chunk_id=row.chunk_id,
        source_image_path=row.source_image_path,
        phase45_status=row.phase45_status,
        phase45_reason=row.phase45_reason,
        phase45_report=row.phase45_report,
        phase46_classification=classification,
        cleanup_status=cleanup_status,
        current_chunk_id=current_chunk_id,
        current_chunk_count=current_chunk_count,
        current_embedding_count=current_embedding_count,
        final_status=final_status,
        audit_reason=audit_reason,
    )


def apply_repairs(
    rows: list[AuditRow],
    connection: sqlite3.Connection,
    *,
    output_dir: Path,
    zoom: float,
) -> list[AuditRow]:
    repaired_rows: list[AuditRow] = []
    for row in rows:
        if row.final_status != "still_candidate":
            repaired_rows.append(row)
            continue
        fix_result = fix_row(
            {
                "chunk_id": str(row.current_chunk_id or row.chunk_id),
                "document_id": str(row.document_id),
                "source_image_path": row.source_image_path,
                "reason": "phase46_orientation_residual_repair",
            },
            connection,
            output_dir=output_dir,
            zoom=zoom,
            apply=True,
        )
        final_status = "fixed" if fix_result.status == "fixed" else "failed"
        repaired_rows.append(
            AuditRow(
                **{
                    **asdict(row),
                    "final_status": final_status,
                    "audit_reason": "phase46_apply_repair" if final_status == "fixed" else row.audit_reason,
                    "apply_status": fix_result.status,
                    "apply_error": fix_result.error,
                }
            )
        )
    return repaired_rows


def summarize(rows: list[AuditRow]) -> dict[str, int]:
    return {
        "candidates_total": len(rows),
        "fixed": sum(1 for row in rows if row.final_status == "fixed"),
        "cleanup_resolved": sum(1 for row in rows if row.final_status == "resolved_by_cleanup"),
        "still_candidate": sum(1 for row in rows if row.final_status == "still_candidate"),
        "failed": sum(1 for row in rows if row.final_status == "failed"),
        "phase45_original_failed": sum(1 for row in rows if row.phase45_status == "failed"),
    }


def write_audit(path: Path, rows: list[AuditRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def write_summary(path: Path, summary: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

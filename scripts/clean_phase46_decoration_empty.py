"""Clean Phase 46 type_a/type_c image artifacts from the manifest."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_MANIFEST = ROOT / "data" / "evaluation" / "phase46_image_quality_manifest.csv"
DEFAULT_REPORT = ROOT / "data" / "evaluation" / "phase46_cleanup_report.csv"
DEFAULT_IMAGE_DIR = ROOT / "data" / "images"
REPORT_FIELDS = [
    "document_id",
    "chunk_id",
    "source_image_path",
    "classification",
    "status",
    "deleted_chunk",
    "deleted_embeddings",
    "deleted_file",
    "error",
]


@dataclass(frozen=True)
class CleanupTarget:
    document_id: int
    chunk_id: int
    source_image_path: str
    classification: str


@dataclass(frozen=True)
class CleanupReportRow:
    document_id: int
    chunk_id: int
    source_image_path: str
    classification: str
    status: str
    deleted_chunk: int
    deleted_embeddings: int
    deleted_file: int
    error: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean Phase 46 type_a/type_c images.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--image-dir", default=str(DEFAULT_IMAGE_DIR))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    targets = read_targets(Path(args.manifest))
    with sqlite3.connect(args.db_path) as connection:
        report_rows = clean_targets(
            connection,
            targets,
            image_dir=Path(args.image_dir),
            root=ROOT,
            apply=args.apply,
        )
    write_report(Path(args.report), report_rows)
    print(
        "summary:",
        f"targets={len(targets)}",
        f"deleted_chunks={sum(row.deleted_chunk for row in report_rows)}",
        f"deleted_embeddings={sum(row.deleted_embeddings for row in report_rows)}",
        f"deleted_files={sum(row.deleted_file for row in report_rows)}",
        f"dry_run={not args.apply}",
    )
    print(f"wrote {args.report}")


def read_targets(manifest_path: Path) -> list[CleanupTarget]:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        targets = [
            CleanupTarget(
                document_id=int(row.get("document_id") or 0),
                chunk_id=int(row.get("chunk_id") or 0),
                source_image_path=str(row.get("source_image_path") or ""),
                classification=str(row.get("classification") or ""),
            )
            for row in rows
            if row.get("classification") in {"type_a", "type_c"}
        ]
    return targets


def clean_targets(
    connection: sqlite3.Connection,
    targets: list[CleanupTarget],
    *,
    image_dir: Path,
    root: Path = ROOT,
    apply: bool,
) -> list[CleanupReportRow]:
    report_rows: list[CleanupReportRow] = []
    try:
        for target in targets:
            report_rows.append(clean_target(connection, target, image_dir=image_dir, root=root, apply=apply))
        if apply:
            connection.commit()
    except Exception:
        if apply:
            connection.rollback()
        raise
    return report_rows


def clean_target(
    connection: sqlite3.Connection,
    target: CleanupTarget,
    *,
    image_dir: Path,
    root: Path,
    apply: bool,
) -> CleanupReportRow:
    deleted_chunk = deleted_embeddings = deleted_file = 0
    try:
        if not apply:
            return report(target, "dry_run", 0, 0, 0, "")
        if target.chunk_id > 0:
            deleted_embeddings = int(
                connection.execute(
                    "delete from chunk_embeddings where chunk_id = ?",
                    (target.chunk_id,),
                ).rowcount
                or 0
            )
            deleted_chunk = int(
                connection.execute(
                    "delete from chunks where id = ? and chunk_type = 'image_description'",
                    (target.chunk_id,),
                ).rowcount
                or 0
            )
        if target.classification == "type_c" and target.source_image_path:
            image_path = resolve_safe_image_path(target.source_image_path, image_dir=image_dir, root=root)
            if image_path.exists():
                image_path.unlink()
                deleted_file = 1
        return report(target, "cleaned", deleted_chunk, deleted_embeddings, deleted_file, "")
    except Exception as exc:  # noqa: BLE001 - keep per-row report complete.
        return report(target, "failed", deleted_chunk, deleted_embeddings, deleted_file, f"{type(exc).__name__}: {exc}")


def resolve_safe_image_path(source_image_path: str, *, image_dir: Path, root: Path) -> Path:
    path = Path(source_image_path)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    allowed = image_dir.resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError(f"refusing to delete outside image dir: {source_image_path}")
    return resolved


def report(
    target: CleanupTarget,
    status: str,
    deleted_chunk: int,
    deleted_embeddings: int,
    deleted_file: int,
    error: str,
) -> CleanupReportRow:
    return CleanupReportRow(
        document_id=target.document_id,
        chunk_id=target.chunk_id,
        source_image_path=target.source_image_path,
        classification=target.classification,
        status=status,
        deleted_chunk=deleted_chunk,
        deleted_embeddings=deleted_embeddings,
        deleted_file=deleted_file,
        error=error,
    )


def write_report(path: Path, rows: list[CleanupReportRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


if __name__ == "__main__":
    main()

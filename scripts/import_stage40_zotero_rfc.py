from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.service import (  # noqa: E402
    EmptyDocumentError,
    IngestionConfig,
    IngestionService,
)


def match_rfc_filename(name: str) -> str:
    lowered = name.casefold()
    normalized = lowered.replace("_", " ").replace("-", " ")
    if "堆石" in name:
        return "堆石"
    if "rock-filled" in lowered or "rock filled" in lowered:
        return "rock-filled"
    if ("rock-fill" in lowered or "rockfill" in lowered) and (
        "dam" in lowered or "concrete" in lowered
    ):
        return "rock-fill/rockfill+dam/concrete"
    if "stone-concrete" in lowered and ("dam" in lowered or "rockfill" in lowered):
        return "stone-concrete+dam"
    scc_context = (
        "concrete" in lowered
        or "rock" in lowered
        or "aggregate" in lowered
    )
    if (
        "scc" in lowered
        or "self compact" in normalized
        or "self-compacting" in lowered
    ) and scc_context:
        return "SCC/self-compacting concrete"
    return ""


def collect_zotero_pdfs(storage_dir: Path) -> list[Path]:
    pdfs: list[Path] = []
    with os.scandir(storage_dir) as entries:
        for entry in entries:
            if not entry.is_dir():
                continue
            try:
                with os.scandir(entry.path) as children:
                    for child in children:
                        if child.is_file() and child.name.casefold().endswith(".pdf"):
                            pdfs.append(Path(child.path))
            except OSError:
                continue
    return sorted(pdfs, key=lambda path: str(path).casefold())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Phase 40 RFC-related PDFs from Zotero storage."
    )
    parser.add_argument("--storage-dir", required=True)
    parser.add_argument("--source-type", default="open_access_pdf")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    storage_dir = Path(args.storage_dir)
    if not storage_dir.is_dir():
        raise SystemExit(f"storage directory not found: {storage_dir}")

    pdfs = collect_zotero_pdfs(storage_dir)
    matches = [(path, match_rfc_filename(path.name)) for path in pdfs]
    matches = [(path, reason) for path, reason in matches if reason]

    print(f"scanned_pdfs={len(pdfs)}", flush=True)
    print(f"matched_pdfs={len(matches)}", flush=True)
    for index, (path, reason) in enumerate(matches, start=1):
        print(f"{index:02d}. [{reason}] {path}", flush=True)

    if args.dry_run:
        print("dry-run: no import performed.", flush=True)
        return

    init_db()
    imported = duplicate = empty = failed = 0
    total_new_chunks = 0
    failures: list[tuple[str, str]] = []

    with SessionLocal() as db:
        service = IngestionService(
            db,
            IngestionConfig(
                raw_dir=args.raw_dir,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            ),
        )
        for index, (path, _reason) in enumerate(matches, start=1):
            try:
                result = service.import_document(
                    path,
                    title=path.stem,
                    source_path=str(path),
                    file_name=path.name,
                    source_type=args.source_type,
                )
            except EmptyDocumentError:
                db.rollback()
                empty += 1
                failures.append((path.name, "EmptyDocumentError"))
                print(f"[{index}/{len(matches)}] empty: {path.name}", flush=True)
                continue
            except Exception as exc:  # noqa: BLE001 - keep batch import alive
                db.rollback()
                failed += 1
                failures.append((path.name, f"{type(exc).__name__}: {exc}"))
                print(
                    f"[{index}/{len(matches)}] failed: {path.name}: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                continue

            if result.status == "duplicate":
                duplicate += 1
                print(f"[{index}/{len(matches)}] duplicate: {path.name}", flush=True)
            else:
                imported += 1
                total_new_chunks += result.chunk_count
                print(
                    f"[{index}/{len(matches)}] imported chunks={result.chunk_count}: "
                    f"{path.name}",
                    flush=True,
                )

    print("=" * 60, flush=True)
    print(f"matched PDFs         : {len(matches)}", flush=True)
    print(f"newly imported       : {imported} (chunks={total_new_chunks})", flush=True)
    print(f"duplicate (skipped)  : {duplicate}", flush=True)
    print(f"empty (no text)      : {empty}", flush=True)
    print(f"failed               : {failed}", flush=True)
    if failures:
        print("--- failures ---", flush=True)
        for name, error in failures:
            print(f"  {name}: {error}", flush=True)


if __name__ == "__main__":
    main()

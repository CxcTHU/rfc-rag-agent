"""Split unfinished Phase 45 PDF multimodal jobs into stable id queues."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_INPUT_DIR = ROOT / "data" / "incoming" / "phase45_literature"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "phase22_queue_feasibility"
DEFAULT_RESULT_PATHS = [
    DEFAULT_INPUT_DIR / "phase21_multimodal_100" / "process_multimodal_results.csv",
    DEFAULT_INPUT_DIR / "phase21_multimodal_100_retry_zhipu" / "process_multimodal_results.csv",
    DEFAULT_INPUT_DIR / "phase22_multimodal_all_zhipu" / "process_multimodal_results.csv",
    DEFAULT_INPUT_DIR / "phase21_remaining_3_zhipu" / "process_multimodal_results.csv",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify unfinished multimodal PDF jobs into three queues.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--completed-document-ids-file",
        action="append",
        default=[],
        help="Additional newline-delimited document ids already processed by staging, including no-image PDFs.",
    )
    parser.add_argument(
        "--include-staging-processed",
        action="store_true",
        help="Recursively include processed_document_ids.txt files under the Phase 45 incoming directory.",
    )
    parser.add_argument(
        "--partial-document-ids-file",
        action="append",
        default=[],
        help="Newline-delimited document ids from interrupted staging runs; image chunks alone do not complete them.",
    )
    parser.add_argument(
        "--include-staging-partial",
        action="store_true",
        help="Recursively include partial_document_ids.txt files under the Phase 45 incoming directory.",
    )
    parser.add_argument(
        "--isolate-known-failures",
        action="store_true",
        help="Exclude known timeout/non-timeout failures from main queues and write them to separate files.",
    )
    args = parser.parse_args()

    latest = read_latest_status(DEFAULT_RESULT_PATHS)
    all_pdf_ids = read_pdf_document_ids(Path(args.db_path))
    image_description_document_ids = read_image_description_document_ids(Path(args.db_path))
    completed_id_files = [Path(value) for value in args.completed_document_ids_file]
    if args.include_staging_processed:
        completed_id_files.extend(sorted(DEFAULT_INPUT_DIR.glob("**/processed_document_ids.txt")))
    extra_completed_document_ids = read_document_ids_files(completed_id_files)
    partial_id_files = [Path(value) for value in args.partial_document_ids_file]
    if args.include_staging_partial:
        partial_id_files.extend(sorted(DEFAULT_INPUT_DIR.glob("**/partial_document_ids.txt")))
    partial_document_ids = read_document_ids_files(partial_id_files)
    legacy_completed = {doc_id for doc_id, row in latest.items() if row.get("status") == "processed"}
    legacy_completed.update(image_description_document_ids)
    completed = (legacy_completed - partial_document_ids) | extra_completed_document_ids
    failed_timeout = {
        doc_id
        for doc_id, row in latest.items()
        if row.get("status") == "failed" and "provider_timeout" in row.get("error", "")
    }
    failed_other = {
        doc_id
        for doc_id, row in latest.items()
        if row.get("status") == "failed" and "provider_timeout" not in row.get("error", "")
    }
    known_failures = failed_timeout | failed_other
    unfinished = [doc_id for doc_id in all_pdf_ids if doc_id not in completed]
    main_queue_document_ids = isolate_known_failures(unfinished, known_failures, args.isolate_known_failures)
    queues = split_three_queues(main_queue_document_ids)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, ids in queues.items():
        (output_dir / f"{name}_document_ids.txt").write_text(
            "\n".join(str(value) for value in ids) + ("\n" if ids else ""),
            encoding="utf-8",
        )
    isolated_timeout = [doc_id for doc_id in unfinished if doc_id in failed_timeout]
    isolated_non_timeout = [doc_id for doc_id in unfinished if doc_id in failed_other]
    if args.isolate_known_failures:
        (output_dir / "timeout_long_tail_document_ids.txt").write_text(
            "\n".join(str(value) for value in isolated_timeout) + ("\n" if isolated_timeout else ""),
            encoding="utf-8",
        )
        (output_dir / "non_timeout_failed_document_ids.txt").write_text(
            "\n".join(str(value) for value in isolated_non_timeout) + ("\n" if isolated_non_timeout else ""),
            encoding="utf-8",
        )
    summary = {
        "all_pdf_documents_with_raw_path": len(all_pdf_ids),
        "already_processed_documents_from_latest_csv": len(completed),
        "extra_completed_documents_from_id_files": len(extra_completed_document_ids),
        "partial_documents_from_id_files": len(partial_document_ids),
        "unfinished_documents": len(unfinished),
        "main_queue_documents": len(main_queue_document_ids),
        "known_timeout_documents": sorted(failed_timeout),
        "known_non_timeout_failed_documents": sorted(failed_other),
        "isolated_timeout_documents": isolated_timeout if args.isolate_known_failures else [],
        "isolated_non_timeout_failed_documents": isolated_non_timeout if args.isolate_known_failures else [],
        "queues": {
            name: {"count": len(ids), "first_ids": ids[:10], "last_ids": ids[-10:]}
            for name, ids in queues.items()
        },
    }
    (output_dir / "queue_split_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def read_latest_status(paths: list[Path]) -> dict[int, dict[str, str]]:
    latest: dict[int, dict[str, str]] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                latest[int(row["document_id"])] = row
    return latest


def read_pdf_document_ids(db_path: Path) -> list[int]:
    with sqlite3.connect(db_path, timeout=5) as connection:
        rows = connection.execute("select id, file_extension, raw_path from documents order by id").fetchall()
    return [int(row[0]) for row in rows if row[1] == ".pdf" and row[2]]


def read_image_description_document_ids(db_path: Path) -> set[int]:
    with sqlite3.connect(db_path, timeout=5) as connection:
        rows = connection.execute(
            "select distinct document_id from chunks where chunk_type = 'image_description'"
        ).fetchall()
    return {int(row[0]) for row in rows}


def read_document_ids_files(paths: list[Path]) -> set[int]:
    document_ids: set[int] = set()
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            value = line.strip()
            if value:
                document_ids.add(int(value))
    return document_ids


def split_three_queues(document_ids: list[int]) -> dict[str, list[int]]:
    queues: dict[str, list[int]] = {
        "official_a": [],
        "official_b": [],
        "paratera_c": [],
    }
    for index, document_id in enumerate(document_ids):
        if index % 3 == 0:
            queues["official_a"].append(document_id)
        elif index % 3 == 1:
            queues["official_b"].append(document_id)
        else:
            queues["paratera_c"].append(document_id)
    return queues


def isolate_known_failures(
    document_ids: list[int],
    known_failures: set[int],
    enabled: bool,
) -> list[int]:
    if not enabled:
        return document_ids
    return [document_id for document_id in document_ids if document_id not in known_failures]


if __name__ == "__main__":
    main()

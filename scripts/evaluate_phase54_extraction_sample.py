from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_database_engine
from app.services.graphrag.extractor import GraphRAGTripleExtractor
try:
    from scripts.extract_phase53_graphrag_triples import (
        build_planner_extractor,
        extract_selected_chunks_to_rows,
        select_diverse_chunks,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    from extract_phase53_graphrag_triples import (
        build_planner_extractor,
        extract_selected_chunks_to_rows,
        select_diverse_chunks,
    )


def entity_key(entity: dict[str, Any]) -> tuple[str, str]:
    return (
        str(entity.get("type") or "").strip(),
        str(entity.get("normalized_name") or entity.get("name") or "").strip().casefold(),
    )


def relation_key(relation: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(relation.get("subject") or "").strip().casefold(),
        str(relation.get("predicate") or "").strip(),
        str(relation.get("object") or "").strip().casefold(),
    )


def count_types(rows: list[dict[str, Any]], field: str, type_field: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for item in row.get(field) or ():
            if isinstance(item, dict):
                counts[str(item.get(type_field) or "unknown")] += 1
    return counts


def overlap_metrics(
    llm_rows: list[dict[str, Any]],
    regex_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    regex_by_chunk = {str(row.get("chunk_id")): row for row in regex_rows}
    llm_entity_total = 0
    regex_entity_total = 0
    entity_overlap = 0
    llm_relation_total = 0
    regex_relation_total = 0
    relation_overlap = 0

    for llm_row in llm_rows:
        regex_row = regex_by_chunk.get(str(llm_row.get("chunk_id")), {})
        llm_entities = {entity_key(item) for item in llm_row.get("entities") or () if isinstance(item, dict)}
        regex_entities = {
            entity_key(item) for item in regex_row.get("entities") or () if isinstance(item, dict)
        }
        llm_relations = {
            relation_key(item) for item in llm_row.get("relations") or () if isinstance(item, dict)
        }
        regex_relations = {
            relation_key(item) for item in regex_row.get("relations") or () if isinstance(item, dict)
        }
        llm_entity_total += len(llm_entities)
        regex_entity_total += len(regex_entities)
        entity_overlap += len(llm_entities & regex_entities)
        llm_relation_total += len(llm_relations)
        regex_relation_total += len(regex_relations)
        relation_overlap += len(llm_relations & regex_relations)

    return {
        "llm_rows": len(llm_rows),
        "regex_rows": len(regex_rows),
        "llm_error_rows": sum(1 for row in llm_rows if row.get("status") == "error"),
        "regex_error_rows": sum(1 for row in regex_rows if row.get("status") == "error"),
        "llm_entity_total": llm_entity_total,
        "regex_entity_total": regex_entity_total,
        "entity_overlap": entity_overlap,
        "entity_overlap_precision_proxy": safe_ratio(entity_overlap, llm_entity_total),
        "entity_overlap_recall_proxy": safe_ratio(entity_overlap, regex_entity_total),
        "llm_relation_total": llm_relation_total,
        "regex_relation_total": regex_relation_total,
        "relation_overlap": relation_overlap,
        "relation_overlap_precision_proxy": safe_ratio(relation_overlap, llm_relation_total),
        "relation_overlap_recall_proxy": safe_ratio(relation_overlap, regex_relation_total),
    }


def safe_ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0000"
    return f"{numerator / denominator:.4f}"


def write_json_payload(
    path: Path,
    *,
    rows: list[dict[str, Any]],
    phase: str,
    execute_llm: bool,
    chunk_type: str,
    limit: int,
    seed: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phase": phase,
            "execute_llm": execute_llm,
            "chunk_type": chunk_type,
            "limit": limit,
            "seed": seed,
            "row_count": len(rows),
            "safety": "sanitized derived extraction rows only",
        },
        "rows": rows,
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    temp_path = path.with_name(f"{path.name}.tmp")
    for attempt in range(1, 4):
        try:
            temp_path.write_text(serialized, encoding="utf-8")
            temp_path.replace(path)
            return
        except OSError:
            if attempt >= 3:
                raise
            time.sleep(0.2 * attempt)


def load_existing_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def extract_rows_incremental(
    chunks,
    *,
    extractor,
    execute_llm: bool,
    output_path: Path,
    phase: str,
    chunk_type: str,
    limit: int,
    seed: int,
    batch_size: int,
    resume: bool,
) -> list[dict[str, Any]]:
    selected_chunk_ids = {str(chunk_pair[0].id) for chunk_pair in chunks}
    selected_chunk_id_order = [str(chunk_pair[0].id) for chunk_pair in chunks]
    loaded_rows = load_existing_rows(output_path) if resume else []
    rows_by_chunk_id = {
        str(row.get("chunk_id")): row
        for row in loaded_rows
        if str(row.get("chunk_id")) in selected_chunk_ids
    }
    rows = [rows_by_chunk_id[chunk_id] for chunk_id in selected_chunk_id_order if chunk_id in rows_by_chunk_id]
    completed_chunk_ids = {str(row.get("chunk_id")) for row in rows}
    pending = [row for row in chunks if str(row[0].id) not in completed_chunk_ids]
    if rows:
        print(f"resume {output_path}: completed={len(rows)} pending={len(pending)}")
    effective_batch_size = max(1, batch_size)
    for start in range(0, len(pending), effective_batch_size):
        batch = pending[start : start + effective_batch_size]
        if effective_batch_size == 1:
            batch_rows = [
                extract_selected_chunks_to_rows(
                    [chunk_pair],
                    extractor=extractor,
                    execute_llm=execute_llm,
                )[0]
                for chunk_pair in batch
            ]
        else:
            with ThreadPoolExecutor(max_workers=effective_batch_size) as executor:
                futures = [
                    executor.submit(
                        extract_selected_chunks_to_rows,
                        [chunk_pair],
                        extractor=extractor,
                        execute_llm=execute_llm,
                    )
                    for chunk_pair in batch
                ]
                batch_rows = []
                for future in as_completed(futures):
                    batch_rows.extend(future.result())
                    rows.extend(batch_rows[-1:])
                    write_json_payload(
                        output_path,
                        rows=rows,
                        phase=phase,
                        execute_llm=execute_llm,
                        chunk_type=chunk_type,
                        limit=limit,
                        seed=seed,
                    )
                    print(f"wrote {len(rows)} rows to {output_path}")
        if effective_batch_size == 1:
            rows.extend(batch_rows)
            write_json_payload(
                output_path,
                rows=rows,
                phase=phase,
                execute_llm=execute_llm,
                chunk_type=chunk_type,
                limit=limit,
                seed=seed,
            )
            print(f"wrote {len(rows)} rows to {output_path}")
    write_json_payload(
        output_path,
        rows=rows,
        phase=phase,
        execute_llm=execute_llm,
        chunk_type=chunk_type,
        limit=limit,
        seed=seed,
    )
    return rows


def write_quality_csv(
    path: Path,
    *,
    metrics: dict[str, Any],
    llm_rows: list[dict[str, Any]],
    regex_rows: list[dict[str, Any]],
    execute_llm: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entity_counts = count_types(llm_rows, "entities", "type")
    relation_counts = count_types(llm_rows, "relations", "predicate")
    regex_entity_counts = count_types(regex_rows, "entities", "type")
    regex_relation_counts = count_types(regex_rows, "relations", "predicate")
    rows: list[dict[str, Any]] = [
        {
            "section": "summary",
            "metric": key,
            "value": value,
            "notes": "real_llm" if execute_llm else "dry_run_no_llm",
        }
        for key, value in metrics.items()
    ]
    for name, value in sorted(entity_counts.items()):
        rows.append({"section": "llm_entity_type", "metric": name, "value": value, "notes": ""})
    for name, value in sorted(relation_counts.items()):
        rows.append({"section": "llm_relation_type", "metric": name, "value": value, "notes": ""})
    for name, value in sorted(regex_entity_counts.items()):
        rows.append({"section": "regex_entity_type", "metric": name, "value": value, "notes": ""})
    for name, value in sorted(regex_relation_counts.items()):
        rows.append({"section": "regex_relation_type", "metric": name, "value": value, "notes": ""})
    rows.append(
        {
            "section": "manual_review_gate",
            "metric": "required_sample_size",
            "value": 20,
            "notes": "Fill manual review CSV before accepting Phase 54A quality gate.",
        }
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "metric", "value", "notes"])
        writer.writeheader()
        writer.writerows(rows)


def write_manual_review_csv(
    path: Path,
    *,
    llm_rows: list[dict[str, Any]],
    regex_rows: list[dict[str, Any]],
    sample_size: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    regex_by_chunk = {str(row.get("chunk_id")): row for row in regex_rows}
    fields = [
        "chunk_id",
        "document_id",
        "document_title",
        "heading_bucket",
        "llm_entity_count",
        "llm_relation_count",
        "regex_entity_count",
        "regex_relation_count",
        "entity_precision_manual",
        "relation_precision_manual",
        "review_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in llm_rows[:sample_size]:
            regex_row = regex_by_chunk.get(str(row.get("chunk_id")), {})
            writer.writerow(
                {
                    "chunk_id": row.get("chunk_id", ""),
                    "document_id": row.get("document_id", ""),
                    "document_title": row.get("document_title", ""),
                    "heading_bucket": (row.get("metadata") or {}).get("heading_bucket", ""),
                    "llm_entity_count": len(row.get("entities") or ()),
                    "llm_relation_count": len(row.get("relations") or ()),
                    "regex_entity_count": len(regex_row.get("entities") or ()),
                    "regex_relation_count": len(regex_row.get("relations") or ()),
                    "entity_precision_manual": "",
                    "relation_precision_manual": "",
                    "review_notes": "",
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 54A GraphRAG extraction sample quality.")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--seed", type=int, default=54)
    parser.add_argument("--chunk-type", default="text")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--llm-output", default="data/evaluation/phase54_extraction_sample_llm.json")
    parser.add_argument("--regex-output", default="data/evaluation/phase54_extraction_sample_regex.json")
    parser.add_argument("--quality-output", default="data/evaluation/phase54_extraction_sample_quality.csv")
    parser.add_argument(
        "--manual-review-output",
        default="data/evaluation/phase54_extraction_manual_review.csv",
    )
    parser.add_argument("--manual-review-size", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--max-attempts", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Call the configured PLANNER_CHAT_MODEL_* provider for the LLM extraction lane.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    database_url = args.database_url or settings.database_url
    engine = create_database_engine(database_url)

    with Session(engine) as db:
        chunks = select_diverse_chunks(
            db,
            limit=args.limit,
            chunk_type=args.chunk_type,
            seed=args.seed,
        )
        llm_rows = extract_rows_incremental(
            chunks,
            extractor=build_planner_extractor(
                execute_llm=args.execute,
                timeout_seconds=args.timeout_seconds,
                max_attempts=args.max_attempts,
            ),
            execute_llm=args.execute,
            output_path=Path(args.llm_output),
            phase="54A",
            chunk_type=args.chunk_type,
            limit=args.limit,
            seed=args.seed,
            batch_size=args.batch_size,
            resume=args.resume,
        )
        regex_rows = extract_selected_chunks_to_rows(
            chunks,
            extractor=GraphRAGTripleExtractor(),
            execute_llm=False,
        )

    write_json_payload(
        Path(args.regex_output),
        rows=regex_rows,
        phase="54A",
        execute_llm=False,
        chunk_type=args.chunk_type,
        limit=args.limit,
        seed=args.seed,
    )
    metrics = overlap_metrics(llm_rows, regex_rows)
    write_quality_csv(
        Path(args.quality_output),
        metrics=metrics,
        llm_rows=llm_rows,
        regex_rows=regex_rows,
        execute_llm=args.execute,
    )
    write_manual_review_csv(
        Path(args.manual_review_output),
        llm_rows=llm_rows,
        regex_rows=regex_rows,
        sample_size=args.manual_review_size,
    )
    print(
        "phase54_extraction_sample "
        f"rows={len(llm_rows)} execute={args.execute} "
        f"llm_errors={metrics['llm_error_rows']} "
        f"quality={args.quality_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

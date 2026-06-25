from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Chunk, Document
from app.db.session import create_database_engine
from app.services.graphrag.schema import (
    GraphExtractionResult,
    deduplicate_entities,
    deduplicate_relations,
)

HIGH_VALUE_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("rock-filled concrete", 50),
    ("堆石混凝土", 50),
    ("rfc", 40),
    ("self-compacting concrete", 30),
    ("scc", 25),
    ("compressive strength", 25),
    ("strength", 14),
    ("slump", 18),
    ("water-cement", 18),
    ("water cement", 18),
    ("cement content", 18),
    ("permeability", 18),
    ("temperature", 12),
    ("curing", 12),
    ("mix proportion", 18),
    ("aggregate", 14),
    ("admixture", 14),
    ("material", 10),
    ("parameter", 10),
    ("method", 8),
    ("test", 8),
    ("standard", 8),
    ("规范", 12),
    ("标准", 12),
    ("材料", 12),
    ("参数", 12),
    ("强度", 16),
    ("水灰比", 18),
    ("抗压", 18),
)
STANDARD_RE = re.compile(
    r"\b(?:GB|GB/T|GBT|DL/T|DL|JTG|SL|ACI|ASTM|EN|ISO)\s*[-/]?\s*[A-Z]?\s*\d{2,6}\b",
    re.IGNORECASE,
)
VALUE_UNIT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mpa|kpa|pa|mm|cm|m|kg/m3|kg/m³|kg|%|℃|°c|d|h|min)\b",
    re.IGNORECASE,
)
try:
    from scripts.evaluate_phase54_extraction_sample import write_json_payload
    from scripts.extract_phase53_graphrag_triples import (
        build_planner_extractor,
        extract_selected_chunks_to_rows,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    from evaluate_phase54_extraction_sample import write_json_payload
    from extract_phase53_graphrag_triples import (
        build_planner_extractor,
        extract_selected_chunks_to_rows,
    )


def chunk_count(db: Session, *, chunk_type: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Chunk).where(Chunk.chunk_type == chunk_type)) or 0)


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def load_rows_many(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(load_rows(path))
    return rows


def parse_path_list(value: str) -> list[Path]:
    return [
        Path(part.strip())
        for part in re.split(r"[;,]", value)
        if part.strip()
    ]


def parse_int_list(value: str) -> set[int]:
    return {
        int(part.strip())
        for part in re.split(r"[;,]", value)
        if part.strip()
    }


def fetch_chunk_pairs(
    db: Session,
    *,
    chunk_type: str,
    limit: int,
    offset: int,
    document_ids: set[int] | None = None,
    skip_chunk_ids: set[str] | None = None,
    selection: str = "all",
    high_value_min_score: int = 1,
    candidate_report_output: Path | None = None,
) -> list[tuple[Chunk, Document]]:
    statement = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.chunk_type == chunk_type)
        .order_by(Chunk.id)
        .offset(max(0, offset))
    )
    if document_ids:
        statement = statement.where(Document.id.in_(sorted(document_ids)))
    if limit > 0 and selection == "all":
        statement = statement.limit(limit)
    rows = list(db.execute(statement).all())
    if skip_chunk_ids:
        rows = [row for row in rows if str(row[0].id) not in skip_chunk_ids]
    if selection == "high-value":
        rows = select_high_value_chunk_pairs(
            rows,
            limit=limit,
            min_score=high_value_min_score,
            report_output=candidate_report_output,
        )
    return rows


def select_high_value_chunk_pairs(
    rows: list[tuple[Chunk, Document]],
    *,
    limit: int,
    min_score: int,
    report_output: Path | None = None,
) -> list[tuple[Chunk, Document]]:
    scored_rows = [
        (score_high_value_chunk(chunk, document), chunk, document)
        for chunk, document in rows
    ]
    selected = [
        (score, chunk, document)
        for score, chunk, document in scored_rows
        if score >= min_score
    ]
    selected.sort(key=lambda row: (-row[0], row[1].id))
    if limit > 0:
        selected = selected[:limit]
    if report_output is not None:
        write_candidate_report(report_output, selected)
    return [(chunk, document) for _, chunk, document in selected]


def score_high_value_chunk(chunk: Chunk, document: Document) -> int:
    text = " ".join(
        part
        for part in (
            document.title,
            chunk.heading_path or "",
            chunk.content,
        )
        if part
    )
    lowered = text.casefold()
    score = 0
    if chunk.chunk_type == "table":
        score += 40
    for keyword, weight in HIGH_VALUE_KEYWORDS:
        if keyword in lowered:
            score += weight
    standards = STANDARD_RE.findall(text)
    values = VALUE_UNIT_RE.findall(text)
    score += min(60, len(standards) * 12)
    score += min(40, len(values) * 8)
    if chunk.parent_chunk_id is not None:
        score += 8
    if chunk.heading_path:
        score += 5
    return score


def write_candidate_report(
    path: Path,
    rows: list[tuple[int, Chunk, Document]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "chunk_id",
                "document_id",
                "document_title",
                "chunk_type",
                "heading_bucket",
                "score",
            ],
        )
        writer.writeheader()
        for score, chunk, document in rows:
            writer.writerow(
                {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "document_title": document.title[:160],
                    "chunk_type": chunk.chunk_type,
                    "heading_bucket": (chunk.heading_path or document.title)[:160],
                    "score": score,
                }
            )


def extract_full_rows(
    db: Session,
    *,
    chunk_type: str,
    extractor,
    execute_llm: bool,
    output_path: Path,
    limit: int,
    offset: int,
    document_ids: set[int] | None = None,
    batch_size: int,
    flush_every: int,
    resume: bool,
    selection: str = "all",
    high_value_min_score: int = 1,
    candidate_report_output: Path | None = None,
    retry_failed: bool = False,
) -> list[dict[str, Any]]:
    existing_rows = load_rows(output_path) if resume else []
    rows_by_chunk_id = {str(row.get("chunk_id")): row for row in existing_rows}
    completed = {
        chunk_id
        for chunk_id, row in rows_by_chunk_id.items()
        if not retry_failed or row.get("status") == "ok"
    }
    chunk_pairs = fetch_chunk_pairs(
        db,
        chunk_type=chunk_type,
        limit=limit,
        offset=offset,
        document_ids=document_ids,
        skip_chunk_ids=completed if resume else None,
        selection=selection,
        high_value_min_score=high_value_min_score,
        candidate_report_output=candidate_report_output,
    )
    print(
        f"phase54_full_extract chunk_type={chunk_type} existing={len(rows_by_chunk_id)} "
        f"pending={len(chunk_pairs)} execute_llm={execute_llm} selection={selection} "
        f"retry_failed={retry_failed}"
    )
    effective_batch_size = max(1, batch_size)
    effective_flush_every = max(1, flush_every)
    for start in range(0, len(chunk_pairs), effective_batch_size):
        batch = chunk_pairs[start : start + effective_batch_size]
        if effective_batch_size == 1:
            for chunk_pair in batch:
                for row in extract_selected_chunks_to_rows(
                    [chunk_pair],
                    extractor=extractor,
                    execute_llm=execute_llm,
                ):
                    rows_by_chunk_id[str(row.get("chunk_id"))] = row
                if len(rows_by_chunk_id) % effective_flush_every == 0:
                    write_phase54_payload(
                        output_path,
                        rows=list(rows_by_chunk_id.values()),
                        mode="llm" if execute_llm else "regex",
                        chunk_type=chunk_type,
                        execute_llm=execute_llm,
                    )
                    print(f"wrote {len(rows_by_chunk_id)} rows to {output_path}")
            continue
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
            for future in as_completed(futures):
                for row in future.result():
                    rows_by_chunk_id[str(row.get("chunk_id"))] = row
                if len(rows_by_chunk_id) % effective_flush_every == 0:
                    write_phase54_payload(
                        output_path,
                        rows=list(rows_by_chunk_id.values()),
                        mode="llm" if execute_llm else "regex",
                        chunk_type=chunk_type,
                        execute_llm=execute_llm,
                    )
                    print(f"wrote {len(rows_by_chunk_id)} rows to {output_path}")
    rows = list(rows_by_chunk_id.values())
    write_phase54_payload(
        output_path,
        rows=rows,
        mode="llm" if execute_llm else "regex",
        chunk_type=chunk_type,
        execute_llm=execute_llm,
    )
    print(f"wrote {len(rows)} rows to {output_path}")
    return rows


def write_phase54_payload(
    path: Path,
    *,
    rows: list[dict[str, Any]],
    mode: str,
    chunk_type: str,
    execute_llm: bool,
) -> None:
    write_json_payload(
        path,
        rows=rows,
        phase=f"54B-{mode}",
        execute_llm=execute_llm,
        chunk_type=chunk_type,
        limit=len(rows),
        seed=0,
    )


def merge_extraction_rows(
    *,
    llm_rows: Iterable[dict[str, Any]],
    regex_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    llm_by_chunk = {str(row.get("chunk_id")): row for row in llm_rows}
    regex_by_chunk = {str(row.get("chunk_id")): row for row in regex_rows}
    chunk_ids = sorted(set(llm_by_chunk) | set(regex_by_chunk), key=lambda value: int(value) if value.isdigit() else value)
    merged_rows: list[dict[str, Any]] = []
    for chunk_id in chunk_ids:
        regex_result = result_from_row(regex_by_chunk.get(chunk_id))
        llm_result = result_from_row(llm_by_chunk.get(chunk_id))
        base = regex_result or llm_result
        if base is None:
            continue
        entities = deduplicate_entities(
            [
                *(list(regex_result.entities) if regex_result else []),
                *(list(llm_result.entities) if llm_result else []),
            ]
        )
        relations = deduplicate_relations(
            [
                *(list(regex_result.relations) if regex_result else []),
                *(list(llm_result.relations) if llm_result else []),
            ]
        )
        status = "ok" if entities or relations else "empty"
        merged = GraphExtractionResult(
            chunk_id=base.chunk_id,
            document_id=base.document_id,
            document_title=base.document_title,
            entities=entities,
            relations=relations,
            extractor="phase54_merge_regex_priority",
            status=status,
            metadata={
                "regex_status": (regex_by_chunk.get(chunk_id) or {}).get("status", "missing"),
                "llm_status": (llm_by_chunk.get(chunk_id) or {}).get("status", "missing"),
                "merge_policy": "regex_priority_llm_supplement",
            },
        )
        merged_rows.append(merged.to_dict())
    return merged_rows


def result_from_row(row: dict[str, Any] | None) -> GraphExtractionResult | None:
    if not row or row.get("status") != "ok":
        return None
    return GraphExtractionResult.from_dict(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 54B full GraphRAG extraction and merge workflow.")
    parser.add_argument("--mode", choices=("llm", "regex", "merge", "all"), default="all")
    parser.add_argument("--chunk-type", default="text")
    parser.add_argument(
        "--document-ids",
        default="",
        help="Optional comma/semicolon-separated document ids to extract, e.g. 2293,2294.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--flush-every", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    parser.add_argument("--max-attempts", type=int, default=1)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="With --resume, retry rows whose existing status is not ok and replace them by chunk_id.",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--selection",
        choices=("all", "high-value"),
        default="all",
        help="Use high-value for semantic LLM supplements; all preserves full regex behavior.",
    )
    parser.add_argument("--high-value-min-score", type=int, default=1)
    parser.add_argument(
        "--candidate-report-output",
        default="",
        help="Optional sanitized CSV of selected high-value candidates.",
    )
    parser.add_argument("--llm-output", default="data/knowledge_graph/extraction_text_chunks.json")
    parser.add_argument(
        "--extra-llm-output",
        default="",
        help="Optional comma/semicolon-separated additional LLM extraction files to include during merge.",
    )
    parser.add_argument("--regex-output", default="data/knowledge_graph/extraction_regex.json")
    parser.add_argument("--merged-output", default="data/knowledge_graph/extraction_merged.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    engine = create_database_engine(args.database_url or settings.database_url)
    llm_output = Path(args.llm_output)
    regex_output = Path(args.regex_output)
    merged_output = Path(args.merged_output)
    candidate_report_output = Path(args.candidate_report_output) if args.candidate_report_output else None
    document_ids = parse_int_list(args.document_ids) if args.document_ids else None
    with Session(engine) as db:
        if args.mode in {"llm", "all"}:
            extractor = build_planner_extractor(
                execute_llm=args.execute,
                timeout_seconds=args.timeout_seconds,
                max_attempts=args.max_attempts,
            )
            extract_full_rows(
                db,
                chunk_type=args.chunk_type,
                extractor=extractor,
                execute_llm=args.execute,
                output_path=llm_output,
                limit=args.limit,
                offset=args.offset,
                document_ids=document_ids,
                batch_size=args.batch_size,
                flush_every=args.flush_every,
                resume=args.resume,
                selection=args.selection,
                high_value_min_score=args.high_value_min_score,
                candidate_report_output=candidate_report_output,
                retry_failed=args.retry_failed,
            )
        if args.mode in {"regex", "all"}:
            from app.services.graphrag.extractor import GraphRAGTripleExtractor

            regex_selection = "all" if args.mode == "all" and args.selection == "high-value" else args.selection
            extract_full_rows(
                db,
                chunk_type=args.chunk_type,
                extractor=GraphRAGTripleExtractor(),
                execute_llm=False,
                output_path=regex_output,
                limit=args.limit,
                offset=args.offset,
                document_ids=document_ids,
                batch_size=args.batch_size,
                flush_every=args.flush_every,
                resume=args.resume,
                selection=regex_selection,
                high_value_min_score=args.high_value_min_score,
                candidate_report_output=None if regex_selection == "all" else candidate_report_output,
                retry_failed=args.retry_failed,
            )
        if args.mode in {"merge", "all"}:
            llm_paths = [llm_output, *parse_path_list(args.extra_llm_output)]
            llm_rows = load_rows_many(llm_paths)
            regex_rows = load_rows(regex_output)
            merged_rows = merge_extraction_rows(llm_rows=llm_rows, regex_rows=regex_rows)
            write_phase54_payload(
                merged_output,
                rows=merged_rows,
                mode="merge",
                chunk_type=args.chunk_type,
                execute_llm=args.execute,
            )
            ok_count = sum(1 for row in merged_rows if row.get("status") == "ok")
            print(
                "phase54_full_merge "
                f"rows={len(merged_rows)} ok={ok_count} output={merged_output}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

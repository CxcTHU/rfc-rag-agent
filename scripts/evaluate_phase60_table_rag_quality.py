from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.db.models import Chunk, DocumentTable
from app.db.session import SessionLocal
from app.services.table_rag.normalization import normalize_lookup_text, parse_markdown_table, short_preview
from app.services.table_rag.search import StructuredTableSearchService


PLACEHOLDER_HEADER_PATTERN = re.compile(r"^(列\d+|column\s*\d+)$", re.IGNORECASE)
GENERIC_CAPTION_PATTERN = re.compile(r"^(table on page \d+|table\s*\d+|fig(?:ure)?\.?\s*\d+|表\s*\d+)$", re.IGNORECASE)
PAGE_HEADER_PATTERN = re.compile(r"(大学\d{4}\s*届|of\s+\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class QualitySummary:
    table_count: int
    source_exact_matches: int
    source_shape_matches: int
    recall_cases: int
    top1_hits: int
    top5_hits: int
    out: Path


def evaluate_quality(*, out: Path, sample_size: int, seed: int, top_k: int) -> QualitySummary:
    random.seed(seed)
    with SessionLocal() as db:
        tables = db.query(DocumentTable).order_by(DocumentTable.id.asc()).all()
        source_exact_matches, source_shape_matches = source_alignment_counts(db, tables)
        cases = build_recall_cases(tables)
        sampled_cases = random.sample(cases, min(sample_size, len(cases))) if sample_size else cases
        service = StructuredTableSearchService(db)
        rows = [evaluate_case(service, case, top_k=top_k) for case in sampled_cases]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    return QualitySummary(
        table_count=len(tables),
        source_exact_matches=source_exact_matches,
        source_shape_matches=source_shape_matches,
        recall_cases=len(rows),
        top1_hits=sum(1 for row in rows if row["hit_top1"] == "true"),
        top5_hits=sum(1 for row in rows if row["hit_top5"] == "true"),
        out=out,
    )


def source_alignment_counts(db, tables: list[DocumentTable]) -> tuple[int, int]:
    exact = 0
    shape = 0
    for table in tables:
        chunk = db.get(Chunk, table.source_table_chunk_id) if table.source_table_chunk_id else None
        parsed = parse_markdown_table(chunk.content if chunk else "")
        structured = tuple(tuple(str(cell) for cell in row) for row in json.loads(table.normalized_rows_json or "[]"))
        if parsed == structured:
            exact += 1
        if len(parsed) == len(structured) and (
            not parsed
            or not structured
            or len(parsed[0]) == len(structured[0])
        ):
            shape += 1
    return exact, shape


def build_recall_cases(tables: list[DocumentTable]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for table in tables:
        headers = [str(value) for value in json.loads(table.headers_json or "[]")]
        rows = [[str(cell) for cell in row] for row in json.loads(table.normalized_rows_json or "[]")]
        raw_caption = clean_text(table.caption or table.header_text or "")
        caption = raw_caption if informative(raw_caption, min_len=6) else ""
        if informative(caption, min_len=6):
            cases.append(case("caption", table.id, f"表格 {caption}", table))
        informative_headers = [header for header in headers if informative(header, min_len=2)]
        if len(informative_headers) >= 2:
            cases.append(case("schema", table.id, spaced_query("表格", caption, "字段", " ".join(informative_headers[:4])), table))
        row_case = first_informative_row(rows)
        if row_case is not None:
            row_label, row_values = row_case
            cases.append(case("row", table.id, spaced_query("表格", caption, "行", row_label, " ".join(row_values[:3])), table))
        cell_case = first_informative_cell(headers, rows)
        if cell_case is not None:
            row_label, header, value = cell_case
            cases.append(case("cell", table.id, spaced_query("表格", caption, row_label, header, value), table))
    cases.append(
        {
            "case_id": "negative_weather",
            "category": "negative",
            "expected_table_id": "",
            "query": "今天北京天气怎么样",
            "document_id": "",
            "source_table_chunk_id": "",
            "page": "",
        }
    )
    return cases


def case(category: str, table_id: int, query: str, table: DocumentTable) -> dict[str, Any]:
    return {
        "case_id": f"{category}_{table_id}",
        "category": category,
        "expected_table_id": table_id,
        "query": query,
        "document_id": table.document_id,
        "source_table_chunk_id": table.source_table_chunk_id or "",
        "page": table.page_number or "",
    }


def spaced_query(*parts: str) -> str:
    return " ".join(part for part in (clean_text(value) for value in parts) if part)


def evaluate_case(
    service: StructuredTableSearchService,
    case_data: dict[str, Any],
    *,
    top_k: int,
) -> dict[str, object]:
    results = service.search(str(case_data["query"]), top_k=top_k)
    ids = [result.table_id for result in results]
    expected = case_data["expected_table_id"]
    top = results[0] if results else None
    hit_top1 = bool(expected and ids[:1] == [expected])
    hit_top5 = bool(expected and expected in ids)
    if case_data["category"] == "negative":
        hit_top1 = not ids
        hit_top5 = not ids
    return {
        "case_id": case_data["case_id"],
        "category": case_data["category"],
        "expected_table_id": expected,
        "query_hash": stable_hash(str(case_data["query"])),
        "query_preview": short_preview(str(case_data["query"]), 120),
        "result_count": len(results),
        "top_table_id": top.table_id if top else "",
        "top_score": top.score if top else "",
        "hit_top1": str(hit_top1).lower(),
        "hit_top5": str(hit_top5).lower(),
        "top_document_id": top.citation.document_id if top else "",
        "top_chunk_id": top.citation.chunk_id if top else "",
        "top_page": top.citation.page if top else "",
        "matched_types": "|".join(sorted({match.type for match in top.matched_units})) if top else "",
    }


def first_informative_row(rows: list[list[str]]) -> tuple[str, list[str]] | None:
    for row in rows[1:]:
        values = [clean_text(cell) for cell in row if informative(cell, min_len=2)]
        if len(values) >= 2 and informative(values[0], min_len=2):
            return values[0], values[1:]
    return None


def first_informative_cell(headers: list[str], rows: list[list[str]]) -> tuple[str, str, str] | None:
    for row in rows[1:]:
        row_label = clean_text(row[0]) if row else ""
        if not informative(row_label, min_len=2):
            continue
        for index, value in enumerate(row[1:], start=1):
            header = headers[index] if index < len(headers) else f"列{index + 1}"
            if informative(header, min_len=2) and informative(value, min_len=2):
                return row_label, clean_text(header), clean_text(value)
    return None


def informative(value: str, *, min_len: int) -> bool:
    normalized = clean_text(value)
    if len(normalized) < min_len:
        return False
    if normalized.isdigit():
        return False
    if PLACEHOLDER_HEADER_PATTERN.match(normalized):
        return False
    if GENERIC_CAPTION_PATTERN.match(normalized):
        return False
    if PAGE_HEADER_PATTERN.search(normalized) and len(normalized) > 60:
        return False
    if normalize_lookup_text(normalized) in {"table", "figure", "fig", "page"}:
        return False
    return True


def clean_text(value: str) -> str:
    return " ".join((value or "").split())


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 60 structured TableRAG quality.")
    parser.add_argument("--out", type=Path, default=Path("data/evaluation/phase60_table_rag_quality_eval.csv"))
    parser.add_argument("--sample-size", type=int, default=400)
    parser.add_argument("--seed", type=int, default=60)
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = evaluate_quality(out=args.out, sample_size=args.sample_size, seed=args.seed, top_k=args.top_k)
    top1 = summary.top1_hits / summary.recall_cases if summary.recall_cases else 0.0
    top5 = summary.top5_hits / summary.recall_cases if summary.recall_cases else 0.0
    exact = summary.source_exact_matches / summary.table_count if summary.table_count else 0.0
    print(
        "phase60 table rag quality: "
        f"tables={summary.table_count} source_exact={summary.source_exact_matches} "
        f"source_exact_rate={exact:.4f} recall_cases={summary.recall_cases} "
        f"top1={top1:.4f} top5={top5:.4f} out={summary.out}"
    )


if __name__ == "__main__":
    main()

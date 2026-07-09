from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from app.db.session import SessionLocal
from app.services.table_rag.search import StructuredTableSearchService


DEFAULT_CASES = (
    {"case_id": "phase60_find_table", "category": "find_table", "query": "表格 参数 单位"},
    {"case_id": "phase60_find_column", "category": "find_column", "query": "用量 kg/m3"},
    {"case_id": "phase60_find_row", "category": "find_row", "query": "材料 水泥"},
    {"case_id": "phase60_find_cell", "category": "find_cell", "query": "水泥 用量"},
    {"case_id": "phase60_negative", "category": "negative", "query": "今天北京天气怎么样"},
)


@dataclass(frozen=True)
class EvalSummary:
    cases: int
    rows: int
    out: Path


def evaluate(*, out: Path, top_k: int, limit: int | None) -> EvalSummary:
    cases = DEFAULT_CASES[:limit] if limit is not None else DEFAULT_CASES
    rows: list[dict[str, object]] = []
    with SessionLocal() as db:
        service = StructuredTableSearchService(db)
        for case in cases:
            results = service.search(str(case["query"]), top_k=top_k)
            top = results[0] if results else None
            rows.append(
                {
                    "case_id": case["case_id"],
                    "category": case["category"],
                    "result_count": len(results),
                    "top_table_id": top.table_id if top else "",
                    "top_score": top.score if top else "",
                    "top_document_id": top.citation.document_id if top else "",
                    "top_chunk_id": top.citation.chunk_id if top else "",
                    "top_page": top.citation.page if top else "",
                    "matched_count": len(top.matched_units) if top else 0,
                    "matched_types": "|".join(sorted({match.type for match in top.matched_units})) if top else "",
                    "row_count": top.metadata.get("row_count", "") if top else "",
                    "col_count": top.metadata.get("col_count", "") if top else "",
                    "quality_score": top.metadata.get("quality_score", "") if top else "",
                }
            )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    return EvalSummary(cases=len(cases), rows=len(rows), out=out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sanitized Phase 60 Structured TableRAG retrieval eval.")
    parser.add_argument("--out", type=Path, default=Path("data/evaluation/phase60_table_rag_eval.csv"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = evaluate(out=args.out, top_k=args.top_k, limit=args.limit)
    print(f"phase60 table rag eval: cases={summary.cases} rows={summary.rows} out={summary.out}")


if __name__ == "__main__":
    main()

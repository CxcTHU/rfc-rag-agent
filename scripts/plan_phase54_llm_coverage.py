from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Chunk, Document
from app.db.session import create_database_engine
try:
    from scripts.extract_phase54_graphrag_full import load_rows, score_high_value_chunk
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    from extract_phase54_graphrag_full import load_rows, score_high_value_chunk


DEFAULT_TEXT_SCORE_THRESHOLD = 180


def score_distribution(scores: list[int], thresholds: list[int]) -> dict[str, int]:
    return {str(threshold): sum(1 for score in scores if score >= threshold) for threshold in thresholds}


def coverage_summary(
    *,
    database_url: str,
    text_llm_output: Path,
    table_llm_output: Path,
    text_score_threshold: int,
) -> dict[str, Any]:
    engine = create_database_engine(database_url)
    with Session(engine) as db:
        chunk_counts = dict(db.execute(select(Chunk.chunk_type, func.count()).group_by(Chunk.chunk_type)).all())
        text_rows = list(
            db.execute(
                select(Chunk, Document)
                .join(Document, Chunk.document_id == Document.id)
                .where(Chunk.chunk_type == "text")
            ).all()
        )
        table_rows = list(
            db.execute(
                select(Chunk, Document)
                .join(Document, Chunk.document_id == Document.id)
                .where(Chunk.chunk_type == "table")
            ).all()
        )

    text_scores = {
        str(chunk.id): score_high_value_chunk(chunk, document)
        for chunk, document in text_rows
    }
    table_ids = {str(chunk.id) for chunk, _ in table_rows}
    text_target_ids = {
        chunk_id
        for chunk_id, score in text_scores.items()
        if score >= text_score_threshold
    }
    completed_text_ids = {str(row.get("chunk_id")) for row in load_rows(text_llm_output)}
    completed_table_ids = {str(row.get("chunk_id")) for row in load_rows(table_llm_output)}
    completed_text_target_ids = completed_text_ids & text_target_ids
    completed_table_target_ids = completed_table_ids & table_ids

    text_thresholds = [150, 180, 200, 240, 280, 320]
    table_scores = [score_high_value_chunk(chunk, document) for chunk, document in table_rows]
    return {
        "chunk_counts": {str(key): int(value) for key, value in chunk_counts.items()},
        "decision": {
            "text_score_threshold": text_score_threshold,
            "text_target_rule": f"score >= {text_score_threshold}",
            "table_target_rule": "all table chunks",
            "rationale": (
                "score>=180 selects the top high-value text band within the planned "
                "2000-5000 range; all table chunks are included because table chunks "
                "are only 1440 rows and dense in material/parameter/value relations."
            ),
        },
        "text": {
            "total": len(text_scores),
            "score_distribution": score_distribution(list(text_scores.values()), text_thresholds),
            "target": len(text_target_ids),
            "completed_target": len(completed_text_target_ids),
            "remaining_target": len(text_target_ids - completed_text_ids),
            "completed_any": len(completed_text_ids),
        },
        "table": {
            "total": len(table_ids),
            "score_distribution": score_distribution(table_scores, [1, 40, 60, 80, 100, 120, 150, 180, 200, 240]),
            "target": len(table_ids),
            "completed_target": len(completed_table_target_ids),
            "remaining_target": len(table_ids - completed_table_ids),
            "completed_any": len(completed_table_ids),
        },
        "combined": {
            "target": len(text_target_ids) + len(table_ids),
            "completed_target": len(completed_text_target_ids) + len(completed_table_target_ids),
            "remaining_target": len(text_target_ids - completed_text_ids) + len(table_ids - completed_table_ids),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan Phase 54B high-value LLM coverage without exposing chunk text.")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--text-llm-output", default="data/knowledge_graph/extraction_text_chunks.json")
    parser.add_argument("--table-llm-output", default="data/knowledge_graph/extraction_table_chunks.json")
    parser.add_argument("--text-score-threshold", type=int, default=DEFAULT_TEXT_SCORE_THRESHOLD)
    parser.add_argument("--output", default="data/evaluation/phase54_llm_coverage_plan.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    summary = coverage_summary(
        database_url=args.database_url or settings.database_url,
        text_llm_output=Path(args.text_llm_output),
        table_llm_output=Path(args.table_llm_output),
        text_score_threshold=args.text_score_threshold,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

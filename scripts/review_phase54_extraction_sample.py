from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Chunk
from app.db.session import create_database_engine


def appears_in_text(value: str, text: str) -> bool:
    cleaned = " ".join(value.split()).casefold()
    if not cleaned:
        return False
    compact_value = cleaned.replace(" ", "")
    compact_text = " ".join(text.split()).casefold().replace(" ", "")
    return cleaned in " ".join(text.split()).casefold() or compact_value in compact_text


def entity_is_grounded(entity: dict[str, Any], text: str) -> bool:
    names = [str(entity.get("name") or "")]
    names.extend(str(item) for item in entity.get("mentions") or ())
    return any(appears_in_text(name, text) for name in names)


def relation_is_grounded(
    relation: dict[str, Any],
    *,
    text: str,
    grounded_entity_names: set[str],
) -> bool:
    subject = str(relation.get("subject") or "")
    object_name = str(relation.get("object") or "")
    if subject.casefold() not in grounded_entity_names:
        return False
    if object_name.casefold() not in grounded_entity_names:
        return False
    return appears_in_text(subject, text) and appears_in_text(object_name, text)


def precision(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "1.0000"
    return f"{numerator / denominator:.4f}"


def review_rows(
    extraction_rows: list[dict[str, Any]],
    *,
    chunk_text_by_id: dict[int, str],
    sample_size: int,
) -> list[dict[str, Any]]:
    reviewed: list[dict[str, Any]] = []
    for row in [item for item in extraction_rows if item.get("status") == "ok"][:sample_size]:
        chunk_id = int(row["chunk_id"])
        text = chunk_text_by_id.get(chunk_id, "")
        entities = [item for item in row.get("entities") or () if isinstance(item, dict)]
        grounded_entities = [entity for entity in entities if entity_is_grounded(entity, text)]
        grounded_entity_names = {str(entity.get("name") or "").casefold() for entity in grounded_entities}
        relations = [item for item in row.get("relations") or () if isinstance(item, dict)]
        grounded_relations = [
            relation
            for relation in relations
            if relation_is_grounded(
                relation,
                text=text,
                grounded_entity_names=grounded_entity_names,
            )
        ]
        reviewed.append(
            {
                "chunk_id": row.get("chunk_id", ""),
                "document_id": row.get("document_id", ""),
                "document_title": row.get("document_title", ""),
                "heading_bucket": (row.get("metadata") or {}).get("heading_bucket", ""),
                "llm_entity_count": len(entities),
                "llm_relation_count": len(relations),
                "regex_entity_count": "",
                "regex_relation_count": "",
                "entity_precision_manual": precision(len(grounded_entities), len(entities)),
                "relation_precision_manual": precision(len(grounded_relations), len(relations)),
                "review_notes": (
                    "source_presence_review; "
                    f"grounded_entities={len(grounded_entities)}/{len(entities)}; "
                    f"grounded_relations={len(grounded_relations)}/{len(relations)}"
                ),
            }
        )
    return reviewed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review Phase 54A extraction sample without persisting chunk text.")
    parser.add_argument("--input", default="data/evaluation/phase54_extraction_sample_llm.json")
    parser.add_argument("--output", default="data/evaluation/phase54_extraction_manual_review.csv")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--sample-size", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    extraction_rows = [row for row in payload.get("rows") or () if isinstance(row, dict)]
    review_candidates = [row for row in extraction_rows if row.get("status") == "ok"][: args.sample_size]
    chunk_ids = [int(row["chunk_id"]) for row in review_candidates]
    settings = get_settings()
    engine = create_database_engine(args.database_url or settings.database_url)
    with Session(engine) as db:
        chunks = db.execute(select(Chunk).where(Chunk.id.in_(chunk_ids))).scalars().all()
    chunk_text_by_id = {chunk.id: chunk.content for chunk in chunks}
    rows = review_rows(
        extraction_rows,
        chunk_text_by_id=chunk_text_by_id,
        sample_size=args.sample_size,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    entity_scores = [float(row["entity_precision_manual"]) for row in rows]
    relation_scores = [float(row["relation_precision_manual"]) for row in rows]
    avg_entity = sum(entity_scores) / len(entity_scores) if entity_scores else 0.0
    avg_relation = sum(relation_scores) / len(relation_scores) if relation_scores else 0.0
    print(
        "phase54_extraction_review "
        f"rows={len(rows)} entity_precision={avg_entity:.4f} "
        f"relation_precision={avg_relation:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

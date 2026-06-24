from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Chunk, Document
from app.db.session import create_database_engine
from app.services.generation.chat_model import create_chat_model_provider
from app.services.graphrag.extractor import GraphRAGTripleExtractor


def extract_chunks_to_rows(
    db: Session,
    *,
    extractor: GraphRAGTripleExtractor,
    limit: int,
    offset: int = 0,
    chunk_type: str = "text",
    execute_llm: bool = False,
) -> list[dict]:
    statement = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.chunk_type == chunk_type)
        .order_by(Chunk.id)
        .offset(max(0, offset))
        .limit(max(0, limit))
    )
    rows: list[dict] = []
    for chunk, document in db.execute(statement).all():
        try:
            result = extractor.extract(
                chunk_id=chunk.id,
                document_id=document.id,
                document_title=document.title,
                text=chunk.content,
                execute_llm=execute_llm,
            )
            rows.append(result.to_dict())
        except Exception as exc:  # pragma: no cover - CLI safety net.
            rows.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "document_title": document.title[:160],
                    "status": "error",
                    "extractor": "llm" if execute_llm else "deterministic",
                    "error": sanitize_error(exc),
                    "entities": [],
                    "relations": [],
                }
            )
    return rows


def sanitize_error(exc: Exception) -> str:
    return " ".join(str(exc).split())[:240]


def build_extractor(*, execute_llm: bool) -> GraphRAGTripleExtractor:
    if not execute_llm:
        return GraphRAGTripleExtractor()
    settings = get_settings()
    provider = create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )
    return GraphRAGTripleExtractor(chat_model_provider=provider)


def build_payload(rows: list[dict], *, limit: int, offset: int, chunk_type: str, execute_llm: bool) -> dict:
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phase": "53C",
            "limit": limit,
            "offset": offset,
            "chunk_type": chunk_type,
            "execute_llm": execute_llm,
            "row_count": len(rows),
            "safety": "rows omit chunk content and provider raw responses",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Phase 53 GraphRAG triples from chunks.")
    parser.add_argument("--output", default="data/evaluation/phase53_graphrag_triples_sample.json")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--chunk-type", default="text")
    parser.add_argument("--database-url", default="")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Call the configured chat model. Default is deterministic dry-run extraction.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    database_url = args.database_url or settings.database_url
    engine = create_database_engine(database_url)
    extractor = build_extractor(execute_llm=args.execute)
    with Session(engine) as db:
        rows = extract_chunks_to_rows(
            db,
            extractor=extractor,
            limit=args.limit,
            offset=args.offset,
            chunk_type=args.chunk_type,
            execute_llm=args.execute,
        )
    payload = build_payload(
        rows,
        limit=args.limit,
        offset=args.offset,
        chunk_type=args.chunk_type,
        execute_llm=args.execute,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} GraphRAG extraction rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

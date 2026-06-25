from __future__ import annotations

import argparse
import json
import os
import random
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Chunk, Document
from app.db.session import create_database_engine
from app.services.generation.chat_model import create_chat_model_provider
from app.services.graphrag.extractor import GraphRAGTripleExtractor


class RoundRobinChatModelProvider:
    def __init__(self, providers: list[Any]) -> None:
        if not providers:
            raise ValueError("providers must not be empty")
        self.providers = tuple(providers)
        self.provider_name = "+".join(sorted({provider.provider_name for provider in self.providers}))
        self.model_name = self.providers[0].model_name
        self._lock = threading.Lock()
        self._next_index = 0

    def _next_provider(self) -> Any:
        with self._lock:
            provider = self.providers[self._next_index % len(self.providers)]
            self._next_index += 1
        return provider

    def generate(self, messages):
        return self._next_provider().generate(messages)

    def stream_generate(self, messages):
        return self._next_provider().stream_generate(messages)

    def generate_with_tools(self, messages, tools):
        return self._next_provider().generate_with_tools(messages, tools)


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


def select_diverse_chunks(
    db: Session,
    *,
    limit: int,
    chunk_type: str = "text",
    seed: int = 54,
) -> list[tuple[Chunk, Document]]:
    """Sample chunks across heading buckets without storing chunk text in outputs."""

    statement = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.chunk_type == chunk_type)
        .order_by(Chunk.id)
    )
    candidates = list(db.execute(statement).all())
    if limit <= 0 or len(candidates) <= limit:
        return candidates[: max(0, limit)]

    rng = random.Random(seed)
    selected: list[tuple[Chunk, Document]] = []
    selected_ids: set[int] = set()

    by_document: dict[int, list[tuple[Chunk, Document]]] = {}
    for chunk, document in candidates:
        by_document.setdefault(document.id, []).append((chunk, document))
    document_ids = list(by_document)
    rng.shuffle(document_ids)
    for document_id in document_ids:
        document_rows = by_document[document_id]
        choice = document_rows[rng.randrange(len(document_rows))]
        selected.append(choice)
        selected_ids.add(choice[0].id)
        if len(selected) >= limit:
            selected.sort(key=lambda row: row[0].id)
            return selected

    buckets: dict[str, list[tuple[Chunk, Document]]] = {}
    for chunk, document in candidates:
        bucket = heading_bucket(chunk.heading_path, document.title)
        buckets.setdefault(bucket, []).append((chunk, document))

    bucket_names = list(buckets)
    rng.shuffle(bucket_names)
    for bucket in bucket_names:
        bucket_rows = buckets[bucket]
        available = [row for row in bucket_rows if row[0].id not in selected_ids]
        if not available:
            continue
        choice = available[rng.randrange(len(available))]
        selected.append(choice)
        selected_ids.add(choice[0].id)
        if len(selected) >= limit:
            selected.sort(key=lambda row: row[0].id)
            return selected

    remaining = [row for row in candidates if row[0].id not in selected_ids]
    rng.shuffle(remaining)
    selected.extend(remaining[: limit - len(selected)])
    selected.sort(key=lambda row: row[0].id)
    return selected[:limit]


def extract_selected_chunks_to_rows(
    chunks: list[tuple[Chunk, Document]],
    *,
    extractor: GraphRAGTripleExtractor,
    execute_llm: bool = False,
) -> list[dict]:
    rows: list[dict] = []
    for chunk, document in chunks:
        try:
            result = extractor.extract(
                chunk_id=chunk.id,
                document_id=document.id,
                document_title=document.title,
                text=chunk.content,
                execute_llm=execute_llm,
            )
            data = result.to_dict()
            data["metadata"] = {
                **dict(data.get("metadata") or {}),
                "heading_bucket": heading_bucket(chunk.heading_path, document.title),
                "chunk_type": chunk.chunk_type,
            }
            rows.append(data)
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
                    "metadata": {
                        "heading_bucket": heading_bucket(chunk.heading_path, document.title),
                        "chunk_type": chunk.chunk_type,
                    },
                }
            )
    return rows


def heading_bucket(heading_path: str | None, document_title: str) -> str:
    heading = " / ".join(part.strip() for part in (heading_path or "").split(">") if part.strip())
    if not heading:
        heading = document_title
    return heading[:120]


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


def build_planner_extractor(
    *,
    execute_llm: bool,
    timeout_seconds: float | None = None,
    max_attempts: int = 1,
) -> GraphRAGTripleExtractor:
    if not execute_llm:
        return GraphRAGTripleExtractor()
    settings = get_settings()
    api_keys = planner_api_keys(
        single_api_key=settings.planner_chat_model_api_key,
        multi_api_keys=settings.planner_chat_model_api_keys,
    )
    missing = [
        name
        for name, value in {
            "PLANNER_CHAT_MODEL_PROVIDER": settings.planner_chat_model_provider,
            "PLANNER_CHAT_MODEL_NAME": settings.planner_chat_model_name,
            "PLANNER_CHAT_MODEL_API_KEY or PLANNER_CHAT_MODEL_API_KEYS": api_keys,
            "PLANNER_CHAT_MODEL_BASE_URL": settings.planner_chat_model_base_url,
        }.items()
        if not str(value or "").strip()
    ]
    if missing:
        raise RuntimeError(
            "Planner chat provider is required for GraphRAG LLM extraction: "
            + ", ".join(missing)
        )
    providers = [
        create_chat_model_provider(
            provider_name=settings.planner_chat_model_provider,
            model_name=settings.planner_chat_model_name,
            api_key=api_key,
            base_url=settings.planner_chat_model_base_url,
            temperature=settings.planner_chat_model_temperature,
            timeout_seconds=timeout_seconds or settings.planner_chat_model_timeout_seconds,
            max_attempts=max(1, max_attempts),
        )
        for api_key in api_keys
    ]
    provider = providers[0] if len(providers) == 1 else RoundRobinChatModelProvider(providers)
    return GraphRAGTripleExtractor(chat_model_provider=provider)


def planner_api_keys(*, single_api_key: str, multi_api_keys: str = "") -> list[str]:
    raw_multi_key = multi_api_keys or os.getenv("PLANNER_CHAT_MODEL_API_KEYS", "")
    keys = [
        key.strip()
        for key in raw_multi_key.split(",")
        if key.strip()
    ]
    single = str(single_api_key or "").strip()
    if single:
        keys.append(single)
    deduped_keys: list[str] = []
    for key in keys:
        if key not in deduped_keys:
            deduped_keys.append(key)
    return deduped_keys


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
            "safety": "sanitized derived extraction rows only",
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
    parser.add_argument("--sample-diverse", action="store_true")
    parser.add_argument("--seed", type=int, default=54)
    parser.add_argument("--timeout-seconds", type=float, default=0.0)
    parser.add_argument("--max-attempts", type=int, default=1)
    parser.add_argument(
        "--provider-role",
        choices=("chat", "planner"),
        default="chat",
        help="Use planner provider for Phase 54 extraction; default preserves Phase 53 behavior.",
    )
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
    if args.provider_role == "planner":
        extractor = build_planner_extractor(
            execute_llm=args.execute,
            timeout_seconds=args.timeout_seconds or None,
            max_attempts=args.max_attempts,
        )
    else:
        extractor = build_extractor(execute_llm=args.execute)
    with Session(engine) as db:
        if args.sample_diverse:
            chunks = select_diverse_chunks(
                db,
                limit=args.limit,
                chunk_type=args.chunk_type,
                seed=args.seed,
            )
            rows = extract_selected_chunks_to_rows(
                chunks,
                extractor=extractor,
                execute_llm=args.execute,
            )
        else:
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

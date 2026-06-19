"""Smoke-test Phase 45 candidate retrieval without exporting chunk text."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchService  # noqa: E402
from app.services.retrieval.keyword_search import KeywordSearchService  # noqa: E402
from app.services.retrieval.vector_search import VectorSearchService  # noqa: E402


DEFAULT_OUTPUT = ROOT / "data" / "incoming" / "phase45_literature" / "phase13_retrieval_smoke.csv"
DEFAULT_QUERIES = [
    "清华大学 堆石混凝土 技术",
    "堆石混凝土 施工 质量控制",
    "胶结颗粒料 筑坝 技术",
]


@dataclass(frozen=True)
class RetrievalSmokeRow:
    query: str
    mode: str
    hit_count: int
    top_title: str
    top_source_type: str
    top_chunk_type: str
    top_document_id: int | None


def run_smoke(queries: list[str]) -> list[RetrievalSmokeRow]:
    settings = get_settings()
    provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    rows: list[RetrievalSmokeRow] = []
    init_db()
    with SessionLocal() as db:
        keyword = KeywordSearchService(db)
        vector = VectorSearchService(db, provider)
        hybrid = HybridSearchService(db, provider, reranking_enabled=False, parallel=False)
        for query in queries:
            for mode, results in (
                ("keyword", keyword.search(query, top_k=5)),
                ("vector", vector.search(query, top_k=5)),
                ("hybrid", hybrid.search(query, top_k=5)),
            ):
                top = results[0] if results else None
                rows.append(
                    RetrievalSmokeRow(
                        query=query,
                        mode=mode,
                        hit_count=len(results),
                        top_title=top.document_title if top else "",
                        top_source_type=top.source_type if top else "",
                        top_chunk_type=get_chunk_type(db, top.chunk_id) if top else "",
                        top_document_id=top.document_id if top else None,
                    )
                )
    return rows


def get_chunk_type(db, chunk_id: int) -> str:
    row = db.execute(__import__("sqlalchemy").text("select chunk_type from chunks where id = :id"), {"id": chunk_id}).fetchone()
    return str(row[0]) if row else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test Phase 45 candidate retrieval.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--query", action="append", default=[])
    args = parser.parse_args()

    rows = run_smoke(args.query or DEFAULT_QUERIES)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    for row in rows:
        print(
            f"{row.mode}\tquery={row.query}\thits={row.hit_count}\t"
            f"top={row.top_title}\tsource={row.top_source_type}\tchunk_type={row.top_chunk_type}\tdoc={row.top_document_id}"
        )
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()

"""Evaluate Phase 45 multimodal sample quality without exporting chunk text."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.vector_search import VectorSearchService  # noqa: E402
from scripts.clean_phase45_low_value_images import classify_image_chunk  # noqa: E402


DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "incoming" / "phase45_literature" / "phase21_multimodal_100_quality"
DEFAULT_RESULT_CSVS = [
    ROOT / "data" / "incoming" / "phase45_literature" / "phase21_multimodal_100" / "process_multimodal_results.csv",
    ROOT
    / "data"
    / "incoming"
    / "phase45_literature"
    / "phase21_multimodal_100_retry_zhipu"
    / "process_multimodal_results.csv",
    ROOT
    / "data"
    / "incoming"
    / "phase45_literature"
    / "phase22_multimodal_all_zhipu"
    / "process_multimodal_results.csv",
    ROOT
    / "data"
    / "incoming"
    / "phase45_literature"
    / "phase21_remaining_3_zhipu"
    / "process_multimodal_results.csv",
]
DEFAULT_QUERIES = [
    "堆石混凝土施工流程图",
    "自密实混凝土填充块石空隙示意图",
    "堆石混凝土抗压强度龄期曲线",
    "堆石混凝土试验装置压力加载图",
    "堆石混凝土坝体剖面结构图",
]


@dataclass(frozen=True)
class SampleQualitySummary:
    sample_documents: int
    processed_documents: int
    failed_documents: int
    documents_with_image_chunks: int
    image_chunks: int
    image_embeddings: int
    missing_image_embeddings: int
    avg_chunks_per_image_doc: float
    avg_description_chars: float
    short_description_chunks: int
    low_value_remove_candidates: int
    low_value_review_candidates: int
    vector_queries: int
    vector_queries_with_image_hit: int
    vector_image_top1_hits: int
    vector_image_top5_hits: int
    passed_quality_gate: bool


@dataclass(frozen=True)
class RetrievalQualityRow:
    query: str
    top_k: int
    image_hits: int
    top1_chunk_type: str
    top1_document_id: int | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Phase 45 multimodal sample quality.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--result-csv", action="append", default=[])
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    result_csvs = [Path(value) for value in args.result_csv] or DEFAULT_RESULT_CSVS
    sample_ids, status_counts = read_sample_status(result_csvs)
    with sqlite3.connect(args.db_path) as connection:
        doc_stats, image_rows = read_image_stats(connection, sample_ids)
        image_embeddings = count_image_embeddings(connection, sample_ids)

    retrieval_rows = run_vector_smoke(args.query or DEFAULT_QUERIES, top_k=args.top_k)
    summary = summarize(
        sample_ids=sample_ids,
        status_counts=status_counts,
        doc_stats=doc_stats,
        image_rows=image_rows,
        image_embeddings=image_embeddings,
        retrieval_rows=retrieval_rows,
    )
    write_outputs(summary, retrieval_rows, Path(args.output_dir))
    print("summary:", " ".join(f"{key}={value}" for key, value in asdict(summary).items()))


def read_sample_status(paths: list[Path]) -> tuple[set[int], Counter[str]]:
    latest_status: dict[int, str] = {}
    sample_ids: set[int] = set()
    for index, path in enumerate(paths):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                document_id = int(row["document_id"])
                status = str(row["status"])
                if index == 0:
                    sample_ids.add(document_id)
                    latest_status[document_id] = status
                elif document_id in sample_ids:
                    latest_status[document_id] = status
    return sample_ids, Counter(latest_status.values())


def read_image_stats(
    connection: sqlite3.Connection,
    sample_ids: set[int],
) -> tuple[dict[int, int], list[tuple[int, int, str]]]:
    if not sample_ids:
        return {}, []
    placeholders = ",".join("?" for _ in sample_ids)
    rows = connection.execute(
        f"""
        select document_id, id, content
        from chunks
        where chunk_type = 'image_description'
          and document_id in ({placeholders})
        order by document_id, id
        """,
        sorted(sample_ids),
    ).fetchall()
    doc_stats: dict[int, int] = Counter(int(row[0]) for row in rows)
    image_rows = [(int(row[0]), int(row[1]), str(row[2] or "")) for row in rows]
    return doc_stats, image_rows


def count_image_embeddings(connection: sqlite3.Connection, sample_ids: set[int]) -> int:
    if not sample_ids:
        return 0
    placeholders = ",".join("?" for _ in sample_ids)
    row = connection.execute(
        f"""
        select count(1)
        from chunk_embeddings
        where chunk_id in (
            select id
            from chunks
            where chunk_type = 'image_description'
              and document_id in ({placeholders})
        )
        """,
        sorted(sample_ids),
    ).fetchone()
    return int(row[0] or 0)


def run_vector_smoke(queries: list[str], top_k: int) -> list[RetrievalQualityRow]:
    settings = get_settings()
    provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    rows: list[RetrievalQualityRow] = []
    init_db()
    with SessionLocal() as db:
        service = VectorSearchService(db, provider)
        for query in queries:
            results = service.search(query, top_k=top_k)
            chunk_types = get_chunk_types(db, [result.chunk_id for result in results])
            top1 = results[0] if results else None
            top1_type = chunk_types.get(top1.chunk_id, "") if top1 else ""
            rows.append(
                RetrievalQualityRow(
                    query=query,
                    top_k=top_k,
                    image_hits=sum(1 for result in results if chunk_types.get(result.chunk_id) == "image_description"),
                    top1_chunk_type=top1_type,
                    top1_document_id=top1.document_id if top1 else None,
                )
            )
    return rows


def get_chunk_types(db, chunk_ids: list[int]) -> dict[int, str]:
    if not chunk_ids:
        return {}
    placeholders = ",".join(f":id_{index}" for index, _ in enumerate(chunk_ids))
    params = {f"id_{index}": chunk_id for index, chunk_id in enumerate(chunk_ids)}
    rows = db.execute(
        __import__("sqlalchemy").text(f"select id, chunk_type from chunks where id in ({placeholders})"),
        params,
    ).fetchall()
    return {int(row[0]): str(row[1] or "") for row in rows}


def summarize(
    *,
    sample_ids: set[int],
    status_counts: Counter[str],
    doc_stats: dict[int, int],
    image_rows: list[tuple[int, int, str]],
    image_embeddings: int,
    retrieval_rows: list[RetrievalQualityRow],
) -> SampleQualitySummary:
    char_counts = [len(content) for _, _, content in image_rows]
    decisions = [classify_image_chunk(content, len(content))[0] for _, _, content in image_rows]
    image_chunks = len(image_rows)
    missing_embeddings = max(0, image_chunks - image_embeddings)
    vector_queries_with_image_hit = sum(1 for row in retrieval_rows if row.image_hits > 0)
    vector_image_top1_hits = sum(1 for row in retrieval_rows if row.top1_chunk_type == "image_description")
    vector_image_top5_hits = vector_queries_with_image_hit
    passed_quality_gate = (
        status_counts["processed"] >= max(1, int(len(sample_ids) * 0.80))
        and image_chunks > 0
        and missing_embeddings == 0
        and decisions.count("remove") / max(1, image_chunks) <= 0.10
        and vector_queries_with_image_hit >= max(1, len(retrieval_rows) // 2)
    )
    return SampleQualitySummary(
        sample_documents=len(sample_ids),
        processed_documents=status_counts["processed"],
        failed_documents=status_counts["failed"],
        documents_with_image_chunks=len(doc_stats),
        image_chunks=image_chunks,
        image_embeddings=image_embeddings,
        missing_image_embeddings=missing_embeddings,
        avg_chunks_per_image_doc=round(image_chunks / max(1, len(doc_stats)), 2),
        avg_description_chars=round(sum(char_counts) / max(1, len(char_counts)), 2),
        short_description_chunks=sum(1 for count in char_counts if count < 60),
        low_value_remove_candidates=decisions.count("remove"),
        low_value_review_candidates=decisions.count("review"),
        vector_queries=len(retrieval_rows),
        vector_queries_with_image_hit=vector_queries_with_image_hit,
        vector_image_top1_hits=vector_image_top1_hits,
        vector_image_top5_hits=vector_image_top5_hits,
        passed_quality_gate=passed_quality_gate,
    )


def write_outputs(
    summary: SampleQualitySummary,
    retrieval_rows: list[RetrievalQualityRow],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "multimodal_sample_quality_summary.json").write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    retrieval_path = output_dir / "multimodal_sample_retrieval.csv"
    with retrieval_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(retrieval_rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in retrieval_rows)


if __name__ == "__main__":
    main()

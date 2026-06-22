from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session, aliased, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models import Base, Chunk, Document, QuestionAnswerLog  # noqa: E402
from app.db.repositories import deserialize_int_list  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402

DEFAULT_OUTPUT_DIR = ROOT / "data" / "reranker_training"
DEFAULT_EVAL_QUERY_FILES = (
    ROOT / "data" / "evaluation" / "agent_queries.csv",
    ROOT / "data" / "evaluation" / "chat_queries.csv",
    ROOT / "data" / "evaluation" / "cn_fulltext_queries.csv",
    ROOT / "data" / "evaluation" / "keyword_queries.csv",
    ROOT / "data" / "evaluation" / "phase45_domestic_coverage_queries.csv",
    ROOT / "data" / "evaluation" / "stage18_hard_queries.csv",
    ROOT / "data" / "evaluation" / "stage19_chinese_hard_queries.csv",
    ROOT / "data" / "evaluation" / "stage29_new_corpus_queries.csv",
    ROOT / "data" / "evaluation" / "stage41_post_import_retrieval_queries.csv",
    ROOT / "data" / "evaluation" / "stage43_multi_turn_eval_cases.csv",
)
DOMAIN_TERMS = (
    "rfc",
    "rock-filled",
    "rock filled",
    "rockfill",
    "堆石",
    "混凝土",
    "坝",
    "dam",
    "密实",
    "自密实",
    "aggregate",
    "施工",
    "强度",
)


@dataclass(frozen=True)
class QALogPair:
    query: str
    chunk_id: int
    label: int
    source: str
    qa_log_id: int
    rank: int
    citation_index: int | None
    document_id: int | None
    chunk_type: str
    content: str


@dataclass(frozen=True)
class SampledChunk:
    chunk_id: int
    document_id: int
    document_title: str
    chunk_type: str
    content: str
    char_count: int


@dataclass(frozen=True)
class EvalQuery:
    query_id: str
    question: str
    source_file: str
    category: str
    expected_source_terms: str
    expected_refused: str


@dataclass(frozen=True)
class ExportSummary:
    qa_log_pairs: int
    sampled_chunks: int
    eval_queries: int
    output_dir: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Step 1 data for RFC-DomainReranker.")
    parser.add_argument("--database-url", default="", help="Override DATABASE_URL for export.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample-size", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=51)
    parser.add_argument("--create-schema", action="store_true", help="Create schema before export for tests.")
    parser.add_argument(
        "--eval-query-file",
        action="append",
        type=Path,
        default=[],
        help="Evaluation CSV to mine for frozen eval queries. Repeatable.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = create_database_engine(args.database_url or _settings_database_url())
    if args.create_schema:
        Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as db:
        summary = export_reranker_step1_data(
            db,
            output_dir=args.output_dir,
            sample_size=args.sample_size,
            seed=args.seed,
            eval_query_files=args.eval_query_file or list(DEFAULT_EVAL_QUERY_FILES),
        )
    print(
        "exported "
        f"qa_log_pairs={summary.qa_log_pairs} "
        f"sampled_chunks={summary.sampled_chunks} "
        f"eval_queries={summary.eval_queries} "
        f"output_dir={summary.output_dir}"
    )


def _settings_database_url() -> str:
    from app.core.config import get_settings

    return get_settings().database_url


def export_reranker_step1_data(
    db: Session,
    *,
    output_dir: Path,
    sample_size: int = 5000,
    seed: int = 51,
    eval_query_files: Iterable[Path] = DEFAULT_EVAL_QUERY_FILES,
) -> ExportSummary:
    output_dir.mkdir(parents=True, exist_ok=True)
    qa_pairs = export_qa_log_pairs(db)
    sampled_chunks = sample_high_quality_chunks(db, sample_size=sample_size, seed=seed)
    eval_queries = collect_eval_queries(eval_query_files)

    write_jsonl(output_dir / "qa_log_pairs.jsonl", qa_pairs)
    write_jsonl(output_dir / "sampled_chunks.jsonl", sampled_chunks)
    write_jsonl(output_dir / "eval_queries.jsonl", eval_queries)
    summary = ExportSummary(
        qa_log_pairs=len(qa_pairs),
        sampled_chunks=len(sampled_chunks),
        eval_queries=len(eval_queries),
        output_dir=str(output_dir),
    )
    (output_dir / "summary.json").write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def export_qa_log_pairs(db: Session) -> list[QALogPair]:
    if not table_exists(db, QuestionAnswerLog.__tablename__) or not table_exists(db, Chunk.__tablename__):
        return []
    logs = list(db.scalars(select(QuestionAnswerLog).order_by(QuestionAnswerLog.id)).all())
    chunk_ids = sorted({chunk_id for log in logs for chunk_id in safe_int_list(log.retrieved_chunk_ids)})
    chunks = load_chunks(db, chunk_ids)
    rows: list[QALogPair] = []
    seen: set[tuple[int, int, int]] = set()
    for log in logs:
        retrieved = safe_int_list(log.retrieved_chunk_ids)
        cited_positions = set(safe_int_list(log.citations))
        for rank, chunk_id in enumerate(retrieved, start=1):
            chunk = chunks.get(chunk_id)
            if chunk is None:
                continue
            citation_index = rank if rank in cited_positions else None
            label = 1 if citation_index is not None else 0
            key = (log.id, chunk_id, label)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                QALogPair(
                    query=normalize_text(log.question),
                    chunk_id=chunk.id,
                    label=label,
                    source="qa_log_cited" if label else "qa_log_retrieved_negative",
                    qa_log_id=log.id,
                    rank=rank,
                    citation_index=citation_index,
                    document_id=chunk.document_id,
                    chunk_type=chunk.chunk_type,
                    content=safe_passage(chunk.content),
                )
            )
    return rows


def sample_high_quality_chunks(db: Session, *, sample_size: int, seed: int) -> list[SampledChunk]:
    if not table_exists(db, Chunk.__tablename__) or not table_exists(db, Document.__tablename__):
        return []
    child = aliased(Chunk)
    statement = (
        select(Chunk, Document.title)
        .join(Document, Document.id == Chunk.document_id)
        .outerjoin(child, child.parent_chunk_id == Chunk.id)
        .where(func.length(Chunk.content).between(100, 2000))
        .where(child.id.is_(None))
        .where(Chunk.chunk_type.in_(("text", "table", "image_description")))
    )
    candidates = list(db.execute(statement).all())
    rng = random.Random(seed)
    rng.shuffle(candidates)
    selected = candidates[: max(sample_size, 0)]
    return [
        SampledChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=normalize_text(title),
            chunk_type=chunk.chunk_type,
            content=safe_passage(chunk.content),
            char_count=chunk.char_count,
        )
        for chunk, title in selected
    ]


def table_exists(db: Session, table_name: str) -> bool:
    return inspect(db.get_bind()).has_table(table_name)


def collect_eval_queries(paths: Iterable[Path]) -> list[EvalQuery]:
    rows: list[EvalQuery] = []
    seen_questions: set[str] = set()
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader, start=1):
                question = first_non_empty(row, "question", "query", "user_question")
                if not question:
                    continue
                normalized_question = normalize_text(question)
                if normalized_question in seen_questions or not looks_domain_relevant(normalized_question):
                    continue
                seen_questions.add(normalized_question)
                rows.append(
                    EvalQuery(
                        query_id=first_non_empty(row, "query_id", "id") or f"{path.stem}_{index}",
                        question=normalized_question,
                        source_file=path.as_posix(),
                        category=first_non_empty(row, "category", "scenario", "mode"),
                        expected_source_terms=first_non_empty(
                            row,
                            "expected_source_terms",
                            "expected_answer_points",
                            "expected_source_type",
                            "top_source_id",
                        ),
                        expected_refused=first_non_empty(row, "expected_refused", "refused"),
                    )
                )
    return rows


def load_chunks(db: Session, chunk_ids: list[int]) -> dict[int, Chunk]:
    if not chunk_ids:
        return {}
    chunks = db.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()
    return {chunk.id: chunk for chunk in chunks}


def safe_int_list(values_json: str) -> list[int]:
    try:
        return deserialize_int_list(values_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def first_non_empty(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and value.strip():
            return normalize_text(value)
    return ""


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").split())


def safe_passage(value: str, max_length: int = 2000) -> str:
    return normalize_text(value)[:max_length]


def looks_domain_relevant(question: str) -> bool:
    lowered = question.casefold()
    return any(term in lowered for term in DOMAIN_TERMS)


def write_jsonl(path: Path, rows: Iterable[object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            payload = asdict(row) if hasattr(row, "__dataclass_fields__") else row
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()

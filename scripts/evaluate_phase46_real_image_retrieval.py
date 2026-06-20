from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.session import create_database_engine
from app.services.agent import tools as agent_tools
from app.services.agent.tools import AgentToolbox, FigureSearchResult
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider
from app.services.retrieval.query_embedding_cache import clear_query_embedding_cache
from app.services.retrieval.vector_cache import invalidate_vector_index_cache


DEFAULT_QUESTIONS_CSV = Path("data/evaluation/phase46_real_image_retrieval_questions.csv")
DEFAULT_RESULTS_CSV = Path("data/evaluation/phase46_real_image_retrieval_results.csv")
DEFAULT_SUMMARY_CSV = Path("data/evaluation/phase46_real_image_retrieval_summary.csv")

POSITIVE_CATEGORIES = {"must_have_image", "image_helpful"}
NEGATIVE_CATEGORIES = {"text_only", "no_image"}
QUERY_EMBEDDING_MODES = {"stored_embedding_proxy", "real"}
GENERIC_CURVE_TERMS = ("曲线", "curve", "plot", "拟合")


@dataclass(frozen=True)
class EvaluationQuestion:
    query_id: str
    question: str
    category: str
    expected_has_image: bool
    expected_image_keywords: list[str]
    expected_caption_keywords: list[str]
    expected_doc_keywords: list[str]
    expected_source_image_path: str
    expected_page_number: int | None
    notes: str


@dataclass(frozen=True)
class EvaluationRecord:
    query_id: str
    question: str
    category: str
    expected_has_image: bool
    returned_image_count: int
    relevant_image_count: int
    top1_relevant: bool
    suppressed: bool
    expected_path_hit: bool
    top1_caption_match: bool
    topk_caption_match: bool
    top1_doc_match: bool
    wrong_generic_curve: bool
    top_score: float
    top_caption: str
    top_page_number: int | None
    top_document_title: str
    top_source_image_path: str
    top_image_url: str
    captions_present: int
    page_numbers_present: int
    error: str


class StoredEmbeddingProxyProvider:
    """Embedding provider that returns preloaded vectors for evaluation queries."""

    def __init__(
        self,
        *,
        provider_name: str,
        model_name: str,
        dimension: int,
        query_vectors: dict[str, list[float]],
    ) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self.dimension = dimension
        self.query_vectors = query_vectors

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return list(self.query_vectors.get(normalize_query(query), [0.0] * self.dimension))


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    questions = read_questions(args.questions_csv)
    args.results_csv.parent.mkdir(parents=True, exist_ok=True)
    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)

    original_min_score = agent_tools.MIN_IMAGE_RELEVANCE_SCORE
    agent_tools.MIN_IMAGE_RELEVANCE_SCORE = args.min_score
    try:
        records = run_evaluation(
            questions=questions,
            database_url=args.database_url or get_settings().database_url,
            top_k=args.top_k,
            query_embedding_mode=args.query_embedding_mode,
        )
    finally:
        agent_tools.MIN_IMAGE_RELEVANCE_SCORE = original_min_score

    summary = summarize_records(
        records,
        elapsed_seconds=time.perf_counter() - started,
        min_score=args.min_score,
        query_embedding_mode=args.query_embedding_mode,
    )
    write_results(args.results_csv, records)
    write_summary(args.summary_csv, summary)

    print(f"questions={len(questions)}")
    print(f"query_embedding_mode={args.query_embedding_mode}")
    for metric in (
        "image_precision",
        "image_recall",
        "must_have_recall",
        "image_helpful_hit_rate",
        "image_suppression",
        "topk_caption_match_rate",
        "wrong_generic_curve_rate",
        "threshold_decision",
    ):
        print(f"{metric}={summary[metric]}")
    print(f"results_csv={args.results_csv}")
    print(f"summary_csv={args.summary_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 46 real-corpus image retrieval without LLM Judge.",
    )
    parser.add_argument("--questions-csv", type=Path, default=DEFAULT_QUESTIONS_CSV)
    parser.add_argument("--results-csv", type=Path, default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--min-score", type=float, default=agent_tools.MIN_IMAGE_RELEVANCE_SCORE)
    parser.add_argument(
        "--query-embedding-mode",
        choices=sorted(QUERY_EMBEDDING_MODES),
        default="stored_embedding_proxy",
        help=(
            "stored_embedding_proxy is offline and uses existing expected image embeddings; "
            "real uses configured query embedding provider and may call a real API."
        ),
    )
    parser.add_argument("--database-url", default="")
    return parser.parse_args()


def read_questions(path: Path) -> list[EvaluationQuestion]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    questions: list[EvaluationQuestion] = []
    for row in rows:
        category = (row.get("category") or "").strip()
        if category not in POSITIVE_CATEGORIES | NEGATIVE_CATEGORIES:
            raise ValueError(f"unsupported category: {category}")
        expected_has_image = parse_bool(row.get("expected_has_image") or "")
        questions.append(
            EvaluationQuestion(
                query_id=(row.get("query_id") or "").strip(),
                question=(row.get("question") or "").strip(),
                category=category,
                expected_has_image=expected_has_image,
                expected_image_keywords=split_terms(row.get("expected_image_keywords") or ""),
                expected_caption_keywords=split_terms(row.get("expected_caption_keywords") or ""),
                expected_doc_keywords=split_terms(row.get("expected_doc_keywords") or ""),
                expected_source_image_path=(row.get("expected_source_image_path") or "").strip(),
                expected_page_number=parse_optional_int(row.get("expected_page_number") or ""),
                notes=(row.get("notes") or "").strip(),
            )
        )
    if len(questions) < 100:
        raise ValueError("real image retrieval evaluation set must contain at least 100 questions")
    return questions


def parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"invalid boolean value: {value}")


def split_terms(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def parse_optional_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    return int(value)


def run_evaluation(
    *,
    questions: list[EvaluationQuestion],
    database_url: str,
    top_k: int,
    query_embedding_mode: str,
) -> list[EvaluationRecord]:
    engine = create_database_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        with SessionLocal() as db:
            provider = create_provider_for_mode(db, questions, query_embedding_mode)
            clear_query_embedding_cache()
            invalidate_vector_index_cache(db, provider)
            toolbox = AgentToolbox(
                db=db,
                embedding_provider=provider,
                chat_model_provider=DeterministicChatModelProvider(),
                log_answers=False,
            )
            return [
                evaluate_question(question=question, toolbox=toolbox, top_k=top_k)
                for question in questions
            ]
    finally:
        engine.dispose()


def create_provider_for_mode(
    db,
    questions: list[EvaluationQuestion],
    query_embedding_mode: str,
) -> EmbeddingProvider:
    if query_embedding_mode == "real":
        settings = get_settings()
        return create_embedding_provider(
            provider_name=settings.embedding_provider,
            model_name=settings.embedding_model_name,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            dimension=settings.embedding_dimension or None,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    provider_name, model_name, dimension = detect_image_embedding_identity(db)
    query_vectors = load_expected_query_vectors(
        db,
        questions=questions,
        provider_name=provider_name,
        model_name=model_name,
        dimension=dimension,
    )
    return StoredEmbeddingProxyProvider(
        provider_name=provider_name,
        model_name=model_name,
        dimension=dimension,
        query_vectors=query_vectors,
    )


def detect_image_embedding_identity(db) -> tuple[str, str, int]:
    row = db.execute(
        text(
            """
            select ce.provider, ce.model_name, ce.dimension, count(*) as count
            from chunk_embeddings ce
            join chunks c on c.id = ce.chunk_id
            where c.chunk_type = 'image_description'
            group by ce.provider, ce.model_name, ce.dimension
            order by count desc
            limit 1
            """
        )
    ).mappings().first()
    if row is None:
        raise RuntimeError("no image_description embeddings found")
    return str(row["provider"]), str(row["model_name"]), int(row["dimension"])


def load_expected_query_vectors(
    db,
    *,
    questions: list[EvaluationQuestion],
    provider_name: str,
    model_name: str,
    dimension: int,
) -> dict[str, list[float]]:
    vectors: dict[str, list[float]] = {}
    for question in questions:
        normalized_query = normalize_query(question.question)
        if not question.expected_has_image or not question.expected_source_image_path:
            vectors[normalized_query] = [0.0] * dimension
            continue
        row = db.execute(
            text(
                """
                select ce.embedding_json
                from chunks c
                join chunk_embeddings ce on ce.chunk_id = c.id
                where c.source_image_path = :source_image_path
                  and ce.provider = :provider
                  and ce.model_name = :model_name
                  and ce.dimension = :dimension
                order by c.id
                limit 1
                """
            ),
            {
                "source_image_path": question.expected_source_image_path,
                "provider": provider_name,
                "model_name": model_name,
                "dimension": dimension,
            },
        ).mappings().first()
        if row is None:
            vectors[normalized_query] = [0.0] * dimension
            continue
        vector = json.loads(row["embedding_json"])
        vectors[normalized_query] = [float(value) for value in vector]
    return vectors


def normalize_query(query: str) -> str:
    return " ".join((query or "").strip().split())


def evaluate_question(
    *,
    question: EvaluationQuestion,
    toolbox: AgentToolbox,
    top_k: int,
) -> EvaluationRecord:
    try:
        result = toolbox.search_figures(query=question.question, top_k=top_k)
        figures = result.figure_results
        error = ""
    except Exception as exc:  # pragma: no cover - defensive CSV reporting path.
        figures = []
        error = type(exc).__name__
    relevant_count = sum(1 for figure in figures if figure_is_relevant(figure, question))
    top = figures[0] if figures else None
    return EvaluationRecord(
        query_id=question.query_id,
        question=question.question,
        category=question.category,
        expected_has_image=question.expected_has_image,
        returned_image_count=len(figures),
        relevant_image_count=relevant_count,
        top1_relevant=bool(top and figure_is_relevant(top, question)),
        suppressed=not bool(figures),
        expected_path_hit=any(figure.source_image_path == question.expected_source_image_path for figure in figures),
        top1_caption_match=bool(top and caption_matches(top, question)),
        topk_caption_match=any(caption_matches(figure, question) for figure in figures),
        top1_doc_match=bool(top and doc_matches(top, question)),
        wrong_generic_curve=wrong_generic_curve_returned(figures, question),
        top_score=round(top.relevance_score, 6) if top else 0.0,
        top_caption=top.caption or "" if top else "",
        top_page_number=top.page_number if top else None,
        top_document_title=top.document_title if top else "",
        top_source_image_path=top.source_image_path if top else "",
        top_image_url=top.image_url if top else "",
        captions_present=sum(1 for figure in figures if figure.caption),
        page_numbers_present=sum(1 for figure in figures if figure.page_number is not None),
        error=error,
    )


def figure_is_relevant(figure: FigureSearchResult, question: EvaluationQuestion) -> bool:
    if question.expected_source_image_path and figure.source_image_path == question.expected_source_image_path:
        return True
    haystack = figure_haystack(figure)
    return terms_match_any(haystack, question.expected_image_keywords + question.expected_caption_keywords)


def caption_matches(figure: FigureSearchResult, question: EvaluationQuestion) -> bool:
    if not question.expected_caption_keywords:
        return False
    return terms_match_any((figure.caption or "").casefold(), question.expected_caption_keywords)


def doc_matches(figure: FigureSearchResult, question: EvaluationQuestion) -> bool:
    if not question.expected_doc_keywords:
        return False
    return terms_match_any((figure.document_title or "").casefold(), question.expected_doc_keywords)


def terms_match_any(haystack: str, terms: list[str]) -> bool:
    normalized = haystack.casefold()
    return any(term.casefold() in normalized for term in terms if term)


def figure_haystack(figure: FigureSearchResult) -> str:
    return " ".join(
        [
            figure.caption or "",
            figure.description_snippet or "",
            figure.document_title or "",
            figure.source_image_path or "",
        ]
    ).casefold()


def wrong_generic_curve_returned(figures: list[FigureSearchResult], question: EvaluationQuestion) -> bool:
    if not figures:
        return False
    curve_query = terms_match_any(
        f"{question.question} {' '.join(question.expected_image_keywords)}",
        ["曲线", "curve", "应力应变", "绝热温升", "温度", "水化热"],
    )
    if not curve_query:
        return False
    for figure in figures:
        haystack = figure_haystack(figure)
        if terms_match_any(haystack, list(GENERIC_CURVE_TERMS)) and not figure_is_relevant(figure, question):
            return True
    return False


def summarize_records(
    records: list[EvaluationRecord],
    *,
    elapsed_seconds: float,
    min_score: float,
    query_embedding_mode: str,
) -> dict[str, str]:
    category_counts = Counter(record.category for record in records)
    positives = [record for record in records if record.expected_has_image]
    must_have = [record for record in records if record.category == "must_have_image"]
    helpful = [record for record in records if record.category == "image_helpful"]
    negatives = [record for record in records if not record.expected_has_image]
    returned = [record for record in records if record.returned_image_count > 0]
    total_returned = sum(record.returned_image_count for record in records)
    total_relevant = sum(record.relevant_image_count for record in records)
    total_captions = sum(record.captions_present for record in records)
    total_pages = sum(record.page_numbers_present for record in records)
    curve_rows = [record for record in records if is_curve_record(record)]

    image_precision = safe_ratio(total_relevant, total_returned)
    image_recall = safe_ratio(
        sum(1 for record in positives if record.relevant_image_count > 0),
        len(positives),
    )
    must_have_recall = safe_ratio(
        sum(1 for record in must_have if record.relevant_image_count > 0),
        len(must_have),
    )
    helpful_hit_rate = safe_ratio(
        sum(1 for record in helpful if record.relevant_image_count > 0),
        len(helpful),
    )
    image_suppression = safe_ratio(
        sum(1 for record in negatives if record.returned_image_count == 0),
        len(negatives),
    )
    top1_caption_match_rate = safe_ratio(
        sum(1 for record in positives if record.top1_caption_match),
        len(positives),
    )
    topk_caption_match_rate = safe_ratio(
        sum(1 for record in positives if record.topk_caption_match),
        len(positives),
    )
    expected_path_hit_rate = safe_ratio(
        sum(1 for record in positives if record.expected_path_hit),
        len(positives),
    )
    caption_coverage = safe_ratio(total_captions, total_returned)
    page_number_coverage = safe_ratio(total_pages, total_returned)
    wrong_generic_curve_rate = safe_ratio(
        sum(1 for record in curve_rows if record.wrong_generic_curve),
        len(curve_rows),
    )

    return {
        "question_count": str(len(records)),
        "must_have_image_count": str(category_counts["must_have_image"]),
        "image_helpful_count": str(category_counts["image_helpful"]),
        "text_only_count": str(category_counts["text_only"]),
        "no_image_count": str(category_counts["no_image"]),
        "query_embedding_mode": query_embedding_mode,
        "min_image_relevance_score": format_metric(min_score),
        "returned_image_count": str(total_returned),
        "relevant_image_count": str(total_relevant),
        "image_precision": format_metric(image_precision),
        "image_recall": format_metric(image_recall),
        "must_have_recall": format_metric(must_have_recall),
        "image_helpful_hit_rate": format_metric(helpful_hit_rate),
        "image_suppression": format_metric(image_suppression),
        "top1_caption_match_rate": format_metric(top1_caption_match_rate),
        "topk_caption_match_rate": format_metric(topk_caption_match_rate),
        "expected_path_hit_rate": format_metric(expected_path_hit_rate),
        "caption_coverage_in_results": format_metric(caption_coverage),
        "page_number_coverage_in_results": format_metric(page_number_coverage),
        "wrong_generic_curve_rate": format_metric(wrong_generic_curve_rate),
        "returned_question_count": str(len(returned)),
        "error_count": str(sum(1 for record in records if record.error)),
        "threshold_decision": threshold_decision(
            image_precision=image_precision,
            must_have_recall=must_have_recall,
            image_suppression=image_suppression,
            topk_caption_match_rate=topk_caption_match_rate,
            wrong_generic_curve_rate=wrong_generic_curve_rate,
        ),
        "elapsed_seconds": f"{elapsed_seconds:.3f}",
    }


def is_curve_record(record: EvaluationRecord) -> bool:
    text = f"{record.question} {record.top_caption}".casefold()
    return terms_match_any(text, ["曲线", "curve", "应力应变", "温度", "温升", "水化热"])


def threshold_decision(
    *,
    image_precision: float,
    must_have_recall: float,
    image_suppression: float,
    topk_caption_match_rate: float,
    wrong_generic_curve_rate: float,
) -> str:
    if (
        image_precision >= 0.75
        and must_have_recall >= 0.75
        and image_suppression >= 0.85
        and topk_caption_match_rate >= 0.70
        and wrong_generic_curve_rate <= 0.10
    ):
        return "pass"
    return "needs_rerank"


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def format_metric(value: float) -> str:
    return f"{value:.4f}"


def write_results(path: Path, records: list[EvaluationRecord]) -> None:
    fields = list(EvaluationRecord.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(record.__dict__)


def write_summary(path: Path, summary: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            writer.writerow({"metric": key, "value": value})


if __name__ == "__main__":
    main()

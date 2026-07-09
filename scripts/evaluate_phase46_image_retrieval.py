from __future__ import annotations

import argparse
import csv
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    ChunkEmbeddingCreate,
    ChunkEmbeddingRepository,
    DocumentCreate,
    DocumentRepository,
)
from app.db.session import create_sqlite_engine
from app.services.agent.tools import AgentToolbox, MIN_IMAGE_RELEVANCE_SCORE
from app.services.agent.tools import query_requests_figure
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_cache import calculate_text_hash, invalidate_vector_index_cache


DEFAULT_QUESTIONS_CSV = Path("data/evaluation/phase46_image_retrieval_questions.csv")
DEFAULT_RESULTS_CSV = Path("data/evaluation/phase46_image_retrieval_results.csv")
DEFAULT_SUMMARY_CSV = Path("data/evaluation/phase46_image_retrieval_summary.csv")
FIXTURE_IMAGE_DIR = Path("data/images/phase46_eval_fixture")

POSITIVE_CATEGORIES = {"must_have_image", "image_helpful"}
NEGATIVE_CATEGORIES = {"text_only", "no_image"}


@dataclass(frozen=True)
class EvaluationQuestion:
    query_id: str
    question: str
    category: str
    expected_has_image: bool
    expected_image_keywords: list[str]
    notes: str


@dataclass(frozen=True)
class EvaluationRecord:
    query_id: str
    category: str
    expected_has_image: bool
    returned_image_count: int
    relevant_image_count: int
    suppressed: bool
    top_score: float
    top_caption: str
    top_page_number: int | None
    top_document_title: str
    top_image_url: str
    quality_ok: bool
    caption_present: bool
    page_number_present: bool


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    questions = read_questions(args.questions_csv)
    args.results_csv.parent.mkdir(parents=True, exist_ok=True)
    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="phase46-image-eval-") as tmpdir:
        db_path = Path(tmpdir) / "eval.sqlite"
        records = run_deterministic_evaluation(
            questions=questions,
            database_url=f"sqlite:///{db_path.as_posix()}",
            top_k=args.top_k,
        )

    summary = summarize_records(records, elapsed_seconds=time.perf_counter() - started)
    write_results(args.results_csv, records)
    write_summary(args.summary_csv, summary)

    print(f"questions={len(questions)}")
    print(f"image_precision={summary['image_precision']}")
    print(f"image_recall={summary['image_recall']}")
    print(f"image_suppression={summary['image_suppression']}")
    print(f"min_image_relevance_score={summary['min_image_relevance_score']}")
    print(f"results_csv={args.results_csv}")
    print(f"summary_csv={args.summary_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 46 figure retrieval without real API calls.",
    )
    parser.add_argument("--questions-csv", type=Path, default=DEFAULT_QUESTIONS_CSV)
    parser.add_argument("--results-csv", type=Path, default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--top-k", type=int, default=4)
    return parser.parse_args()


def read_questions(path: Path) -> list[EvaluationQuestion]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    questions: list[EvaluationQuestion] = []
    for row in rows:
        category = (row.get("category") or "").strip()
        if category not in POSITIVE_CATEGORIES | NEGATIVE_CATEGORIES:
            raise ValueError(f"unsupported category: {category}")
        keywords = [
            item.strip()
            for item in (row.get("expected_image_keywords") or "").split("|")
            if item.strip()
        ]
        expected_has_image = parse_bool(row.get("expected_has_image") or "")
        questions.append(
            EvaluationQuestion(
                query_id=(row.get("query_id") or "").strip(),
                question=(row.get("question") or "").strip(),
                category=category,
                expected_has_image=expected_has_image,
                expected_image_keywords=keywords,
                notes=(row.get("notes") or "").strip(),
            )
        )
    if len(questions) < 30:
        raise ValueError("evaluation set must contain at least 30 questions")
    return questions


def parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"invalid boolean value: {value}")


def run_deterministic_evaluation(
    *,
    questions: list[EvaluationQuestion],
    database_url: str,
    top_k: int,
) -> list[EvaluationRecord]:
    provider = DeterministicEmbeddingProvider(dimension=64)
    engine = create_sqlite_engine(database_url)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        with TestingSessionLocal() as db:
            seed_fixture_corpus(db, questions, provider)
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


def seed_fixture_corpus(
    db,
    questions: list[EvaluationQuestion],
    provider: DeterministicEmbeddingProvider,
) -> None:
    FIXTURE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    embedding_repository = ChunkEmbeddingRepository(db)
    positive_questions = [question for question in questions if question.expected_has_image]
    for index, question in enumerate(positive_questions, start=1):
        image_path = FIXTURE_IMAGE_DIR / f"page{index}_img1.png"
        source_image_path = f"data/images/phase46_eval_fixture/page{index}_img1.png"
        create_fixture_image(image_path, question.query_id)
        keyword_text = " ".join(question.expected_image_keywords)
        content = (
            f"{question.question} {keyword_text}. "
            f"Phase 46 deterministic figure retrieval fixture for {question.category}."
        )
        caption = f"Fig. {index} {keyword_text}".strip()
        document = DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title=f"Phase 46 Image Retrieval Fixture {index}",
                source_type="evaluation_fixture",
                source_path=f"phase46_fixture_{index}.pdf",
                file_name=f"phase46_fixture_{index}.pdf",
                file_extension=".pdf",
                content_hash=f"phase46-image-fixture-{index}",
                raw_path=f"data/raw/phase46_fixture_{index}.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content=content,
                    char_count=len(content),
                    heading_path="Figure",
                    start_char=None,
                    end_char=None,
                    chunk_type="image_description",
                    source_image_path=source_image_path,
                    caption=caption,
                    page_number=index,
                )
            ],
        )
        chunk = document.chunks[0]
        embedding_repository.save_embedding(
            ChunkEmbeddingCreate(
                chunk_id=chunk.id,
                provider=provider.provider_name,
                model_name=provider.model_name,
                dimension=provider.dimension,
                embedding=provider.embed_query(content),
                content_hash=calculate_text_hash(content),
            )
        )


def create_fixture_image(path: Path, label: str) -> None:
    image = Image.new("RGB", (96, 72), color=(240, 245, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 88, 64), outline=(50, 90, 140), width=2)
    draw.text((14, 28), label[:12], fill=(20, 40, 70))
    image.save(path)


def evaluate_question(
    *,
    question: EvaluationQuestion,
    toolbox: AgentToolbox,
    top_k: int,
) -> EvaluationRecord:
    if not question.expected_has_image and not query_requests_figure(question.question):
        return EvaluationRecord(
            query_id=question.query_id,
            category=question.category,
            expected_has_image=question.expected_has_image,
            returned_image_count=0,
            relevant_image_count=0,
            suppressed=True,
            top_score=0.0,
            top_caption="",
            top_page_number=None,
            top_document_title="",
            top_image_url="",
            quality_ok=False,
            caption_present=False,
            page_number_present=False,
        )

    result = toolbox.search_figures(query=question.question, top_k=top_k)
    figures = result.figure_results
    relevant_count = sum(
        1 for figure in figures if figure_matches_keywords(figure, question.expected_image_keywords)
    )
    top = figures[0] if figures else None
    return EvaluationRecord(
        query_id=question.query_id,
        category=question.category,
        expected_has_image=question.expected_has_image,
        returned_image_count=len(figures),
        relevant_image_count=relevant_count,
        suppressed=not bool(figures),
        top_score=round(top.relevance_score, 6) if top else 0.0,
        top_caption=top.caption or "" if top else "",
        top_page_number=top.page_number if top else None,
        top_document_title=top.document_title if top else "",
        top_image_url=top.image_url if top else "",
        quality_ok=bool(figures),
        caption_present=bool(top and top.caption),
        page_number_present=bool(top and top.page_number),
    )


def figure_matches_keywords(figure, keywords: list[str]) -> bool:
    if not keywords:
        return False
    haystack = " ".join(
        [
            figure.caption or "",
            figure.description_snippet or "",
            figure.document_title or "",
        ]
    ).casefold()
    return any(keyword.casefold() in haystack for keyword in keywords)


def summarize_records(
    records: list[EvaluationRecord],
    *,
    elapsed_seconds: float,
) -> dict[str, str]:
    total_returned = sum(record.returned_image_count for record in records)
    total_relevant = sum(record.relevant_image_count for record in records)
    positive = [record for record in records if record.expected_has_image]
    must_have = [record for record in records if record.category == "must_have_image"]
    negative = [record for record in records if not record.expected_has_image]
    returned_records = [record for record in records if record.returned_image_count > 0]
    category_counts = Counter(record.category for record in records)

    image_precision = safe_ratio(total_relevant, total_returned)
    image_recall = safe_ratio(
        sum(1 for record in must_have if record.relevant_image_count > 0),
        len(must_have),
    )
    image_suppression = safe_ratio(
        sum(1 for record in negative if record.returned_image_count == 0),
        len(negative),
    )
    image_quality_rate = safe_ratio(
        sum(1 for record in returned_records if record.quality_ok),
        len(returned_records),
    )
    caption_coverage = safe_ratio(
        sum(1 for record in returned_records if record.caption_present),
        len(returned_records),
    )
    page_number_coverage = safe_ratio(
        sum(1 for record in returned_records if record.page_number_present),
        len(returned_records),
    )
    positive_hit_rate = safe_ratio(
        sum(1 for record in positive if record.returned_image_count > 0),
        len(positive),
    )

    return {
        "question_count": str(len(records)),
        "must_have_image_count": str(category_counts["must_have_image"]),
        "image_helpful_count": str(category_counts["image_helpful"]),
        "text_only_count": str(category_counts["text_only"]),
        "no_image_count": str(category_counts["no_image"]),
        "returned_image_count": str(total_returned),
        "relevant_image_count": str(total_relevant),
        "image_precision": format_metric(image_precision),
        "image_recall": format_metric(image_recall),
        "image_suppression": format_metric(image_suppression),
        "image_quality_rate": format_metric(image_quality_rate),
        "caption_coverage": format_metric(caption_coverage),
        "page_number_coverage": format_metric(page_number_coverage),
        "positive_hit_rate": format_metric(positive_hit_rate),
        "min_image_relevance_score": format_metric(MIN_IMAGE_RELEVANCE_SCORE),
        "threshold_decision": threshold_decision(
            image_precision=image_precision,
            image_recall=image_recall,
            image_suppression=image_suppression,
        ),
        "elapsed_seconds": f"{elapsed_seconds:.3f}",
    }


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def format_metric(value: float) -> str:
    return f"{value:.4f}"


def threshold_decision(
    *,
    image_precision: float,
    image_recall: float,
    image_suppression: float,
) -> str:
    if image_precision >= 0.85 and image_suppression >= 0.85 and image_recall >= 0.75:
        return "keep_current_threshold"
    if image_precision < 0.85 or image_suppression < 0.85:
        return "raise_threshold_or_tighten_query_gate"
    return "lower_threshold_or_expand_positive_query_terms"


def write_results(path: Path, records: list[EvaluationRecord]) -> None:
    fields = [
        "query_id",
        "category",
        "expected_has_image",
        "returned_image_count",
        "relevant_image_count",
        "suppressed",
        "top_score",
        "top_caption",
        "top_page_number",
        "top_document_title",
        "top_image_url",
        "quality_ok",
        "caption_present",
        "page_number_present",
    ]
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

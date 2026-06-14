from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.brain.config import RetrievalConfig  # noqa: E402
from app.services.brain.service import BrainService  # noqa: E402
from app.services.generation.chat_model import DeterministicChatModelProvider  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService  # noqa: E402
from app.services.retrieval.hybrid_rrf_tail import HybridRrfTailSearchService  # noqa: E402
from app.services.retrieval.rrf_fusion import RRFHybridSearchResult, RRFHybridSearchService  # noqa: E402


QUERY_PATH = ROOT / "data" / "evaluation" / "stage29_new_corpus_queries.csv"
RESULTS_PATH = ROOT / "data" / "evaluation" / "stage29_real_quality_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage29_real_quality_summary.csv"

RESULT_FIELDS = [
    "query_id",
    "question",
    "category",
    "expected_source_type",
    "expected_refused",
    "provider",
    "model_name",
    "retrieval_mode",
    "top_k",
    "precision_at_1",
    "precision_at_3",
    "precision_at_5",
    "coverage_ratio",
    "covered_points",
    "missing_points",
    "refused",
    "refusal_matched",
    "source_type_distribution",
    "top1_source_type",
    "top1_document_title",
    "top_titles",
    "latency_ms",
    "status",
    "error",
]

SUMMARY_FIELDS = [
    "provider",
    "model_name",
    "retrieval_mode",
    "real_config_status",
    "total_queries",
    "non_refusal_total",
    "precision_at_1",
    "precision_at_3",
    "precision_at_5",
    "avg_coverage_ratio",
    "refusal_total",
    "refusal_accuracy",
    "source_type_distribution",
    "decision",
    "next_action",
]


@dataclass(frozen=True)
class Stage29Query:
    query_id: str
    question: str
    category: str
    expected_source_type: str
    expected_answer_points: tuple[str, ...]
    expected_refused: bool
    notes: str


@dataclass(frozen=True)
class CoverageResult:
    ratio: float
    covered_points: tuple[str, ...]
    missing_points: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate stage 29 real retrieval quality on new corpus queries."
    )
    parser.add_argument("--queries", default=str(QUERY_PATH))
    parser.add_argument("--out-results", default=str(RESULTS_PATH))
    parser.add_argument("--out-summary", default=str(SUMMARY_PATH))
    parser.add_argument("--provider", default="glm")
    parser.add_argument(
        "--retrieval-mode",
        choices=["hybrid", "bm25_rrf", "hybrid_rrf_tail"],
        default="hybrid",
        help="Retrieval strategy used for non-refusal evidence collection.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def load_queries(path: Path) -> list[Stage29Query]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {
            "query_id",
            "question",
            "category",
            "expected_source_type",
            "expected_answer_points",
            "expected_refused",
            "notes",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing stage29 query fields: {', '.join(sorted(missing))}")
        return [
            Stage29Query(
                query_id=row["query_id"].strip(),
                question=row["question"].strip(),
                category=row["category"].strip(),
                expected_source_type=row["expected_source_type"].strip(),
                expected_answer_points=split_points(row["expected_answer_points"]),
                expected_refused=parse_bool(row["expected_refused"]),
                notes=row.get("notes", "").strip(),
            )
            for row in reader
            if row.get("query_id", "").strip()
        ]


def split_points(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or "").split(";") if part.strip())


def parse_bool(value: str) -> bool:
    return (value or "").strip().casefold() in {"true", "yes", "1"}


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").casefold())


SearchResult = HybridSearchResult | RRFHybridSearchResult


def result_evidence(result: SearchResult) -> str:
    return " ".join(
        part
        for part in [
            result.document_title,
            result.heading_path or "",
            result.content,
        ]
        if part
    )


def result_matches_query(result: SearchResult, query: Stage29Query) -> bool:
    if query.expected_source_type != "any" and result.source_type != query.expected_source_type:
        return False
    evidence = normalize_for_match(result_evidence(result))
    return any(normalize_for_match(point) in evidence for point in query.expected_answer_points)


def hit_at_k(results: list[SearchResult], query: Stage29Query, k: int) -> bool:
    return any(result_matches_query(result, query) for result in results[:k])


def coverage_ratio(results: list[SearchResult], query: Stage29Query) -> CoverageResult:
    if not query.expected_answer_points:
        return CoverageResult(0.0, (), ())
    evidence = normalize_for_match(" ".join(result_evidence(result) for result in results))
    covered: list[str] = []
    missing: list[str] = []
    for point in query.expected_answer_points:
        if normalize_for_match(point) in evidence:
            covered.append(point)
        else:
            missing.append(point)
    return CoverageResult(
        ratio=round(len(covered) / len(query.expected_answer_points), 3),
        covered_points=tuple(covered),
        missing_points=tuple(missing),
    )


def source_type_distribution(results: list[SearchResult]) -> str:
    counts = Counter(result.source_type for result in results)
    return ";".join(f"{source_type}:{count}" for source_type, count in sorted(counts.items()))


def evaluate_query(
    query: Stage29Query,
    *,
    search_service: HybridSearchService | RRFHybridSearchService,
    brain_service: BrainService,
    provider: str,
    model_name: str,
    retrieval_mode: str,
    top_k: int,
) -> dict[str, str]:
    started = time.perf_counter()
    try:
        results = search_service.search(query.question, top_k=top_k)
        coverage = coverage_ratio(results, query)
        refused = ""
        refusal_matched = ""
        if query.expected_refused:
            answer = brain_service.answer(
                question=query.question,
                config=RetrievalConfig(retrieval_mode="hybrid", top_k=top_k),
            )
            refused_bool = bool(answer.refused)
            refused = str(refused_bool).lower()
            refusal_matched = str(refused_bool == query.expected_refused).lower()

        latency_ms = (time.perf_counter() - started) * 1000.0
        top1 = results[0] if results else None
        return {
            "query_id": query.query_id,
            "question": query.question,
            "category": query.category,
            "expected_source_type": query.expected_source_type,
            "expected_refused": str(query.expected_refused).lower(),
            "provider": provider,
            "model_name": model_name,
            "retrieval_mode": retrieval_mode,
            "top_k": str(top_k),
            "precision_at_1": str(hit_at_k(results, query, 1)).lower(),
            "precision_at_3": str(hit_at_k(results, query, min(3, top_k))).lower(),
            "precision_at_5": str(hit_at_k(results, query, min(5, top_k))).lower(),
            "coverage_ratio": f"{coverage.ratio:.3f}",
            "covered_points": ";".join(coverage.covered_points),
            "missing_points": ";".join(coverage.missing_points),
            "refused": refused,
            "refusal_matched": refusal_matched,
            "source_type_distribution": source_type_distribution(results),
            "top1_source_type": top1.source_type if top1 else "",
            "top1_document_title": top1.document_title[:160] if top1 else "",
            "top_titles": " || ".join(result.document_title[:80] for result in results),
            "latency_ms": f"{latency_ms:.2f}",
            "status": "completed",
            "error": "",
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "query_id": query.query_id,
            "question": query.question,
            "category": query.category,
            "expected_source_type": query.expected_source_type,
            "expected_refused": str(query.expected_refused).lower(),
            "provider": provider,
            "model_name": model_name,
            "retrieval_mode": retrieval_mode,
            "top_k": str(top_k),
            "precision_at_1": "false",
            "precision_at_3": "false",
            "precision_at_5": "false",
            "coverage_ratio": "0.000",
            "covered_points": "",
            "missing_points": ";".join(query.expected_answer_points),
            "refused": "",
            "refusal_matched": "",
            "source_type_distribution": "",
            "top1_source_type": "",
            "top1_document_title": "",
            "top_titles": "",
            "latency_ms": f"{latency_ms:.2f}",
            "status": "error",
            "error": sanitize_error(exc),
        }


def summarize_results(rows: list[dict[str, str]], provider: str, model_name: str, retrieval_mode: str = "hybrid") -> dict[str, str]:
    non_refusal = [row for row in rows if row["expected_refused"] == "false"]
    refusal = [row for row in rows if row["expected_refused"] == "true"]
    source_counts: Counter[str] = Counter()
    for row in rows:
        for part in row["source_type_distribution"].split(";"):
            if not part or ":" not in part:
                continue
            source_type, count = part.split(":", 1)
            source_counts[source_type] += int(count)

    errors = [row for row in rows if row["status"] == "error"]
    precision1 = ratio(count_true(non_refusal, "precision_at_1"), len(non_refusal))
    precision3 = ratio(count_true(non_refusal, "precision_at_3"), len(non_refusal))
    precision5 = ratio(count_true(non_refusal, "precision_at_5"), len(non_refusal))
    avg_coverage = average([float(row["coverage_ratio"]) for row in non_refusal])
    refusal_accuracy = ratio(count_true(refusal, "refusal_matched"), len(refusal))
    decision = "completed_with_errors" if errors else "completed"
    next_action = (
        f"{len(errors)} queries errored; inspect stage29_real_quality_results.csv"
        if errors
        else "Review low coverage and missed source_type cases before human approval"
    )
    return {
        "provider": provider,
        "model_name": model_name,
        "retrieval_mode": retrieval_mode,
        "real_config_status": "error" if errors else "completed",
        "total_queries": str(len(rows)),
        "non_refusal_total": str(len(non_refusal)),
        "precision_at_1": f"{precision1:.3f}",
        "precision_at_3": f"{precision3:.3f}",
        "precision_at_5": f"{precision5:.3f}",
        "avg_coverage_ratio": f"{avg_coverage:.3f}",
        "refusal_total": str(len(refusal)),
        "refusal_accuracy": f"{refusal_accuracy:.3f}",
        "source_type_distribution": ";".join(
            f"{source_type}:{count}" for source_type, count in sorted(source_counts.items())
        ),
        "decision": decision,
        "next_action": next_action,
    }


def count_true(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if row.get(field) == "true")


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sanitize_error(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    settings = get_settings()
    api_key = (settings.embedding_api_key or "").strip()
    if api_key:
        message = message.replace(api_key, "<redacted>")
    message = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer <redacted>", message)
    return message[:240]


def force_deterministic_reranking() -> None:
    os.environ["RERANKING_PROVIDER"] = "deterministic"
    os.environ["RERANKING_MODEL_NAME"] = "keyword-overlap-reranker-v1"
    os.environ["RERANKING_API_KEY"] = ""
    os.environ["RERANKING_BASE_URL"] = ""
    get_settings.cache_clear()


def read_dotenv_value(path: Path, name: str) -> str:
    if not path.exists():
        return ""
    prefix = f"{name}="
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value.startswith(("'", '"')):
            return value[1:-1].strip()
        return value
    return ""


def env_value(name: str) -> str:
    return os.getenv(name, "").strip() or read_dotenv_value(ROOT / ".env", name)


def provider_setting(
    *,
    explicit: str,
    settings_value: str,
    settings_provider: str,
    expected_provider: str,
) -> str:
    if explicit.strip():
        return explicit.strip()
    if settings_provider.strip().casefold() == expected_provider:
        return settings_value.strip()
    return ""


def create_stage29_embedding_provider(provider_name: str, settings):
    normalized = (provider_name or settings.embedding_provider or "deterministic").strip().casefold()
    if normalized == "jina":
        return create_embedding_provider(
            provider_name="jina",
            model_name="jina-embeddings-v3",
            api_key=provider_setting(
                explicit=env_value("JINA_API_KEY"),
                settings_value=settings.embedding_api_key,
                settings_provider=settings.embedding_provider,
                expected_provider="jina",
            ),
            base_url=provider_setting(
                explicit=env_value("JINA_BASE_URL"),
                settings_value=settings.embedding_base_url,
                settings_provider=settings.embedding_provider,
                expected_provider="jina",
            ),
            dimension=1024,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    if normalized in {"paratera", "glm"}:
        return create_embedding_provider(
            provider_name="paratera",
            model_name="GLM-Embedding-3",
            api_key=provider_setting(
                explicit=env_value("PARATERA_API_KEY"),
                settings_value=settings.embedding_api_key,
                settings_provider=settings.embedding_provider,
                expected_provider="paratera",
            ),
            base_url=provider_setting(
                explicit=env_value("PARATERA_EMBEDDING_BASE_URL"),
                settings_value=settings.embedding_base_url,
                settings_provider=settings.embedding_provider,
                expected_provider="paratera",
            ),
            dimension=2048,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    return create_embedding_provider(
        provider_name=normalized,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


def main() -> None:
    args = parse_args()
    if args.top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    force_deterministic_reranking()
    settings = get_settings()
    provider = create_stage29_embedding_provider(args.provider, settings)
    queries = load_queries(Path(args.queries))

    init_db()
    with SessionLocal() as db:
        if args.retrieval_mode == "bm25_rrf":
            search_service = RRFHybridSearchService(db=db, embedding_provider=provider)
        elif args.retrieval_mode == "hybrid_rrf_tail":
            search_service = HybridRrfTailSearchService(
                db=db,
                embedding_provider=provider,
            )
        else:
            search_service = HybridSearchService(
                db=db,
                embedding_provider=provider,
                reranking_enabled=True,
            )
        brain_service = BrainService(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        rows = [
            evaluate_query(
                query,
                search_service=search_service,
                brain_service=brain_service,
                provider=provider.provider_name,
                model_name=provider.model_name,
                retrieval_mode=args.retrieval_mode,
                top_k=args.top_k,
            )
            for query in queries
        ]

    summary = summarize_results(rows, provider.provider_name, provider.model_name, args.retrieval_mode)
    write_csv(Path(args.out_results), RESULT_FIELDS, rows)
    write_csv(Path(args.out_summary), SUMMARY_FIELDS, [summary])

    print(
        "stage29 real quality "
        f"provider={provider.provider_name} model={provider.model_name} "
        f"retrieval_mode={args.retrieval_mode} "
        f"p@1={summary['precision_at_1']} p@3={summary['precision_at_3']} "
        f"p@5={summary['precision_at_5']} coverage={summary['avg_coverage_ratio']} "
        f"refusal_accuracy={summary['refusal_accuracy']}"
    )


if __name__ == "__main__":
    main()

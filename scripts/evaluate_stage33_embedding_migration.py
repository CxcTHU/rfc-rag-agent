from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchService  # noqa: E402
from scripts.evaluate_stage29_real_quality import (  # noqa: E402
    Stage29Query,
    coverage_ratio,
    force_deterministic_reranking,
    hit_at_k,
    load_queries,
    sanitize_error,
    source_type_distribution,
)


QUERY_PATH = ROOT / "data" / "evaluation" / "stage29_new_corpus_queries.csv"
RESULTS_PATH = ROOT / "data" / "evaluation" / "stage33_embedding_migration_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage33_embedding_migration_summary.csv"

RESULT_FIELDS = [
    "query_id",
    "category",
    "expected_refused",
    "candidate",
    "provider",
    "model_name",
    "dimension",
    "top_k",
    "precision_at_1",
    "precision_at_3",
    "precision_at_5",
    "hit_at_5",
    "coverage_ratio",
    "source_type_distribution",
    "top1_source_type",
    "top1_document_title",
    "latency_ms",
    "status",
    "error",
]

SUMMARY_FIELDS = [
    "candidate",
    "provider",
    "model_name",
    "dimension",
    "status",
    "total_queries",
    "completed_queries",
    "precision_at_1",
    "precision_at_3",
    "precision_at_5",
    "hit_at_5",
    "avg_coverage_ratio",
    "avg_latency_ms",
    "decision",
    "next_action",
]


@dataclass(frozen=True)
class EmbeddingCandidate:
    candidate: str
    provider: str
    model_name: str
    dimension: int
    api_key: str
    base_url: str


def main() -> None:
    args = parse_args()
    queries = load_queries(Path(args.queries))
    if args.execute_real:
        rows = run_real_evaluation(args, queries)
    else:
        rows = run_dry_fixture(queries, top_k=args.top_k)
    summaries = summarize(rows)
    write_csv(Path(args.out_results), RESULT_FIELDS, rows)
    write_csv(Path(args.out_summary), SUMMARY_FIELDS, summaries)
    for summary in summaries:
        print(
            f"{summary['candidate']}: status={summary['status']} "
            f"p@5={summary['precision_at_5']} coverage={summary['avg_coverage_ratio']} "
            f"latency={summary['avg_latency_ms']}ms decision={summary['decision']}"
        )
    print(f"wrote {args.out_results}")
    print(f"wrote {args.out_summary}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare stage 33 GLM-Embedding-3 2048-dim retrieval quality against "
            "the old Jina 1024-dim baseline. Defaults to dry-run fixture mode."
        )
    )
    parser.add_argument("--queries", default=str(QUERY_PATH))
    parser.add_argument("--out-results", default=str(RESULTS_PATH))
    parser.add_argument("--out-summary", default=str(SUMMARY_PATH))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--execute-real", action="store_true")
    parser.add_argument("--jina-api-key", default=env_value("JINA_API_KEY"))
    parser.add_argument("--jina-base-url", default=env_value("JINA_BASE_URL"))
    parser.add_argument("--glm-api-key", default=env_value("PARATERA_API_KEY"))
    parser.add_argument("--glm-base-url", default=env_value("PARATERA_EMBEDDING_BASE_URL"))
    return parser.parse_args()


def env_value(name: str, *, env_file: Path = ROOT / ".env") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    return read_dotenv_value(env_file, name)


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
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value.startswith(("'", '"'))
        ):
            return value[1:-1].strip()
        return value
    return ""


def run_dry_fixture(queries: list[Stage29Query], *, top_k: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for query in queries:
        for candidate in [
            ("jina_baseline", "jina", "jina-embeddings-v3", 1024),
            ("glm_candidate", "paratera", "GLM-Embedding-3", 2048),
        ]:
            rows.append(
                {
                    "query_id": query.query_id,
                    "category": query.category,
                    "expected_refused": str(query.expected_refused).lower(),
                    "candidate": candidate[0],
                    "provider": candidate[1],
                    "model_name": candidate[2],
                    "dimension": str(candidate[3]),
                    "top_k": str(top_k),
                    "precision_at_1": "false" if query.expected_refused else "true",
                    "precision_at_3": "false" if query.expected_refused else "true",
                    "precision_at_5": "false" if query.expected_refused else "true",
                    "hit_at_5": "false" if query.expected_refused else "true",
                    "coverage_ratio": "0.000" if query.expected_refused else "1.000",
                    "source_type_distribution": "",
                    "top1_source_type": "",
                    "top1_document_title": "",
                    "latency_ms": "0.00",
                    "status": "dry_run",
                    "error": "",
                }
            )
    return rows


def run_real_evaluation(args: argparse.Namespace, queries: list[Stage29Query]) -> list[dict[str, str]]:
    if args.top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    force_deterministic_reranking()
    settings = get_settings()
    candidates = [
        EmbeddingCandidate(
            candidate="jina_baseline",
            provider="jina",
            model_name="jina-embeddings-v3",
            dimension=1024,
            api_key=candidate_setting(
                explicit=args.jina_api_key,
                settings_value=settings.embedding_api_key,
                settings_provider=settings.embedding_provider,
                expected_provider="jina",
            ),
            base_url=candidate_setting(
                explicit=args.jina_base_url,
                settings_value=settings.embedding_base_url,
                settings_provider=settings.embedding_provider,
                expected_provider="jina",
            ),
        ),
        EmbeddingCandidate(
            candidate="glm_candidate",
            provider="paratera",
            model_name="GLM-Embedding-3",
            dimension=2048,
            api_key=candidate_setting(
                explicit=args.glm_api_key,
                settings_value=settings.embedding_api_key,
                settings_provider=settings.embedding_provider,
                expected_provider="paratera",
            ),
            base_url=candidate_setting(
                explicit=args.glm_base_url,
                settings_value=settings.embedding_base_url,
                settings_provider=settings.embedding_provider,
                expected_provider="paratera",
            ),
        ),
    ]
    init_db()
    rows: list[dict[str, str]] = []
    with SessionLocal() as db:
        for candidate in candidates:
            if not candidate.api_key.strip() or not candidate.base_url.strip():
                rows.extend(skipped_rows(queries, candidate, top_k=args.top_k, reason="missing provider configuration"))
                continue
            try:
                provider = create_embedding_provider(
                    provider_name=candidate.provider,
                    model_name=candidate.model_name,
                    api_key=candidate.api_key,
                    base_url=candidate.base_url,
                    dimension=candidate.dimension,
                    timeout_seconds=settings.embedding_timeout_seconds,
                )
                service = HybridSearchService(db=db, embedding_provider=provider, reranking_enabled=True)
                rows.extend(evaluate_candidate(queries, candidate, service, top_k=args.top_k))
            except Exception as exc:
                rows.extend(skipped_rows(queries, candidate, top_k=args.top_k, reason=sanitize_error(exc)))
    return rows


def candidate_setting(
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


def evaluate_candidate(
    queries: list[Stage29Query],
    candidate: EmbeddingCandidate,
    service: HybridSearchService,
    *,
    top_k: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for query in queries:
        started = time.perf_counter()
        try:
            results = [] if query.expected_refused else service.search(query.question, top_k=top_k)
            coverage = coverage_ratio(results, query)
            top1 = results[0] if results else None
            latency_ms = (time.perf_counter() - started) * 1000.0
            rows.append(
                {
                    "query_id": query.query_id,
                    "category": query.category,
                    "expected_refused": str(query.expected_refused).lower(),
                    "candidate": candidate.candidate,
                    "provider": candidate.provider,
                    "model_name": candidate.model_name,
                    "dimension": str(candidate.dimension),
                    "top_k": str(top_k),
                    "precision_at_1": str(hit_at_k(results, query, 1)).lower(),
                    "precision_at_3": str(hit_at_k(results, query, min(3, top_k))).lower(),
                    "precision_at_5": str(hit_at_k(results, query, min(5, top_k))).lower(),
                    "hit_at_5": str(hit_at_k(results, query, min(5, top_k))).lower(),
                    "coverage_ratio": f"{coverage.ratio:.3f}",
                    "source_type_distribution": source_type_distribution(results),
                    "top1_source_type": top1.source_type if top1 else "",
                    "top1_document_title": top1.document_title[:160] if top1 else "",
                    "latency_ms": f"{latency_ms:.2f}",
                    "status": "completed",
                    "error": "",
                }
            )
        except Exception as exc:
            rows.append(error_row(query, candidate, top_k=top_k, latency_ms=(time.perf_counter() - started) * 1000.0, error=sanitize_error(exc)))
    return rows


def skipped_rows(
    queries: list[Stage29Query],
    candidate: EmbeddingCandidate,
    *,
    top_k: int,
    reason: str,
) -> list[dict[str, str]]:
    return [
        error_row(query, candidate, top_k=top_k, latency_ms=0.0, status="skipped", error=reason)
        for query in queries
    ]


def error_row(
    query: Stage29Query,
    candidate: EmbeddingCandidate,
    *,
    top_k: int,
    latency_ms: float,
    error: str,
    status: str = "error",
) -> dict[str, str]:
    return {
        "query_id": query.query_id,
        "category": query.category,
        "expected_refused": str(query.expected_refused).lower(),
        "candidate": candidate.candidate,
        "provider": candidate.provider,
        "model_name": candidate.model_name,
        "dimension": str(candidate.dimension),
        "top_k": str(top_k),
        "precision_at_1": "false",
        "precision_at_3": "false",
        "precision_at_5": "false",
        "hit_at_5": "false",
        "coverage_ratio": "0.000",
        "source_type_distribution": "",
        "top1_source_type": "",
        "top1_document_title": "",
        "latency_ms": f"{latency_ms:.2f}",
        "status": status,
        "error": error,
    }


def summarize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for candidate in sorted({row["candidate"] for row in rows}):
        candidate_rows = [row for row in rows if row["candidate"] == candidate]
        completed = [row for row in candidate_rows if row["status"] in {"completed", "dry_run"}]
        first = candidate_rows[0]
        non_refusal = [row for row in completed if row["expected_refused"] == "false"]
        status = "completed" if all(row["status"] == "completed" for row in candidate_rows) else candidate_rows[0]["status"]
        summaries.append(
            {
                "candidate": candidate,
                "provider": first["provider"],
                "model_name": first["model_name"],
                "dimension": first["dimension"],
                "status": status,
                "total_queries": str(len(candidate_rows)),
                "completed_queries": str(len(completed)),
                "precision_at_1": f"{ratio(count_true(non_refusal, 'precision_at_1'), len(non_refusal)):.3f}",
                "precision_at_3": f"{ratio(count_true(non_refusal, 'precision_at_3'), len(non_refusal)):.3f}",
                "precision_at_5": f"{ratio(count_true(non_refusal, 'precision_at_5'), len(non_refusal)):.3f}",
                "hit_at_5": f"{ratio(count_true(non_refusal, 'hit_at_5'), len(non_refusal)):.3f}",
                "avg_coverage_ratio": f"{average([float(row['coverage_ratio']) for row in non_refusal]):.3f}",
                "avg_latency_ms": f"{average([float(row['latency_ms']) for row in completed]):.2f}",
                "decision": decision_for(candidate_rows),
                "next_action": next_action_for(candidate_rows),
            }
        )
    apply_comparative_decisions(summaries)
    return summaries


def apply_comparative_decisions(summaries: list[dict[str, str]]) -> None:
    by_candidate = {summary["candidate"]: summary for summary in summaries}
    jina = by_candidate.get("jina_baseline")
    glm = by_candidate.get("glm_candidate")
    if not jina or not glm:
        return
    if jina["status"] != "completed" or glm["status"] != "completed":
        return

    jina_p5 = float(jina["precision_at_5"])
    glm_p5 = float(glm["precision_at_5"])
    jina_p3 = float(jina["precision_at_3"])
    glm_p3 = float(glm["precision_at_3"])
    jina_coverage = float(jina["avg_coverage_ratio"])
    glm_coverage = float(glm["avg_coverage_ratio"])
    jina_latency = float(jina["avg_latency_ms"])
    glm_latency = float(glm["avg_latency_ms"])
    latency_delta_ratio = ratio_float(glm_latency - jina_latency, jina_latency)

    jina_edge_is_small = (jina_p5 - glm_p5) <= 0.10 and (jina_coverage - glm_coverage) <= 0.05

    if jina_edge_is_small:
        decision = "keep_glm"
        next_action = (
            "Keep GLM-Embedding-3 as the default provider; Jina's small top-5/coverage edge "
            "does not offset quota sustainability risk, so keep Jina only as historical baseline "
            "and rollback reference."
        )
    elif glm_p5 >= jina_p5 and glm_coverage >= jina_coverage - 0.02 and latency_delta_ratio <= 0.20:
        decision = "keep_glm"
        next_action = "Keep GLM candidate under review; no rollback signal from same-environment retrieval."
    elif jina_p5 >= glm_p5 + 0.05 and jina_coverage >= glm_coverage + 0.02 and jina_p3 >= glm_p3:
        decision = "rollback_jina"
        next_action = "Jina wins consistently; review rollback before changing defaults."
    elif jina_p5 > glm_p5 and glm_p3 > jina_p3:
        decision = "route_by_query_type"
        next_action = "Mixed ranking signal: compare per-query categories before choosing a single default."
    elif jina_p5 > glm_p5 or jina_coverage > glm_coverage:
        decision = "review_required"
        next_action = "Jina retains an edge in top-5 or coverage; do not switch defaults without manual review."
    else:
        decision = "review_required"
        next_action = "Metrics are close; keep both indexes and review per-query differences."

    for summary in summaries:
        summary["decision"] = decision
        summary["next_action"] = next_action


def ratio_float(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


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


def decision_for(rows: list[dict[str, str]]) -> str:
    statuses = {row["status"] for row in rows}
    if statuses == {"dry_run"}:
        return "dry_run_only"
    if "error" in statuses:
        return "review_errors"
    if "skipped" in statuses:
        return "skipped_missing_real_config"
    return "review_for_silent_regression"


def next_action_for(rows: list[dict[str, str]]) -> str:
    decision = decision_for(rows)
    if decision == "dry_run_only":
        return "Run with --execute-real and local provider configuration for real migration evidence."
    if decision == "skipped_missing_real_config":
        return "Provide local Jina and GLM provider configuration, then rerun --execute-real."
    if decision == "review_errors":
        return "Inspect per-query errors; do not claim migration pass."
    return "Compare GLM candidate against Jina baseline before changing defaults."


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

"""阶段 20：中文难评测集答案级 coverage_ratio 判定升级。

本脚本复用阶段 19 中文难评测集和 source_type_reweight 候选配置，
但不再把 ``expected_source_hit`` 作为主 hit 判定，而是用
``expected_answer_points`` 计算 top-1 证据的答案要点覆盖率。

默认 deterministic，不依赖真实 API；真实 Jina query 端校验会在阶段 20
后续 Phase 作为显式可选模式扩展，且不会重做 chunk embedding。
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.brain.config import RetrievalConfig  # noqa: E402
from app.services.brain.service import BrainService  # noqa: E402
from app.services.generation.chat_model import create_chat_model_provider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService  # noqa: E402
from app.services.retrieval.keyword_search import expand_query_terms, normalize_text  # noqa: E402
from app.services.retrieval.source_type_reweight import (  # noqa: E402
    BASELINE_WEIGHTS,
    DEEP_FULLTEXT_TYPES,
    FULLTEXT_BOOST_WEIGHTS,
    METADATA_DEMOTE_WEIGHTS,
    Stage19TuningWeights,
    TOPIC_ANCHOR_STRICT_WEIGHTS,
    reweight_results,
)
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402


QUERY_PATH = ROOT / "data" / "evaluation" / "stage19_chinese_hard_queries.csv"
RESULTS_PATH = ROOT / "data" / "evaluation" / "stage20_eval_upgrade_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage20_eval_upgrade_summary.csv"

COVERAGE_THRESHOLD = 0.60
JUDGE_MODE = "coverage_ratio"
REAL_JINA_JUDGE_MODE = "coverage_ratio_real_jina"

CONFIGS: tuple[Stage19TuningWeights, ...] = (
    BASELINE_WEIGHTS,
    FULLTEXT_BOOST_WEIGHTS,
    METADATA_DEMOTE_WEIGHTS,
    TOPIC_ANCHOR_STRICT_WEIGHTS,
)

RESULT_FIELDS = [
    "query_id",
    "config",
    "judge_mode",
    "query",
    "difficulty_type",
    "expected_refused",
    "hit",
    "coverage_ratio",
    "coverage_threshold",
    "covered_points",
    "missing_points",
    "deep_fulltext_top1",
    "refusal_matched",
    "refused",
    "decision",
    "next_action",
    "top1_source_type",
    "top1_document_title",
    "top_source_types",
    "real_config_status",
    "error",
]

SUMMARY_FIELDS = [
    "config",
    "judge_mode",
    "real_config_status",
    "non_refusal_total",
    "hits",
    "precision_at_1",
    "avg_coverage_ratio",
    "deep_fulltext_top1_rate",
    "refusal_total",
    "refusal_accuracy",
    "decision",
    "next_action",
]


@dataclass(frozen=True)
class ChineseHardQuery:
    query_id: str
    query: str
    difficulty_type: str
    language_type: str
    expected_source_hit: tuple[str, ...]
    expected_source_type: str
    expected_refused: bool
    expected_answer_points: tuple[str, ...]
    distractor_topics: str
    notes: str


@dataclass(frozen=True)
class CoverageResult:
    ratio: float
    covered_points: tuple[str, ...]
    missing_points: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", default=str(QUERY_PATH))
    parser.add_argument("--out-results", default=str(RESULTS_PATH))
    parser.add_argument("--out-summary", default=str(SUMMARY_PATH))
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--fetch-k", type=int, default=24)
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=COVERAGE_THRESHOLD,
        help="coverage_ratio >= threshold counts as hit; default 0.60.",
    )
    parser.add_argument(
        "--provider",
        default="",
        help="Embedding provider override. Default uses .env or deterministic.",
    )
    parser.add_argument(
        "--real-query",
        action="store_true",
        help=(
            "Use .env real embedding provider for query embedding only. "
            "Does not rebuild chunk embeddings."
        ),
    )
    return parser.parse_args()


def load_queries(path: Path) -> list[ChineseHardQuery]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [
            ChineseHardQuery(
                query_id=row["query_id"],
                query=row["query"],
                difficulty_type=row["difficulty_type"],
                language_type=row["language_type"],
                expected_source_hit=split_semicolon(row.get("expected_source_hit", "")),
                expected_source_type=row["expected_source_type"],
                expected_refused=row["expected_refused"].strip().lower() == "true",
                expected_answer_points=split_semicolon(row.get("expected_answer_points", "")),
                distractor_topics=row.get("distractor_topics", ""),
                notes=row.get("notes", ""),
            )
            for row in reader
        ]


def split_semicolon(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or "").split(";") if part.strip())


def normalized_for_match(text: str | None) -> str:
    normalized = normalize_text(text)
    return re.sub(r"\s+", "", normalized)


def chinese_fragments(text: str) -> tuple[str, ...]:
    """Return stable Chinese bigram/trigram fragments for lenient point matching."""
    chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    fragments: list[str] = []
    for size in (3, 2):
        for index in range(0, max(0, len(chars) - size + 1)):
            fragment = "".join(chars[index : index + size])
            if fragment not in fragments:
                fragments.append(fragment)
    return tuple(fragments)


def point_match_terms(point: str) -> tuple[str, ...]:
    normalized = normalized_for_match(point)
    terms: list[str] = []
    if normalized:
        terms.append(normalized)

    for expanded in expand_query_terms(point):
        term = normalized_for_match(expanded.text)
        if len(term) >= 2 and term not in terms:
            terms.append(term)

    for fragment in chinese_fragments(point):
        if fragment not in terms:
            terms.append(fragment)
    return tuple(terms)


def point_is_covered(point: str, evidence_text: str) -> bool:
    terms = point_match_terms(point)
    if not terms:
        return False
    # Exact or synonym match is enough.
    direct_terms = terms[: max(1, len(terms) - len(chinese_fragments(point)))]
    if any(term in evidence_text for term in direct_terms):
        return True

    # For a Chinese multi-character point, require at least two fragments.
    fragments = chinese_fragments(point)
    if not fragments:
        return False
    matched_fragments = sum(1 for fragment in fragments if fragment in evidence_text)
    return matched_fragments >= min(2, len(fragments))


def coverage_ratio_for_points(
    expected_points: tuple[str, ...],
    evidence_text: str,
) -> CoverageResult:
    if not expected_points:
        return CoverageResult(ratio=0.0, covered_points=(), missing_points=())
    normalized_evidence = normalized_for_match(evidence_text)
    covered: list[str] = []
    missing: list[str] = []
    for point in expected_points:
        if point_is_covered(point, normalized_evidence):
            covered.append(point)
        else:
            missing.append(point)
    ratio = len(covered) / len(expected_points)
    return CoverageResult(
        ratio=round(ratio, 3),
        covered_points=tuple(covered),
        missing_points=tuple(missing),
    )


def evidence_text_for_top1(result: HybridSearchResult | None) -> str:
    if result is None:
        return ""
    # Intentionally exclude document_title to reduce title/metadata-card bias.
    return " ".join([result.heading_path or "", result.content])


def evaluate_non_refusal(
    baseline_results: list[HybridSearchResult],
    query: ChineseHardQuery,
    weights: Stage19TuningWeights,
    top_k: int,
    threshold: float,
    judge_mode: str,
    real_config_status: str,
) -> dict[str, str]:
    reweighted = reweight_results(baseline_results, weights, query=query.query)
    top = reweighted[:top_k]
    top1 = top[0] if top else None
    coverage = coverage_ratio_for_points(
        query.expected_answer_points,
        evidence_text_for_top1(top1),
    )
    hit = coverage.ratio >= threshold
    deep_fulltext_top1 = bool(top1 and top1.source_type in DEEP_FULLTEXT_TYPES)
    return {
        "query_id": query.query_id,
        "config": weights.name,
        "judge_mode": judge_mode,
        "query": query.query,
        "difficulty_type": query.difficulty_type,
        "expected_refused": str(query.expected_refused).lower(),
        "hit": str(hit).lower(),
        "coverage_ratio": f"{coverage.ratio:.3f}",
        "coverage_threshold": f"{threshold:.2f}",
        "covered_points": ";".join(coverage.covered_points),
        "missing_points": ";".join(coverage.missing_points),
        "deep_fulltext_top1": str(deep_fulltext_top1).lower(),
        "refusal_matched": "",
        "refused": "",
        "decision": "",
        "next_action": "",
        "top1_source_type": top1.source_type if top1 else "",
        "top1_document_title": top1.document_title[:120] if top1 else "",
        "top_source_types": ";".join(result.source_type for result in top),
        "real_config_status": real_config_status,
        "error": "",
    }


def evaluate_refusal(
    brain: BrainService,
    query: ChineseHardQuery,
    weights: Stage19TuningWeights,
    top_k: int,
    threshold: float,
    judge_mode: str,
    real_config_status: str,
    api_key: str = "",
) -> dict[str, str]:
    try:
        answer = brain.answer(
            question=query.query,
            config=RetrievalConfig(retrieval_mode="hybrid", top_k=top_k),
        )
        refused = bool(answer.refused)
        refusal_matched = refused == query.expected_refused
        return {
            "query_id": query.query_id,
            "config": weights.name,
            "judge_mode": judge_mode,
            "query": query.query,
            "difficulty_type": query.difficulty_type,
            "expected_refused": str(query.expected_refused).lower(),
            "hit": str(refusal_matched).lower(),
            "coverage_ratio": "",
            "coverage_threshold": f"{threshold:.2f}",
            "covered_points": "",
            "missing_points": "",
            "deep_fulltext_top1": "",
            "refusal_matched": str(refusal_matched).lower(),
            "refused": str(refused).lower(),
            "decision": "",
            "next_action": "",
            "top1_source_type": "",
            "top1_document_title": "",
            "top_source_types": "",
            "real_config_status": real_config_status,
            "error": "",
        }
    except Exception as exc:
        return {
            "query_id": query.query_id,
            "config": weights.name,
            "judge_mode": judge_mode,
            "query": query.query,
            "difficulty_type": query.difficulty_type,
            "expected_refused": str(query.expected_refused).lower(),
            "hit": "false",
            "coverage_ratio": "",
            "coverage_threshold": f"{threshold:.2f}",
            "covered_points": "",
            "missing_points": "",
            "deep_fulltext_top1": "",
            "refusal_matched": "",
            "refused": "",
            "decision": "",
            "next_action": "",
            "top1_source_type": "",
            "top1_document_title": "",
            "top_source_types": "",
            "real_config_status": "error" if real_config_status == "completed" else real_config_status,
            "error": sanitize_error(exc, api_key),
        }


def summarize(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    by_config: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_config.setdefault(row["config"], []).append(row)

    summary_rows: list[dict[str, str]] = []
    lookup: dict[str, dict[str, str]] = {}
    for config, config_rows in by_config.items():
        non_refusal = [row for row in config_rows if row["difficulty_type"] != "refusal"]
        refusal = [row for row in config_rows if row["difficulty_type"] == "refusal"]
        hits = sum(1 for row in non_refusal if row["hit"] == "true")
        coverage_values = [
            float(row["coverage_ratio"])
            for row in non_refusal
            if row["coverage_ratio"]
        ]
        deep_top1 = sum(1 for row in non_refusal if row["deep_fulltext_top1"] == "true")
        refusal_matched = sum(1 for row in refusal if row["refusal_matched"] == "true")
        non_refusal_total = len(non_refusal)
        refusal_total = len(refusal)
        summary = {
            "config": config,
            "judge_mode": config_rows[0].get("judge_mode", JUDGE_MODE),
            "real_config_status": summarize_real_status(config_rows),
            "non_refusal_total": str(non_refusal_total),
            "hits": str(hits),
            "precision_at_1": format_ratio(hits, non_refusal_total),
            "avg_coverage_ratio": f"{average(coverage_values):.3f}",
            "deep_fulltext_top1_rate": format_ratio(deep_top1, non_refusal_total),
            "refusal_total": str(refusal_total),
            "refusal_accuracy": format_ratio(refusal_matched, refusal_total),
            "decision": "",
            "next_action": "",
        }
        summary_rows.append(summary)
        lookup[config] = summary
    return summary_rows, lookup


def summarize_real_status(rows: list[dict[str, str]]) -> str:
    statuses = {row.get("real_config_status", "") for row in rows if row.get("real_config_status", "")}
    if not statuses:
        return ""
    if "error" in statuses:
        return "error"
    if "skipped" in statuses:
        return "skipped"
    if statuses == {"completed"}:
        return "completed"
    return ";".join(sorted(statuses))


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def format_ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000"
    return f"{(numerator / denominator):.3f}"


def apply_decisions(
    summary_lookup: dict[str, dict[str, str]],
    rows: list[dict[str, str]],
) -> str:
    baseline = summary_lookup.get(BASELINE_WEIGHTS.name)
    if not baseline:
        return "no_baseline"
    base_p1 = float(baseline["precision_at_1"])
    base_deep = float(baseline["deep_fulltext_top1_rate"])
    base_refusal = float(baseline["refusal_accuracy"])

    promoted: list[str] = []
    for config, summary in summary_lookup.items():
        if config == BASELINE_WEIGHTS.name:
            summary["decision"] = "baseline"
            summary["next_action"] = "作为 coverage_ratio 判定下的默认 hybrid 对照"
            continue
        delta_p1 = float(summary["precision_at_1"]) - base_p1
        delta_deep = float(summary["deep_fulltext_top1_rate"]) - base_deep
        refusal_ok = float(summary["refusal_accuracy"]) >= base_refusal
        epsilon = 1e-9
        if delta_p1 + epsilon >= 0.10 and delta_deep + epsilon >= 0.20 and refusal_ok:
            summary["decision"] = "promote_candidate"
            summary["next_action"] = (
                f"满足切换门槛: Δp@1={delta_p1:+.3f}; "
                f"Δdeep_top1={delta_deep:+.3f}; refusal 不退化"
            )
            promoted.append(config)
        else:
            reasons: list[str] = []
            if delta_p1 < 0.10:
                reasons.append(f"delta_precision_at_1={delta_p1:+.3f}<0.10")
            if delta_deep < 0.20:
                reasons.append(f"delta_deep_fulltext_top1_rate={delta_deep:+.3f}<0.20")
            if not refusal_ok:
                reasons.append("refusal_accuracy_regressed")
            summary["decision"] = "keep_existing_hybrid"
            summary["next_action"] = "; ".join(reasons)

    for row in rows:
        summary = summary_lookup.get(row["config"])
        if summary:
            row["decision"] = summary["decision"]
            row["next_action"] = summary["next_action"][:160]

    if promoted:
        return f"switch_default_to:{','.join(promoted)}"
    return "keep_existing_hybrid"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def real_embedding_missing_settings(settings: Settings) -> tuple[str, ...]:
    missing: list[str] = []
    if not settings.embedding_provider:
        missing.append("EMBEDDING_PROVIDER")
    if not settings.embedding_model_name:
        missing.append("EMBEDDING_MODEL_NAME")
    if not settings.embedding_api_key:
        missing.append("EMBEDDING_API_KEY")
    if not settings.embedding_base_url:
        missing.append("EMBEDDING_BASE_URL")
    if not settings.embedding_dimension:
        missing.append("EMBEDDING_DIMENSION")
    return tuple(missing)


def sanitize_error(exc: Exception, api_key: str = "") -> str:
    message = f"{type(exc).__name__}: {str(exc)}"
    if api_key:
        message = message.replace(api_key, "<redacted>")
    message = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer <redacted>", message)
    return message[:200]


def skipped_rows(
    queries: list[ChineseHardQuery],
    missing_settings: tuple[str, ...],
    threshold: float,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    reason = "missing real embedding settings: " + ",".join(missing_settings)
    for query in queries:
        for weights in CONFIGS:
            rows.append(
                {
                    "query_id": query.query_id,
                    "config": weights.name,
                    "judge_mode": REAL_JINA_JUDGE_MODE,
                    "query": query.query,
                    "difficulty_type": query.difficulty_type,
                    "expected_refused": str(query.expected_refused).lower(),
                    "hit": "false",
                    "coverage_ratio": "",
                    "coverage_threshold": f"{threshold:.2f}",
                    "covered_points": "",
                    "missing_points": "",
                    "deep_fulltext_top1": "",
                    "refusal_matched": "",
                    "refused": "",
                    "decision": "real_jina_skipped",
                    "next_action": "真实 Jina query 校验跳过；补齐本地 .env 后可重跑，不影响 deterministic baseline",
                    "top1_source_type": "",
                    "top1_document_title": "",
                    "top_source_types": "",
                    "real_config_status": "skipped",
                    "error": reason,
                }
            )
    return rows


def error_row(
    query: ChineseHardQuery,
    weights: Stage19TuningWeights,
    threshold: float,
    judge_mode: str,
    exc: Exception,
    api_key: str = "",
) -> dict[str, str]:
    return {
        "query_id": query.query_id,
        "config": weights.name,
        "judge_mode": judge_mode,
        "query": query.query,
        "difficulty_type": query.difficulty_type,
        "expected_refused": str(query.expected_refused).lower(),
        "hit": "false",
        "coverage_ratio": "",
        "coverage_threshold": f"{threshold:.2f}",
        "covered_points": "",
        "missing_points": "",
        "deep_fulltext_top1": "",
        "refusal_matched": "",
        "refused": "",
        "decision": "",
        "next_action": "",
        "top1_source_type": "",
        "top1_document_title": "",
        "top_source_types": "",
        "real_config_status": "error" if judge_mode == REAL_JINA_JUDGE_MODE else "",
        "error": sanitize_error(exc, api_key),
    }


def main() -> None:
    args = parse_args()
    if args.top_k <= 0 or args.fetch_k <= 0:
        raise ValueError("top_k and fetch_k must be positive")
    if args.fetch_k < args.top_k:
        raise ValueError("fetch_k must be >= top_k")
    if args.coverage_threshold <= 0 or args.coverage_threshold > 1:
        raise ValueError("coverage_threshold must be in (0, 1]")

    settings = get_settings()
    if args.real_query:
        if args.out_results == str(RESULTS_PATH):
            args.out_results = str(ROOT / "data" / "evaluation" / "stage20_eval_upgrade_real_jina_results.csv")
        if args.out_summary == str(SUMMARY_PATH):
            args.out_summary = str(ROOT / "data" / "evaluation" / "stage20_eval_upgrade_real_jina_summary.csv")

    queries = load_queries(Path(args.queries))
    judge_mode = REAL_JINA_JUDGE_MODE if args.real_query else JUDGE_MODE
    real_status = "completed" if args.real_query else ""
    missing_settings = real_embedding_missing_settings(settings) if args.real_query else ()
    if missing_settings:
        rows = skipped_rows(queries, missing_settings, args.coverage_threshold)
        summary_rows, summary_lookup = summarize(rows)
        for summary in summary_rows:
            summary["decision"] = "real_jina_skipped"
            summary["next_action"] = "真实 Jina query 校验跳过；补齐本地 .env 后重跑"
        write_csv(Path(args.out_results), RESULT_FIELDS, rows)
        write_csv(Path(args.out_summary), SUMMARY_FIELDS, summary_rows)
        print(
            "stage20 eval upgrade "
            f"({REAL_JINA_JUDGE_MODE}) -> overall=real_jina_skipped "
            f"missing={','.join(missing_settings)}"
        )
        return

    provider_name = settings.embedding_provider if args.real_query else args.provider
    embedding_provider = create_embedding_provider_from_settings(provider_name, settings)
    chat_provider = create_chat_model_provider(provider_name="deterministic")

    init_db()
    rows: list[dict[str, str]] = []
    with SessionLocal() as db:
        hybrid = HybridSearchService(db=db, embedding_provider=embedding_provider)
        brain = BrainService(
            db=db,
            chat_model_provider=chat_provider,
            embedding_provider=embedding_provider,
            log_answers=False,
        )
        for query in queries:
            if query.expected_refused:
                for weights in CONFIGS:
                    rows.append(
                        evaluate_refusal(
                            brain,
                            query,
                            weights,
                            args.top_k,
                            args.coverage_threshold,
                            judge_mode,
                            real_status,
                            settings.embedding_api_key,
                        )
                    )
                continue

            try:
                baseline_results = hybrid.search(query=query.query, top_k=args.fetch_k)
            except Exception as exc:
                for weights in CONFIGS:
                    rows.append(error_row(query, weights, args.coverage_threshold, judge_mode, exc, settings.embedding_api_key))
                continue
            for weights in CONFIGS:
                rows.append(
                    evaluate_non_refusal(
                        baseline_results=baseline_results,
                        query=query,
                        weights=weights,
                        top_k=args.top_k,
                        threshold=args.coverage_threshold,
                        judge_mode=judge_mode,
                        real_config_status=real_status,
                    )
                )

    summary_rows, summary_lookup = summarize(rows)
    overall = apply_decisions(summary_lookup, rows)
    write_csv(Path(args.out_results), RESULT_FIELDS, rows)
    write_csv(Path(args.out_summary), SUMMARY_FIELDS, summary_rows)

    print(f"stage20 eval upgrade ({judge_mode}) -> overall={overall}")
    for row in summary_rows:
        print(
            f"  {row['config']:<28} "
            f"p@1={row['precision_at_1']} "
            f"coverage={row['avg_coverage_ratio']} "
            f"deep_top1={row['deep_fulltext_top1_rate']} "
            f"refusal_acc={row['refusal_accuracy']} "
            f"decision={row['decision']}"
        )


if __name__ == "__main__":
    main()

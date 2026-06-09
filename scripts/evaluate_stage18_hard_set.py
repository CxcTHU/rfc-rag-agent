"""阶段 18：难评测集多配置检索对比。

在难评测集（跨段证据 / 易混淆术语 / 需拒答边界）上对比 5 种检索配置：

    keyword           -> KeywordSearchService
    vector            -> VectorSearchService
    hybrid            -> HybridSearchService（当前默认链路）
    bm25_rrf          -> RRFHybridSearchService（阶段 17 候选）
    bm25_rrf_context  -> RRFHybridSearchService + 邻近 chunk 上下文扩展

输出：
    data/evaluation/stage18_hard_results.csv      每个 (config, query) 一行
    data/evaluation/stage18_config_comparison.csv 每个 config 汇总

需拒答查询用默认 Brain（CitationAnswerService + evidence confidence）判断是否拒答，
验证检索升级不会绕过拒答边界。

默认 deterministic provider，可复跑；不静默 fallback 掩盖配置差异。
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.generation.answer_service import CitationAnswerService  # noqa: E402
from app.services.generation.chat_model import create_chat_model_provider  # noqa: E402
from app.services.retrieval.bm25_search import BM25SearchService  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchService  # noqa: E402
from app.services.retrieval.keyword_search import KeywordSearchService  # noqa: E402
from app.services.retrieval.rrf_fusion import RRFHybridSearchService  # noqa: E402
from app.services.retrieval.vector_search import VectorSearchService  # noqa: E402
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402


CONFIGS = ["keyword", "vector", "hybrid", "bm25_rrf", "bm25_rrf_context"]

QUERY_FIELDS = [
    "query_id",
    "query",
    "difficulty_type",
    "language_type",
    "top_k",
    "expected_title_terms",
    "expected_content_terms",
    "expected_source_types",
    "expected_refused",
    "expected_answer_points",
    "distractor_topics",
    "notes",
]

RESULT_FIELDS = [
    "config",
    "query_id",
    "difficulty_type",
    "language_type",
    "expected_refused",
    "hit",
    "rank",
    "refused",
    "refusal_matched",
    "best_score",
    "hit_title",
    "top_titles",
    "notes",
]

COMPARISON_FIELDS = [
    "config",
    "answerable_total",
    "hits",
    "hit_rate",
    "rank1_hits",
    "precision_at_1",
    "mean_hit_rank",
    "distinct_wins",
    "notes",
]


@dataclass(frozen=True)
class HardQuery:
    query_id: str
    query: str
    difficulty_type: str
    language_type: str
    top_k: int
    expected_title_terms: list[str]
    expected_content_terms: list[str]
    expected_source_types: list[str]
    expected_refused: bool
    notes: str


@dataclass
class ConfigResult:
    config: str
    query_id: str
    difficulty_type: str
    language_type: str
    expected_refused: bool
    hit: bool | None
    rank: int | None
    refused: bool | None
    refusal_matched: bool | None
    best_score: float
    hit_title: str
    top_titles: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "config": self.config,
            "query_id": self.query_id,
            "difficulty_type": self.difficulty_type,
            "language_type": self.language_type,
            "expected_refused": _bool(self.expected_refused),
            "hit": _opt_bool(self.hit),
            "rank": str(self.rank or ""),
            "refused": _opt_bool(self.refused),
            "refusal_matched": _opt_bool(self.refusal_matched),
            "best_score": f"{self.best_score:.4f}",
            "hit_title": self.hit_title,
            "top_titles": self.top_titles,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 18 hard-set multi-config retrieval comparison.")
    parser.add_argument("--queries", default="data/evaluation/stage18_hard_queries.csv")
    parser.add_argument("--out", default="data/evaluation/stage18_hard_results.csv")
    parser.add_argument("--comparison-out", default="data/evaluation/stage18_config_comparison.csv")
    parser.add_argument("--context-window", type=int, default=1, help="Adjacent chunks for bm25_rrf_context config.")
    parser.add_argument("--embedding-provider", default="deterministic")
    args = parser.parse_args()

    settings = get_settings()
    provider = create_embedding_provider_from_settings(args.embedding_provider, settings)
    queries = read_hard_queries(Path(args.queries))

    init_db()
    with SessionLocal() as db:
        results = evaluate_all(db, provider, queries, context_window=args.context_window)
        refusal_rows = evaluate_refusals(db, provider, queries)

    all_rows = results + refusal_rows
    write_results(Path(args.out), all_rows)
    comparison = build_comparison(results, queries)
    write_comparison(Path(args.comparison_out), comparison)
    print_summary(all_rows, comparison, queries, args.out, args.comparison_out)


def read_hard_queries(path: Path) -> list[HardQuery]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(QUERY_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing query fields: {', '.join(sorted(missing))}")
        return [
            HardQuery(
                query_id=row["query_id"],
                query=row["query"],
                difficulty_type=row["difficulty_type"],
                language_type=row["language_type"],
                top_k=_parse_top_k(row["top_k"]),
                expected_title_terms=_split(row["expected_title_terms"]),
                expected_content_terms=_split(row["expected_content_terms"]),
                expected_source_types=_split(row["expected_source_types"]),
                expected_refused=_parse_bool(row["expected_refused"]),
                notes=row["notes"],
            )
            for row in reader
        ]


def run_config(config: str, db, provider, query: str, top_k: int, context_window: int):
    if config == "keyword":
        return KeywordSearchService(db).search(query, top_k=top_k)
    if config == "vector":
        return VectorSearchService(db, provider).search(query, top_k=top_k)
    if config == "hybrid":
        return HybridSearchService(db, provider).search(query, top_k=top_k)
    if config == "bm25_rrf":
        return RRFHybridSearchService(db, provider).search(query, top_k=top_k)
    if config == "bm25_rrf_context":
        return RRFHybridSearchService(db, provider).search(
            query, top_k=top_k, context_window=context_window
        )
    raise ValueError(f"unknown config: {config}")


def evaluate_all(db, provider, queries: list[HardQuery], context_window: int) -> list[ConfigResult]:
    answerable = [q for q in queries if not q.expected_refused]
    rows: list[ConfigResult] = []
    for config in CONFIGS:
        for q in answerable:
            results = run_config(config, db, provider, q.query, q.top_k, context_window)
            hit_index = find_hit(q, results)
            hit = results[hit_index] if hit_index is not None else None
            rows.append(
                ConfigResult(
                    config=config,
                    query_id=q.query_id,
                    difficulty_type=q.difficulty_type,
                    language_type=q.language_type,
                    expected_refused=False,
                    hit=hit_index is not None,
                    rank=(hit_index + 1) if hit_index is not None else None,
                    refused=None,
                    refusal_matched=None,
                    best_score=float(getattr(results[0], "score", 0.0)) if results else 0.0,
                    hit_title=getattr(hit, "document_title", "") if hit else "",
                    top_titles=" || ".join(getattr(r, "document_title", "") for r in results[:5]),
                    notes=q.notes,
                )
            )
    return rows


def evaluate_refusals(db, provider, queries: list[HardQuery]) -> list[ConfigResult]:
    """用默认 Brain（hybrid + evidence confidence）判断需拒答查询是否被拒答。"""

    refusal_queries = [q for q in queries if q.expected_refused]
    if not refusal_queries:
        return []
    chat_provider = create_chat_model_provider(provider_name="deterministic")
    service = CitationAnswerService(
        db=db,
        chat_model_provider=chat_provider,
        embedding_provider=provider,
        log_answers=False,
    )
    rows: list[ConfigResult] = []
    for q in refusal_queries:
        result = service.answer(question=q.query, top_k=q.top_k, retrieval_mode="hybrid")
        rows.append(
            ConfigResult(
                config="brain_default",
                query_id=q.query_id,
                difficulty_type=q.difficulty_type,
                language_type=q.language_type,
                expected_refused=True,
                hit=None,
                rank=None,
                refused=result.refused,
                refusal_matched=(result.refused is True),
                best_score=0.0,
                hit_title="",
                top_titles=" || ".join(s.document_title for s in result.sources[:5]),
                notes=q.notes,
            )
        )
    return rows


def find_hit(query: HardQuery, results) -> int | None:
    for index, result in enumerate(results):
        source_type = getattr(result, "source_type", "")
        title = getattr(result, "document_title", "")
        content = getattr(result, "content", "")
        if query.expected_source_types and source_type not in query.expected_source_types:
            continue
        if query.expected_title_terms and not contains_any(title, query.expected_title_terms):
            continue
        if query.expected_content_terms and not contains_any(content, query.expected_content_terms):
            continue
        if not (query.expected_title_terms or query.expected_content_terms or query.expected_source_types):
            continue
        return index
    return None


def build_comparison(results: list[ConfigResult], queries: list[HardQuery]) -> list[dict[str, str]]:
    answerable_ids = [q.query_id for q in queries if not q.expected_refused]
    # 哪些 query 只有某一个 config 命中 -> distinct_wins。
    hits_by_query: dict[str, list[str]] = {qid: [] for qid in answerable_ids}
    for row in results:
        if row.hit:
            hits_by_query.setdefault(row.query_id, []).append(row.config)

    comparison: list[dict[str, str]] = []
    for config in CONFIGS:
        config_rows = [r for r in results if r.config == config]
        total = len(config_rows)
        hits = sum(1 for r in config_rows if r.hit)
        ranks = [r.rank for r in config_rows if r.hit and r.rank is not None]
        rank1 = sum(1 for r in config_rows if r.hit and r.rank == 1)
        mean_rank = sum(ranks) / len(ranks) if ranks else 0.0
        distinct = sum(
            1
            for r in config_rows
            if r.hit and hits_by_query.get(r.query_id) == [config]
        )
        comparison.append(
            {
                "config": config,
                "answerable_total": str(total),
                "hits": str(hits),
                "hit_rate": f"{(hits / total):.2f}" if total else "0.00",
                "rank1_hits": str(rank1),
                "precision_at_1": f"{(rank1 / total):.2f}" if total else "0.00",
                "mean_hit_rank": f"{mean_rank:.2f}",
                "distinct_wins": str(distinct),
                "notes": "",
            }
        )
    return comparison


def default_chain_decision(comparison: list[dict[str, str]]) -> str:
    by_config = {row["config"]: row for row in comparison}
    hybrid = by_config.get("hybrid")
    rrf = by_config.get("bm25_rrf")
    if not hybrid or not rrf:
        return "insufficient_data"
    hybrid_hits = int(hybrid["hits"])
    rrf_hits = int(rrf["hits"])
    hybrid_rank1 = int(hybrid["rank1_hits"])
    rrf_rank1 = int(rrf["rank1_hits"])
    rrf_distinct = int(rrf["distinct_wins"])
    hybrid_distinct = int(hybrid["distinct_wins"])
    # 只有 RRF 在难评测集上命中更多，或 hit@k 相同但 precision@1 明显更优且无独占劣势时，才建议切换。
    if rrf_hits > hybrid_hits and rrf_distinct >= hybrid_distinct:
        return "consider_switch_to_bm25_rrf"
    if rrf_hits == hybrid_hits and rrf_rank1 > hybrid_rank1 and rrf_distinct >= hybrid_distinct:
        return "consider_switch_to_bm25_rrf_on_precision"
    return "keep_existing_hybrid"


def contains_any(value: str, terms: list[str]) -> bool:
    normalized = (value or "").casefold()
    return any((term or "").casefold() in normalized for term in terms)


def _split(value: str) -> list[str]:
    return [term.strip() for term in (value or "").split("|") if term.strip()]


def _parse_top_k(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return 8
    return parsed if parsed > 0 else 8


def _parse_bool(value: str) -> bool:
    return (value or "").strip().casefold() in {"yes", "true", "1"}


def _bool(value: bool) -> str:
    return "yes" if value else "no"


def _opt_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "yes" if value else "no"


def write_results(path: Path, rows: list[ConfigResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_row())


def write_comparison(path: Path, comparison: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COMPARISON_FIELDS)
        writer.writeheader()
        for row in comparison:
            writer.writerow(row)


def print_summary(
    all_rows: list[ConfigResult],
    comparison: list[dict[str, str]],
    queries: list[HardQuery],
    out: str,
    comparison_out: str,
) -> None:
    print(f"wrote per-query results to {out}")
    print(f"wrote config comparison to {comparison_out}")
    for row in comparison:
        print(
            f"{row['config']:<18} hits={row['hits']}/{row['answerable_total']} "
            f"hit_rate={row['hit_rate']} rank1={row['rank1_hits']} p@1={row['precision_at_1']} "
            f"mean_rank={row['mean_hit_rank']} distinct_wins={row['distinct_wins']}"
        )
    refusal_rows = [r for r in all_rows if r.expected_refused]
    refused_ok = sum(1 for r in refusal_rows if r.refusal_matched)
    print(f"refusal: {refused_ok}/{len(refusal_rows)} refused as expected (brain_default)")
    print(f"default_chain_decision: {default_chain_decision(comparison)}")


if __name__ == "__main__":
    main()

"""阶段 19 检索排序调优评测脚本。

在中文难评测集 (``data/evaluation/stage19_chinese_hard_queries.csv``) 上
对照四种配置：

- hybrid_baseline
- hybrid_fulltext_boost
- hybrid_metadata_demote
- hybrid_topic_anchor_strict

口径：
- 非 refusal 题：用 ``HybridSearchService(top_k=fetch_k=24)`` 拿候选，应用 ``source_type_reweight``
  得到 top-8；按 ``expected_source_hit`` 关键词判定 hit + rank；同时统计 top-1/top-8 的
  source_type 分布。
- refusal 题：跑 ``BrainService.answer``（默认 hybrid），用 ``refused`` 判定 refusal_accuracy。
  四种配置在 refusal 题上结果相同（保留 baseline 的 Brain 行为）。

输出：
- ``data/evaluation/stage19_retrieval_tuning_results.csv``（每 config × query 一行）
- ``data/evaluation/stage19_retrieval_tuning_summary.csv``（每 config 一行汇总）
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.brain.config import RetrievalConfig  # noqa: E402
from app.services.brain.service import BrainService  # noqa: E402
from app.services.retrieval.hybrid_search import (  # noqa: E402
    HybridSearchResult,
    HybridSearchService,
)
from app.services.retrieval.source_type_reweight import (  # noqa: E402
    BASELINE_WEIGHTS,
    DEEP_FULLTEXT_TYPES,
    FULLTEXT_BOOST_WEIGHTS,
    METADATA_DEMOTE_WEIGHTS,
    METADATA_TYPES,
    Stage19TuningWeights,
    TOPIC_ANCHOR_STRICT_WEIGHTS,
    reweight_results,
)
from scripts.explore_chinese_corpus import build_providers  # noqa: E402

QUERY_PATH = ROOT / "data" / "evaluation" / "stage19_chinese_hard_queries.csv"
RESULTS_PATH = ROOT / "data" / "evaluation" / "stage19_retrieval_tuning_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage19_retrieval_tuning_summary.csv"

CONFIGS: tuple[Stage19TuningWeights, ...] = (
    BASELINE_WEIGHTS,
    FULLTEXT_BOOST_WEIGHTS,
    METADATA_DEMOTE_WEIGHTS,
    TOPIC_ANCHOR_STRICT_WEIGHTS,
)


RESULT_FIELDS = [
    "config",
    "query_id",
    "query",
    "difficulty_type",
    "expected_source_type",
    "expected_refused",
    "hit",
    "rank_before",
    "rank_after",
    "deep_fulltext_in_top8",
    "metadata_in_top8",
    "deep_fulltext_top1",
    "metadata_top1",
    "source_match",
    "refusal_matched",
    "refused",
    "top_source_types",
    "top_source_titles",
    "decision",
    "next_action",
    "error",
]

SUMMARY_FIELDS = [
    "config",
    "non_refusal_total",
    "hits",
    "precision_at_1",
    "mean_rank",
    "deep_fulltext_top1_rate",
    "metadata_top1_rate",
    "refusal_total",
    "refusal_accuracy",
    "distinct_wins_vs_baseline",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real",
        action="store_true",
        help="使用 .env 配置的真实 MIMO+Jina；默认 deterministic。",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="每条 query 应用重权后返回的 top-K。默认 8。",
    )
    parser.add_argument(
        "--fetch-k",
        type=int,
        default=24,
        help="hybrid 召回阶段的候选池大小（要 >= top_k 才有重排空间）。默认 24。",
    )
    parser.add_argument(
        "--queries",
        type=str,
        default=str(QUERY_PATH),
    )
    parser.add_argument(
        "--out-results",
        type=str,
        default=str(RESULTS_PATH),
    )
    parser.add_argument(
        "--out-summary",
        type=str,
        default=str(SUMMARY_PATH),
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
                expected_source_hit=tuple(
                    term.strip()
                    for term in (row["expected_source_hit"] or "").split(";")
                    if term.strip()
                ),
                expected_source_type=row["expected_source_type"],
                expected_refused=row["expected_refused"].strip().lower() == "true",
                expected_answer_points=tuple(
                    term.strip()
                    for term in (row["expected_answer_points"] or "").split(";")
                    if term.strip()
                ),
                distractor_topics=row.get("distractor_topics", ""),
                notes=row.get("notes", ""),
            )
            for row in reader
        ]


def first_match_rank(
    results: list[HybridSearchResult],
    keywords: tuple[str, ...],
) -> int:
    """命中（标题或正文含任一 keyword）的最小 rank（1-based）；未命中返回 0。"""
    if not keywords:
        return 0
    lowered_keywords = [k.casefold() for k in keywords]
    for idx, result in enumerate(results, start=1):
        haystack = (result.document_title + " " + result.content).casefold()
        if any(kw in haystack for kw in lowered_keywords):
            return idx
    return 0


def count_in_top_k(results: list[HybridSearchResult], wanted: frozenset[str]) -> int:
    return sum(1 for r in results if r.source_type in wanted)


def is_source_type_match(top_result: HybridSearchResult, expected: str) -> bool:
    if expected == "any":
        return True
    return top_result.source_type == expected


def evaluate_non_refusal(
    baseline_results: list[HybridSearchResult],
    query: ChineseHardQuery,
    weights: Stage19TuningWeights,
    top_k: int,
) -> dict[str, str]:
    rank_before = first_match_rank(baseline_results[:top_k], query.expected_source_hit)
    reweighted = reweight_results(baseline_results, weights, query=query.query)
    top = reweighted[:top_k]
    rank_after = first_match_rank(top, query.expected_source_hit)
    hit = bool(rank_after)
    deep_top8 = count_in_top_k(top, DEEP_FULLTEXT_TYPES)
    meta_top8 = count_in_top_k(top, METADATA_TYPES)
    deep_top1 = bool(top and top[0].source_type in DEEP_FULLTEXT_TYPES)
    meta_top1 = bool(top and top[0].source_type in METADATA_TYPES)
    source_match = bool(top and is_source_type_match(top[0], query.expected_source_type))
    return {
        "config": weights.name,
        "query_id": query.query_id,
        "query": query.query,
        "difficulty_type": query.difficulty_type,
        "expected_source_type": query.expected_source_type,
        "expected_refused": str(query.expected_refused).lower(),
        "hit": str(hit).lower(),
        "rank_before": str(rank_before),
        "rank_after": str(rank_after),
        "deep_fulltext_in_top8": str(deep_top8),
        "metadata_in_top8": str(meta_top8),
        "deep_fulltext_top1": str(deep_top1).lower(),
        "metadata_top1": str(meta_top1).lower(),
        "source_match": str(source_match).lower(),
        "refusal_matched": "",
        "refused": "",
        "top_source_types": ";".join(r.source_type for r in top),
        "top_source_titles": " | ".join(r.document_title[:60] for r in top),
        "decision": "",
        "next_action": "",
        "error": "",
    }


def evaluate_refusal(
    brain: BrainService,
    query: ChineseHardQuery,
    weights_name: str,
    top_k: int,
) -> dict[str, str]:
    try:
        answer = brain.answer(
            question=query.query,
            config=RetrievalConfig(retrieval_mode="hybrid", top_k=top_k),
        )
        refused = bool(answer.refused)
        refusal_matched = refused == query.expected_refused
        return {
            "config": weights_name,
            "query_id": query.query_id,
            "query": query.query,
            "difficulty_type": query.difficulty_type,
            "expected_source_type": query.expected_source_type,
            "expected_refused": str(query.expected_refused).lower(),
            "hit": "",
            "rank_before": "",
            "rank_after": "",
            "deep_fulltext_in_top8": "",
            "metadata_in_top8": "",
            "deep_fulltext_top1": "",
            "metadata_top1": "",
            "source_match": "",
            "refusal_matched": str(refusal_matched).lower(),
            "refused": str(refused).lower(),
            "top_source_types": "",
            "top_source_titles": "",
            "decision": "",
            "next_action": "",
            "error": "",
        }
    except Exception as exc:
        return {
            "config": weights_name,
            "query_id": query.query_id,
            "query": query.query,
            "difficulty_type": query.difficulty_type,
            "expected_source_type": query.expected_source_type,
            "expected_refused": str(query.expected_refused).lower(),
            "hit": "",
            "rank_before": "",
            "rank_after": "",
            "deep_fulltext_in_top8": "",
            "metadata_in_top8": "",
            "deep_fulltext_top1": "",
            "metadata_top1": "",
            "source_match": "",
            "refusal_matched": "",
            "refused": "",
            "top_source_types": "",
            "top_source_titles": "",
            "decision": "",
            "next_action": "",
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }


def write_results(out: Path, rows: list[dict[str, str]]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """按 config 汇总；返回 (汇总行列表, 配置 -> 汇总行 dict)。"""
    by_config: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_config.setdefault(row["config"], []).append(row)

    baseline_rows = by_config.get(BASELINE_WEIGHTS.name, [])
    baseline_rank_by_qid = {
        r["query_id"]: int(r["rank_after"]) if r["rank_after"] else 0
        for r in baseline_rows
        if r["difficulty_type"] != "refusal"
    }

    summary_rows: list[dict[str, str]] = []
    summary_lookup: dict[str, dict[str, str]] = {}
    for config_name, cfg_rows in by_config.items():
        non_refusal = [r for r in cfg_rows if r["difficulty_type"] != "refusal"]
        refusal = [r for r in cfg_rows if r["difficulty_type"] == "refusal"]
        n = len(non_refusal)
        hits = sum(1 for r in non_refusal if r["hit"] == "true")
        top1_correct = sum(
            1
            for r in non_refusal
            if r["rank_after"] == "1"
        )
        deep_top1 = sum(1 for r in non_refusal if r["deep_fulltext_top1"] == "true")
        meta_top1 = sum(1 for r in non_refusal if r["metadata_top1"] == "true")
        hit_ranks = [int(r["rank_after"]) for r in non_refusal if r["rank_after"] not in {"", "0"}]
        mean_rank = round(sum(hit_ranks) / len(hit_ranks), 3) if hit_ranks else 0.0
        precision_at_1 = round(top1_correct / n, 3) if n else 0.0
        deep_top1_rate = round(deep_top1 / n, 3) if n else 0.0
        meta_top1_rate = round(meta_top1 / n, 3) if n else 0.0
        ref_matched = sum(1 for r in refusal if r["refusal_matched"] == "true")
        ref_acc = round(ref_matched / len(refusal), 3) if refusal else 0.0
        distinct_wins = 0
        if config_name != BASELINE_WEIGHTS.name:
            for r in non_refusal:
                base_rank = baseline_rank_by_qid.get(r["query_id"], 0)
                cur_rank = int(r["rank_after"]) if r["rank_after"] else 0
                # 把 0（未命中）当作很大的 rank
                base_eff = base_rank if base_rank else 9999
                cur_eff = cur_rank if cur_rank else 9999
                if cur_eff < base_eff:
                    distinct_wins += 1
        row = {
            "config": config_name,
            "non_refusal_total": str(n),
            "hits": str(hits),
            "precision_at_1": str(precision_at_1),
            "mean_rank": str(mean_rank),
            "deep_fulltext_top1_rate": str(deep_top1_rate),
            "metadata_top1_rate": str(meta_top1_rate),
            "refusal_total": str(len(refusal)),
            "refusal_accuracy": str(ref_acc),
            "distinct_wins_vs_baseline": str(distinct_wins),
            "decision": "",
            "next_action": "",
        }
        summary_rows.append(row)
        summary_lookup[config_name] = row
    return summary_rows, summary_lookup


def apply_decisions(
    summary_lookup: dict[str, dict[str, str]],
    rows: list[dict[str, str]],
) -> str:
    """按门槛打 decision/next_action；返回总体结论字符串。

    门槛：candidate.precision@1 - baseline.precision@1 >= 0.10 且
    candidate.deep_fulltext_top1_rate - baseline.deep_fulltext_top1_rate >= 0.20 且
    candidate.refusal_accuracy >= baseline.refusal_accuracy。
    """
    baseline = summary_lookup.get(BASELINE_WEIGHTS.name)
    if not baseline:
        return "no_baseline"
    base_p1 = float(baseline["precision_at_1"])
    base_deep = float(baseline["deep_fulltext_top1_rate"])
    base_ref = float(baseline["refusal_accuracy"])

    promoted: list[str] = []
    for name, summary in summary_lookup.items():
        if name == BASELINE_WEIGHTS.name:
            summary["decision"] = "baseline"
            summary["next_action"] = "保持默认链路；与候选配置对照"
            continue
        d_p1 = float(summary["precision_at_1"]) - base_p1
        d_deep = float(summary["deep_fulltext_top1_rate"]) - base_deep
        ref_ok = float(summary["refusal_accuracy"]) >= base_ref
        meets_threshold = d_p1 >= 0.10 and d_deep >= 0.20 and ref_ok
        if meets_threshold:
            summary["decision"] = "promote_candidate"
            summary["next_action"] = (
                f"满足切换门槛（Δp@1=+{d_p1:.2f}, Δdeep_top1=+{d_deep:.2f}）：建议作为默认 hybrid 后处理"
            )
            promoted.append(name)
        else:
            reasons = []
            if d_p1 < 0.10:
                reasons.append(f"Δp@1={d_p1:+.2f}<0.10")
            if d_deep < 0.20:
                reasons.append(f"Δdeep_top1={d_deep:+.2f}<0.20")
            if not ref_ok:
                reasons.append("refusal_accuracy 退化")
            summary["decision"] = "keep_existing_hybrid"
            summary["next_action"] = "; ".join(reasons) or "未达切换门槛"

    if promoted:
        overall = f"switch_default_to:{','.join(promoted)}"
    else:
        overall = "keep_existing_hybrid"

    # 把决策回写到 results 行
    for row in rows:
        cfg = row["config"]
        summary = summary_lookup.get(cfg)
        if summary:
            row["decision"] = summary["decision"]
            row["next_action"] = summary["next_action"][:140]
    return overall


def write_summary(out: Path, rows: list[dict[str, str]]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    init_db()
    chat, embed, config_mode = build_providers(real=args.real)
    queries = load_queries(Path(args.queries))

    rows: list[dict[str, str]] = []
    with SessionLocal() as db:
        hybrid = HybridSearchService(db=db, embedding_provider=embed)
        brain = BrainService(
            db=db,
            chat_model_provider=chat,
            embedding_provider=embed,
            log_answers=False,
        )

        for query in queries:
            if query.expected_refused:
                # refusal 题：默认 Brain 行为，四 config 同结果
                for weights in CONFIGS:
                    row = evaluate_refusal(brain, query, weights.name, top_k=args.top_k)
                    rows.append(row)
                continue

            baseline_results = hybrid.search(query=query.query, top_k=args.fetch_k)
            for weights in CONFIGS:
                rows.append(
                    evaluate_non_refusal(
                        baseline_results=baseline_results,
                        query=query,
                        weights=weights,
                        top_k=args.top_k,
                    )
                )

    summary_rows, summary_lookup = summarize(rows)
    overall = apply_decisions(summary_lookup, rows)

    write_results(Path(args.out_results), rows)
    write_summary(Path(args.out_summary), summary_rows)
    print(f"stage19 retrieval tuning ({config_mode}) -> overall={overall}")
    for row in summary_rows:
        print(
            f"  {row['config']:<28} "
            f"p@1={row['precision_at_1']} "
            f"deep_top1={row['deep_fulltext_top1_rate']} "
            f"meta_top1={row['metadata_top1_rate']} "
            f"refusal_acc={row['refusal_accuracy']} "
            f"wins_vs_baseline={row['distinct_wins_vs_baseline']} "
            f"decision={row['decision']}"
        )


if __name__ == "__main__":
    main()

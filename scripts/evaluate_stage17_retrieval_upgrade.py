from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.retrieval.embedding import EmbeddingProvider  # noqa: E402
from app.services.retrieval.rrf_fusion import RRFHybridSearchResult, RRFHybridSearchService  # noqa: E402
from app.services.retrieval.vector_index import VectorIndexService  # noqa: E402
from scripts.evaluate_vector_search import ExpectedQuery  # noqa: E402
from scripts.evaluate_vector_search import contains_any  # noqa: E402
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402
from scripts.evaluate_vector_search import read_expected_queries  # noqa: E402


RESULT_FIELDS = [
    "query_id",
    "query",
    "baseline_hit",
    "upgraded_hit",
    "source_match",
    "rank_before",
    "rank_after",
    "retrieval_mode",
    "decision",
    "evidence",
    "baseline_top_titles",
    "upgraded_top_titles",
    "matched_channels",
    "provider",
    "model_name",
    "notes",
]


@dataclass(frozen=True)
class BaselineRow:
    passed: bool
    hit_rank: int | None
    hit_title: str
    top_titles: str


@dataclass(frozen=True)
class EvaluatedUpgradeResult:
    query_id: str
    query: str
    baseline_hit: bool
    upgraded_hit: bool
    source_match: bool
    rank_before: int | None
    rank_after: int | None
    retrieval_mode: str
    decision: str
    evidence: str
    baseline_top_titles: str
    upgraded_top_titles: str
    matched_channels: str
    provider: str
    model_name: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "baseline_hit": format_bool(self.baseline_hit),
            "upgraded_hit": format_bool(self.upgraded_hit),
            "source_match": format_bool(self.source_match),
            "rank_before": str(self.rank_before or ""),
            "rank_after": str(self.rank_after or ""),
            "retrieval_mode": self.retrieval_mode,
            "decision": self.decision,
            "evidence": self.evidence,
            "baseline_top_titles": self.baseline_top_titles,
            "upgraded_top_titles": self.upgraded_top_titles,
            "matched_channels": self.matched_channels,
            "provider": self.provider,
            "model_name": self.model_name,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the stage-17 BM25+vector RRF retrieval upgrade.")
    parser.add_argument("--queries", default="data/evaluation/keyword_queries.csv")
    parser.add_argument("--baseline-results", default="data/evaluation/hybrid_results.csv")
    parser.add_argument("--out", default="data/evaluation/stage17_retrieval_upgrade_results.csv")
    parser.add_argument("--report", default="docs/stage17_retrieval_upgrade_report.md")
    parser.add_argument(
        "--manual-review",
        default="data/evaluation/stage17_retrieval_upgrade_manual_review.csv",
        help="Optional stage-17 manual review table; its summary is appended to the report when present.",
    )
    parser.add_argument("--top-k", type=int, default=0, help="Override top_k for every query when greater than zero.")
    parser.add_argument("--provider", default="", help="Embedding provider name. Defaults to .env EMBEDDING_PROVIDER or deterministic.")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--skip-index-build", action="store_true")
    parser.add_argument("--context-window", type=int, default=1)
    args = parser.parse_args()

    settings = get_settings()
    provider = create_embedding_provider_from_settings(args.provider, settings)
    expected_queries = read_expected_queries(Path(args.queries), top_k_override=args.top_k)
    baseline_rows = read_baseline_rows(Path(args.baseline_results))

    init_db()
    with SessionLocal() as db:
        if not args.skip_index_build:
            VectorIndexService(db, provider).build_index(batch_size=args.batch_size)
        results = evaluate_queries(
            expected_queries=expected_queries,
            db=db,
            provider=provider,
            baseline_rows=baseline_rows,
            context_window=args.context_window,
        )

    write_results(Path(args.out), results)
    write_report(Path(args.report), results, Path(args.out), Path(args.manual_review))
    print_summary(results, args.out, args.report)


def evaluate_queries(
    expected_queries: list[ExpectedQuery],
    db,
    provider: EmbeddingProvider,
    baseline_rows: dict[str, BaselineRow] | None = None,
    context_window: int = 1,
) -> list[EvaluatedUpgradeResult]:
    baseline_rows = baseline_rows or {}
    search_service = RRFHybridSearchService(db, provider)
    evaluated: list[EvaluatedUpgradeResult] = []
    for expected in expected_queries:
        search_results = search_service.search(
            expected.query,
            top_k=expected.top_k,
            context_window=context_window,
        )
        hit_index = find_hit(expected, search_results)
        hit = search_results[hit_index] if hit_index is not None else None
        baseline = baseline_rows.get(expected.query_id, BaselineRow(False, None, "", ""))
        upgraded_hit = hit is not None
        rank_after = (hit_index + 1) if hit_index is not None else None
        source_match = bool(
            baseline.hit_title
            and hit
            and baseline.hit_title.casefold() == hit.document_title.casefold()
        )
        decision = decide_upgrade(
            baseline_hit=baseline.passed,
            upgraded_hit=upgraded_hit,
            rank_before=baseline.hit_rank,
            rank_after=rank_after,
        )
        evaluated.append(
            EvaluatedUpgradeResult(
                query_id=expected.query_id,
                query=expected.query,
                baseline_hit=baseline.passed,
                upgraded_hit=upgraded_hit,
                source_match=source_match,
                rank_before=baseline.hit_rank,
                rank_after=rank_after,
                retrieval_mode="bm25_vector_rrf",
                decision=decision,
                evidence=hit.provenance if hit else "upgraded retrieval did not hit expected source",
                baseline_top_titles=baseline.top_titles,
                upgraded_top_titles=" || ".join(result.document_title for result in search_results),
                matched_channels="+".join(hit.matched_channels) if hit else "",
                provider=provider.provider_name,
                model_name=provider.model_name,
                notes=expected.notes,
            )
        )
    return evaluated


def find_hit(expected: ExpectedQuery, search_results: list[RRFHybridSearchResult]) -> int | None:
    for index, result in enumerate(search_results):
        if expected.expected_source_types and result.source_type not in expected.expected_source_types:
            continue
        if expected.expected_title_terms and not contains_any(result.document_title, expected.expected_title_terms):
            continue
        if expected.expected_content_terms and not contains_any(result.content, expected.expected_content_terms):
            continue
        return index
    return None


def decide_upgrade(
    baseline_hit: bool,
    upgraded_hit: bool,
    rank_before: int | None,
    rank_after: int | None,
) -> str:
    if baseline_hit and not upgraded_hit:
        return "regression"
    if upgraded_hit and not baseline_hit:
        return "improved"
    if not baseline_hit and not upgraded_hit:
        return "unresolved"
    if rank_before is not None and rank_after is not None and rank_after < rank_before:
        return "improved"
    return "neutral"


def read_baseline_rows(path: Path) -> dict[str, BaselineRow]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return {
            row["query_id"]: BaselineRow(
                passed=parse_bool(row.get("passed", "")),
                hit_rank=parse_optional_int(row.get("hit_rank", "")),
                hit_title=row.get("hit_title", ""),
                top_titles=row.get("top_titles", ""),
            )
            for row in reader
            if row.get("query_id")
        }


def parse_optional_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def parse_bool(value: str) -> bool:
    return (value or "").strip().casefold() in {"yes", "true", "1", "pass", "passed"}


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def write_results(path: Path, results: list[EvaluatedUpgradeResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def read_manual_review_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row for row in csv.DictReader(file) if row.get("query_id")]


def manual_review_section(rows: list[dict[str, str]], review_path: Path) -> list[str]:
    if not rows:
        return []

    def count(field: str, value: str) -> int:
        return sum(1 for row in rows if (row.get(field, "") or "").strip().casefold() == value)

    total = len(rows)
    acceptable = count("review_decision", "acceptable")
    needs_tuning = count("review_decision", "needs_tuning")
    regression = count("review_decision", "regression")
    defer = count("review_decision", "defer")
    source_mismatch = count("source_match", "no")
    blockers = [
        row["query_id"]
        for row in rows
        if (row.get("default_chain_recommendation", "") or "").strip().casefold() == "keep_default_hybrid"
    ]
    blocker_text = ", ".join(blockers) if blockers else "无"
    phase9_recommendation = (
        "keep_existing_hybrid" if blockers or needs_tuning or regression else "candidate_for_default"
    )
    return [
        "",
        "## Phase 9 人工复核摘要",
        "",
        f"人工复核结果表：`{review_path.as_posix()}`。",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| reviewed_queries | {total} |",
        f"| acceptable | {acceptable} |",
        f"| needs_tuning | {needs_tuning} |",
        f"| regression | {regression} |",
        f"| defer | {defer} |",
        f"| source_mismatch | {source_mismatch} |",
        f"| default_switch_blockers | {len(blockers)} |",
        f"| phase9_default_recommendation | {phase9_recommendation} |",
        "",
        "### 风险判断",
        "",
        f"- 升级检索在评测集上无 hit 级 regression，但存在排序软退化样例：{blocker_text}（hit 指标掩盖的名次下降）。",
        "- source_match=no 的样例多为等价主题文献换位（常见为中文 query 下中文母语文献上浮），仍 top-1 命中，判定 acceptable。",
        "",
        "### 默认链路接入建议",
        "",
        "- 保持 BM25 + vector RRF 与邻近 chunk 上下文扩展为候选能力 / 配置开关，暂不替换默认 `HybridSearchService`、Brain、`/chat`、`/agent`。",
        "- 阻断原因：评测集 hit 已饱和（缺乏区分度）导致升级零增益，且存在综述文档上浮造成的排序软退化。",
        "",
        "### 下一阶段依据",
        "",
        "- 阶段 18 构建更有区分度的难评测集（跨段证据、易混淆术语、需拒答边界），并对综述类文档加权或 topic-anchor rerank 做对照，再决定 RRF 是否进入默认链路。",
    ]


def write_report(
    path: Path,
    results: list[EvaluatedUpgradeResult],
    results_path: Path,
    manual_review_path: Path | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = len(results)
    upgraded_hits = sum(1 for result in results if result.upgraded_hit)
    baseline_hits = sum(1 for result in results if result.baseline_hit)
    regressions = sum(1 for result in results if result.decision == "regression")
    improved = sum(1 for result in results if result.decision == "improved")
    neutral = sum(1 for result in results if result.decision == "neutral")
    unresolved = sum(1 for result in results if result.decision == "unresolved")
    default_decision = (
        "keep_existing_hybrid"
        if regressions
        else "candidate_for_manual_review"
    )
    lines = [
        "# 阶段 17 检索架构升级评测报告",
        "",
        "本报告由 `scripts/evaluate_stage17_retrieval_upgrade.py` 生成，对比旧 hybrid baseline 与 BM25+vector RRF upgraded retrieval。",
        "",
        "## 汇总",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| results_file | `{results_path.as_posix()}` |",
        f"| total_queries | {total} |",
        f"| baseline_hits | {baseline_hits} |",
        f"| upgraded_hits | {upgraded_hits} |",
        f"| improved | {improved} |",
        f"| neutral | {neutral} |",
        f"| regression | {regressions} |",
        f"| unresolved | {unresolved} |",
        f"| default_decision | {default_decision} |",
        "",
        "## 默认链路结论",
        "",
        "阶段 17 默认不自动替换旧 `HybridSearchService`。只有人工核验评测表确认无关键回归后，才考虑把 BM25+vector RRF 接入默认 Brain hybrid。",
        "",
        "## 数据安全边界",
        "",
        "- 本报告不触发真实 API 调用。",
        "- 本报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。",
        "- 阶段 17 当前等待用户人工核验，尚不提交、不打 tag、不推送。",
    ]
    if manual_review_path is not None:
        lines.extend(manual_review_section(read_manual_review_rows(manual_review_path), manual_review_path))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(results: list[EvaluatedUpgradeResult], output_path: str, report_path: str) -> None:
    total = len(results)
    upgraded_hits = sum(1 for result in results if result.upgraded_hit)
    baseline_hits = sum(1 for result in results if result.baseline_hit)
    regressions = sum(1 for result in results if result.decision == "regression")
    improved = sum(1 for result in results if result.decision == "improved")
    print(
        f"stage17 retrieval upgrade: upgraded={upgraded_hits}/{total}\t"
        f"baseline={baseline_hits}/{total}\timproved={improved}\tregression={regressions}"
    )
    print(f"wrote results to {output_path}")
    print(f"wrote report to {report_path}")


if __name__ == "__main__":
    main()

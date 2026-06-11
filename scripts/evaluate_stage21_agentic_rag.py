"""阶段 21：Agentic RAG vs Baseline 对照评测。

用 stage19 中文难评测集比较：
- baseline: BrainService 默认 hybrid 链路
- agentic: LangGraph 状态图

指标：coverage_ratio, p@1, deep_top1, refusal_accuracy。
门槛：Δp@1>=0.10 AND Δdeep_top1>=0.20 AND refusal not degraded。
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.agentic.graph import run_agentic_rag  # noqa: E402
from app.services.brain.config import RetrievalConfig  # noqa: E402
from app.services.brain.service import BrainService  # noqa: E402
from app.services.generation.chat_model import create_chat_model_provider  # noqa: E402
from app.services.retrieval.keyword_search import expand_query_terms, normalize_text  # noqa: E402
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402

QUERY_PATH = ROOT / "data" / "evaluation" / "stage19_chinese_hard_queries.csv"
RESULTS_PATH = ROOT / "data" / "evaluation" / "stage21_agentic_comparison_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage21_agentic_comparison_summary.csv"
DECISION_PATH = ROOT / "data" / "evaluation" / "stage21_agentic_decision.csv"

COVERAGE_THRESHOLD = 0.60
DEEP_FULLTEXT_TYPES = frozenset({
    "open_access_pdf",
    "institutional_access_pdf",
    "local_file",
})

RESULT_FIELDS = [
    "query_id", "config", "query", "difficulty_type", "expected_refused",
    "hit", "coverage_ratio", "deep_fulltext_top1", "refusal_matched",
    "refused", "top1_source_type", "top1_document_title",
    "iteration_count", "error",
]

SUMMARY_FIELDS = [
    "config", "non_refusal_total", "non_refusal_errors", "hits", "precision_at_1",
    "avg_coverage_ratio", "deep_fulltext_top1_rate",
    "refusal_total", "refusal_errors", "refusal_accuracy",
    "error_rate", "decision",
]


@dataclass(frozen=True)
class ChineseHardQuery:
    query_id: str
    query: str
    difficulty_type: str
    expected_refused: bool
    expected_answer_points: tuple[str, ...]


def load_queries(path: Path) -> list[ChineseHardQuery]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            ChineseHardQuery(
                query_id=row["query_id"],
                query=row["query"],
                difficulty_type=row["difficulty_type"],
                expected_refused=row["expected_refused"].strip().lower() == "true",
                expected_answer_points=tuple(
                    p.strip() for p in (row.get("expected_answer_points", "") or "").split(";") if p.strip()
                ),
            )
            for row in reader
        ]


def normalized_for_match(text: str | None) -> str:
    return re.sub(r"\s+", "", normalize_text(text))


def chinese_fragments(text: str) -> tuple[str, ...]:
    chars = [c for c in text if "一" <= c <= "鿿"]
    frags: list[str] = []
    for size in (3, 2):
        for i in range(max(0, len(chars) - size + 1)):
            f = "".join(chars[i:i + size])
            if f not in frags:
                frags.append(f)
    return tuple(frags)


def point_is_covered(point: str, evidence_text: str) -> bool:
    normalized = normalized_for_match(point)
    if not normalized:
        return False
    if normalized in evidence_text:
        return True
    for expanded in expand_query_terms(point):
        term = normalized_for_match(expanded.text)
        if len(term) >= 2 and term in evidence_text:
            return True
    frags = chinese_fragments(point)
    if frags:
        matched = sum(1 for f in frags if f in evidence_text)
        if matched >= min(2, len(frags)):
            return True
    return False


def coverage_ratio(points: tuple[str, ...], evidence_text: str) -> tuple[float, list[str], list[str]]:
    if not points:
        return 0.0, [], []
    norm_evidence = normalized_for_match(evidence_text)
    covered = [p for p in points if point_is_covered(p, norm_evidence)]
    missing = [p for p in points if p not in covered]
    return round(len(covered) / len(points), 3), covered, missing


def evidence_text_for_sources(sources) -> str:
    parts = []
    for s in sources:
        parts.append(getattr(s, "heading_path", "") or "")
        parts.append(getattr(s, "content", "") or "")
    return " ".join(parts)


def run_baseline_eval(db, embedding_provider, chat_model_provider, query: ChineseHardQuery) -> dict:
    config_name = "baseline_hybrid"
    try:
        brain = BrainService(db=db, chat_model_provider=chat_model_provider,
                             embedding_provider=embedding_provider, log_answers=False)
        result = brain.answer(query.query, config=RetrievalConfig(retrieval_mode="hybrid", top_k=5))

        if query.expected_refused:
            refusal_matched = result.refused == query.expected_refused
            return make_row(query, config_name, refused=result.refused,
                            refusal_matched=refusal_matched, hit=refusal_matched)

        evidence = evidence_text_for_sources(result.sources[:1])
        ratio, _, _ = coverage_ratio(query.expected_answer_points, evidence)
        hit = ratio >= COVERAGE_THRESHOLD
        top1 = result.sources[0] if result.sources else None
        deep = bool(top1 and getattr(top1, "source_type", "") in DEEP_FULLTEXT_TYPES)
        return make_row(query, config_name, hit=hit, ratio=ratio, deep=deep,
                        refused=result.refused, top1=top1)
    except Exception as exc:
        return make_row(query, config_name, error=str(exc)[:200])


def run_agentic_eval(db, embedding_provider, chat_model_provider, query: ChineseHardQuery) -> dict:
    config_name = "agentic_rag"
    try:
        result = run_agentic_rag(
            question=query.query,
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_model_provider,
        )

        if query.expected_refused:
            refusal_matched = result.refused == query.expected_refused
            return make_row(query, config_name, refused=result.refused,
                            refusal_matched=refusal_matched, hit=refusal_matched,
                            iteration_count=result.iteration_count)

        evidence = evidence_text_for_sources(result.sources[:1])
        ratio, _, _ = coverage_ratio(query.expected_answer_points, evidence)
        hit = ratio >= COVERAGE_THRESHOLD
        top1 = result.sources[0] if result.sources else None
        deep = bool(top1 and getattr(top1, "source_type", "") in DEEP_FULLTEXT_TYPES)
        return make_row(query, config_name, hit=hit, ratio=ratio, deep=deep,
                        refused=result.refused, top1=top1,
                        iteration_count=result.iteration_count)
    except Exception as exc:
        return make_row(query, config_name, error=str(exc)[:200])


def make_row(query, config, *, hit=False, ratio=0.0, deep=False,
             refused=False, refusal_matched=None, top1=None,
             iteration_count=0, error="") -> dict:
    return {
        "query_id": query.query_id,
        "config": config,
        "query": query.query,
        "difficulty_type": query.difficulty_type,
        "expected_refused": str(query.expected_refused).lower(),
        "hit": str(hit).lower(),
        "coverage_ratio": f"{ratio:.3f}" if not query.expected_refused else "",
        "deep_fulltext_top1": str(deep).lower() if not query.expected_refused else "",
        "refusal_matched": str(refusal_matched).lower() if refusal_matched is not None else "",
        "refused": str(refused).lower(),
        "top1_source_type": getattr(top1, "source_type", "") if top1 else "",
        "top1_document_title": (getattr(top1, "document_title", "") or "")[:120] if top1 else "",
        "iteration_count": str(iteration_count),
        "error": error,
    }


def summarize_config(config_name: str, rows: list[dict]) -> dict:
    non_refusal = [r for r in rows if r["difficulty_type"] != "refusal"]
    refusal = [r for r in rows if r["difficulty_type"] == "refusal"]

    nr_ok = [r for r in non_refusal if not r.get("error")]
    nr_errors = len(non_refusal) - len(nr_ok)
    ref_ok = [r for r in refusal if not r.get("error")]
    ref_errors = len(refusal) - len(ref_ok)

    hits = sum(1 for r in nr_ok if r["hit"] == "true")
    coverages = [float(r["coverage_ratio"]) for r in nr_ok if r["coverage_ratio"]]
    deep_top1s = sum(1 for r in nr_ok if r["deep_fulltext_top1"] == "true")
    refusal_matched = sum(1 for r in ref_ok if r["refusal_matched"] == "true")
    nr_total = len(nr_ok)
    ref_total = len(ref_ok)
    total_rows = len(rows)
    total_errors = nr_errors + ref_errors
    error_rate = total_errors / total_rows if total_rows else 0.0
    return {
        "config": config_name,
        "non_refusal_total": str(nr_total),
        "non_refusal_errors": str(nr_errors),
        "hits": str(hits),
        "precision_at_1": f"{hits / nr_total:.3f}" if nr_total else "0.000",
        "avg_coverage_ratio": f"{sum(coverages) / len(coverages):.3f}" if coverages else "0.000",
        "deep_fulltext_top1_rate": f"{deep_top1s / nr_total:.3f}" if nr_total else "0.000",
        "refusal_total": str(ref_total),
        "refusal_errors": str(ref_errors),
        "refusal_accuracy": f"{refusal_matched / ref_total:.3f}" if ref_total else "1.000",
        "error_rate": f"{error_rate:.3f}",
        "decision": "",
    }


def make_decision(baseline_summary: dict, agentic_summary: dict) -> dict:
    bp1 = float(baseline_summary["precision_at_1"])
    ap1 = float(agentic_summary["precision_at_1"])
    bdt = float(baseline_summary["deep_fulltext_top1_rate"])
    adt = float(agentic_summary["deep_fulltext_top1_rate"])
    bra = float(baseline_summary["refusal_accuracy"])
    ara = float(agentic_summary["refusal_accuracy"])
    b_err = float(baseline_summary["error_rate"])
    a_err = float(agentic_summary["error_rate"])

    dp1 = ap1 - bp1
    ddt = adt - bdt
    refusal_ok = ara >= bra - 1e-9

    high_error = b_err > 0.25 or a_err > 0.25

    threshold_met = dp1 >= 0.10 - 1e-9 and ddt >= 0.20 - 1e-9 and refusal_ok
    if high_error:
        decision = "inconclusive_high_error_rate"
    elif threshold_met:
        decision = "integrate_agentic_mode"
    else:
        decision = "keep_candidate"

    reason_parts = []
    if high_error:
        reason_parts.append(f"error_rate baseline={b_err:.3f} agentic={a_err:.3f}")
    if dp1 < 0.10 - 1e-9:
        reason_parts.append(f"delta_p1={dp1:+.3f}<0.10")
    if ddt < 0.20 - 1e-9:
        reason_parts.append(f"delta_deep_top1={ddt:+.3f}<0.20")
    if not refusal_ok:
        reason_parts.append(f"refusal_degraded={ara:.3f}<{bra:.3f}")
    reason = "; ".join(reason_parts) if reason_parts else "all thresholds met"

    return {
        "baseline_p1": f"{bp1:.3f}",
        "agentic_p1": f"{ap1:.3f}",
        "delta_p1": f"{dp1:+.3f}",
        "baseline_deep_top1": f"{bdt:.3f}",
        "agentic_deep_top1": f"{adt:.3f}",
        "delta_deep_top1": f"{ddt:+.3f}",
        "baseline_refusal_acc": f"{bra:.3f}",
        "agentic_refusal_acc": f"{ara:.3f}",
        "baseline_error_rate": f"{b_err:.3f}",
        "agentic_error_rate": f"{a_err:.3f}",
        "decision": decision,
        "reason": reason,
    }


def main() -> None:
    init_db()
    settings = get_settings()
    embedding_provider = create_embedding_provider_from_settings(None, settings)
    chat_model_provider = create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
    )

    queries = load_queries(QUERY_PATH)
    all_rows: list[dict] = []

    db = SessionLocal()
    try:
        for i, q in enumerate(queries):
            print(f"  [{i+1}/{len(queries)}] {q.query_id} baseline...", flush=True)
            all_rows.append(run_baseline_eval(db, embedding_provider, chat_model_provider, q))
            print(f"  [{i+1}/{len(queries)}] {q.query_id} agentic...", flush=True)
            all_rows.append(run_agentic_eval(db, embedding_provider, chat_model_provider, q))
    finally:
        db.close()

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    baseline_rows = [r for r in all_rows if r["config"] == "baseline_hybrid"]
    agentic_rows = [r for r in all_rows if r["config"] == "agentic_rag"]
    bs = summarize_config("baseline_hybrid", baseline_rows)
    ag = summarize_config("agentic_rag", agentic_rows)

    decision = make_decision(bs, ag)
    bs["decision"] = "baseline"
    ag["decision"] = decision["decision"]

    with SUMMARY_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows([bs, ag])

    decision_fields = list(decision.keys())
    with DECISION_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=decision_fields)
        writer.writeheader()
        writer.writerow(decision)

    print(f"stage21 agentic vs baseline comparison")
    print(f"  baseline:  p@1={bs['precision_at_1']} deep_top1={bs['deep_fulltext_top1_rate']} refusal_acc={bs['refusal_accuracy']} errors={bs['non_refusal_errors']}+{bs['refusal_errors']} error_rate={bs['error_rate']}")
    print(f"  agentic:   p@1={ag['precision_at_1']} deep_top1={ag['deep_fulltext_top1_rate']} refusal_acc={ag['refusal_accuracy']} errors={ag['non_refusal_errors']}+{ag['refusal_errors']} error_rate={ag['error_rate']}")
    print(f"  delta_p1={decision['delta_p1']} delta_deep_top1={decision['delta_deep_top1']}")
    print(f"  decision: {decision['decision']}")
    print(f"  reason: {decision['reason']}")


if __name__ == "__main__":
    main()

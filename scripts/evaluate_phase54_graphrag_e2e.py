from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from app.services.generation.chat_model import (  # noqa: E402
    ChatMessage,
    ChatModelProvider,
    create_chat_model_provider,
)
from app.services.graphrag.graph_search import GraphEnhancedSearchService  # noqa: E402
from app.services.observability.latency_trace import (  # noqa: E402
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService  # noqa: E402
from app.services.retrieval.reranking import create_reranking_provider  # noqa: E402


DEFAULT_CASES = Path("data/evaluation/phase54_graphrag_eval_cases.csv")
DEFAULT_RESULTS = Path("data/evaluation/phase54_graphrag_eval_results.csv")
DEFAULT_SUMMARY = Path("data/evaluation/phase54_graphrag_eval_summary.csv")
DEFAULT_ABLATION = Path("data/evaluation/phase54_graphrag_eval_ablation.csv")
DEFAULT_GRAPH = Path("data/knowledge_graph/domain_graph.json")
SOURCE_MARKER_RE = re.compile(r"\[(\d+)\]")
GRAPH_INTENT_COMPLETENESS_DELTA_GATE = 0.3
GRAPH_INTENT_ACCURACY_DELTA_GATE = 0.0
ORDINARY_ACCURACY_DELTA_GATE = -0.1
NEGATIVE_GRAPH_FALSE_POSITIVE_GATE = 0
JUDGE_SCORE_KEYS = (
    "baseline_accuracy",
    "graph_accuracy",
    "baseline_completeness",
    "graph_completeness",
    "baseline_citation_quality",
    "graph_citation_quality",
)


@dataclass(frozen=True)
class Phase54EvalCase:
    case_id: str
    category: str
    question: str
    expected_graph_intent: bool
    expected_entities: str
    expected_relation_focus: str
    expected_behavior: str


def load_cases(path: Path) -> list[Phase54EvalCase]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            Phase54EvalCase(
                case_id=row["case_id"],
                category=row["category"],
                question=row["question"],
                expected_graph_intent=row["expected_graph_intent"].casefold() == "true",
                expected_entities=row["expected_entities"],
                expected_relation_focus=row["expected_relation_focus"],
                expected_behavior=row["expected_behavior"],
            )
            for row in reader
        ]


def dry_run_rows(cases: list[Phase54EvalCase]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    result_rows: list[dict[str, str]] = []
    ablation_rows: list[dict[str, str]] = []
    for case in cases:
        graph_strategy = "graph_enhanced_search" if case.expected_graph_intent else "hybrid_knowledge_search"
        result_rows.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "status": "dry_run",
                "expected_graph_intent": str(case.expected_graph_intent).lower(),
                "expected_relation_focus": case.expected_relation_focus,
                "baseline_top_chunk_ids": "",
                "graph_top_chunk_ids": "",
                "baseline_top_title_hashes": "",
                "graph_top_title_hashes": "",
                "graph_candidate_chunk_count": "",
                "graph_used_match_count": "",
                "baseline_answer_chars": "",
                "graph_answer_chars": "",
                "baseline_accuracy": "",
                "graph_accuracy": "",
                "baseline_completeness": "",
                "graph_completeness": "",
                "baseline_citation_quality": "",
                "graph_citation_quality": "",
                "judge_reason": "",
                "error": "",
            }
        )
        ablation_rows.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "baseline_strategy": "hybrid_knowledge_search",
                "graph_strategy": graph_strategy,
                "expected_delta": "graph_needed" if case.expected_graph_intent else "no_graph_required",
            }
        )
    return result_rows, ablation_rows


def filter_cases(
    cases: list[Phase54EvalCase],
    *,
    case_ids: list[str],
    categories: list[str],
) -> list[Phase54EvalCase]:
    selected = cases
    if case_ids:
        wanted_ids = {case_id.strip() for case_id in case_ids if case_id.strip()}
        selected = [case for case in selected if case.case_id in wanted_ids]
    if categories:
        wanted_categories = {category.strip() for category in categories if category.strip()}
        selected = [case for case in selected if case.category in wanted_categories]
    return selected


def run_retrieval(
    cases: list[Phase54EvalCase],
    *,
    graph_path: Path,
    top_k: int,
    answer_mode: str,
    results_output: Path | None = None,
    summary_output: Path | None = None,
    resume: bool = False,
    progress: bool = False,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    settings = get_settings()
    embedding = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    execute_answers = answer_mode in {"answer_only", "judge"}
    answer_provider = build_answer_provider(settings) if execute_answers else None
    judge_provider = build_judge_provider(settings) if answer_mode == "judge" else None
    if execute_answers and answer_provider is None:
        raise RuntimeError("Phase 54D answer execution requires configured chat provider")
    if answer_mode == "judge" and judge_provider is None:
        raise RuntimeError("Phase 54D --execute requires configured chat and judge providers")
    engine = create_database_engine(settings.database_url)

    result_rows = resume_result_rows(results_output) if resume and results_output else []
    completed_ids = {
        row["case_id"]
        for row in result_rows
        if row.get("status") in {"completed", "retrieval_only", "answer_only"}
    }
    cases_to_run = [case for case in cases if case.case_id not in completed_ids]
    ablation_rows: list[dict[str, str]] = []
    with Session(engine) as db:
        baseline_service = HybridSearchService(db, embedding)
        graph_final_reranker = None
        graph_hybrid_factory = None
        graph_hybrid_candidate_k = None
        graph_multi_channel_candidate_k = None
        graph_final_candidate_k = None
        graph_final_graph_candidate_quota = 0
        if getattr(settings, "reranking_enabled", False):
            graph_final_reranker = create_reranking_provider(
                provider_name=settings.reranking_provider,
                model_name=settings.reranking_model_name,
                api_key=settings.reranking_api_key,
                base_url=settings.reranking_base_url,
                timeout_seconds=settings.reranking_timeout_seconds,
            )
            graph_hybrid_factory = lambda: HybridSearchService(db, embedding, reranking_enabled=False)
            graph_hybrid_candidate_k = settings.reranking_recall_k
            graph_multi_channel_candidate_k = settings.reranking_recall_k
            graph_final_candidate_k = max(settings.reranking_recall_k * 4, 350)
            graph_final_graph_candidate_quota = min(settings.reranking_recall_k, top_k * 2)
        graph_service = GraphEnhancedSearchService(
            db,
            embedding,
            graph_path=graph_path,
            hybrid_service_factory=graph_hybrid_factory,
            hybrid_candidate_k=graph_hybrid_candidate_k,
            multi_channel_candidate_k=graph_multi_channel_candidate_k,
            final_reranking_provider=graph_final_reranker,
            final_rerank_candidate_k=graph_final_candidate_k,
            final_graph_candidate_quota=graph_final_graph_candidate_quota,
        )
        for index, case in enumerate(cases_to_run, start=1):
            if progress:
                print(
                    f"phase54 case_start {index}/{len(cases_to_run)} "
                    f"{case.case_id} {case.category}",
                    flush=True,
                )
            try:
                trace = LatencyTrace()
                trace_token = set_current_latency_trace(trace)
                try:
                    baseline_results = baseline_service.search(case.question, top_k=top_k)
                    graph_service.relation_focus = None if case.expected_relation_focus == "none" else case.expected_relation_focus
                    graph_outcome = graph_service.search(case.question, top_k=top_k)
                    trace_values = dict(trace.values)
                finally:
                    reset_current_latency_trace(trace_token)
                baseline_answer = ""
                graph_answer = ""
                judge_scores: dict[str, str] = {}
                if execute_answers and answer_provider:
                    baseline_answer = generate_answer(answer_provider, case.question, baseline_results)
                    graph_answer = generate_answer(answer_provider, case.question, graph_outcome.results)
                if answer_mode == "judge" and judge_provider:
                    judge_scores = judge_pair(
                        judge_provider,
                        case,
                        baseline_answer=baseline_answer,
                        graph_answer=graph_answer,
                        baseline_results=baseline_results,
                        graph_results=graph_outcome.results,
                    )
                result_rows.append(
                    {
                        "case_id": case.case_id,
                        "category": case.category,
                        "status": row_status(answer_mode),
                        "expected_graph_intent": str(case.expected_graph_intent).lower(),
                        "expected_relation_focus": case.expected_relation_focus,
                        "baseline_top_chunk_ids": join_chunk_ids(baseline_results),
                        "graph_top_chunk_ids": join_chunk_ids(graph_outcome.results),
                        "baseline_top_title_hashes": join_title_hashes(baseline_results),
                        "graph_top_title_hashes": join_title_hashes(graph_outcome.results),
                        "graph_candidate_chunk_count": str(graph_outcome.summary.candidate_chunk_count),
                        "graph_used_match_count": str(len(graph_outcome.graph_matches)),
                        "reranking_provider_configured": settings.reranking_provider if settings.reranking_enabled else "disabled",
                        "reranking_model_configured": settings.reranking_model_name if settings.reranking_enabled else "",
                        "reranking_base_url_configured": settings.reranking_base_url if settings.reranking_enabled else "",
                        "baseline_reranking_provider": str(trace_values.get("reranking_provider", "")),
                        "baseline_reranking_model": str(trace_values.get("reranking_model", "")),
                        "baseline_reranking_fallback": str(trace_values.get("reranking_fallback", "")),
                        "baseline_reranking_error": str(trace_values.get("reranking_error", "")),
                        "graph_final_reranking_provider": str(trace_values.get("graph_final_reranking_provider", "")),
                        "graph_final_reranking_model": str(trace_values.get("graph_final_reranking_model", "")),
                        "graph_final_reranking_fallback": str(trace_values.get("graph_final_reranking_fallback", "")),
                        "graph_final_reranking_error": str(trace_values.get("graph_final_reranking_error", "")),
                        "baseline_answer_chars": str(len(baseline_answer)) if execute_answers else "",
                        "graph_answer_chars": str(len(graph_answer)) if execute_answers else "",
                        "baseline_accuracy": judge_scores.get("baseline_accuracy", ""),
                        "graph_accuracy": judge_scores.get("graph_accuracy", ""),
                        "baseline_completeness": judge_scores.get("baseline_completeness", ""),
                        "graph_completeness": judge_scores.get("graph_completeness", ""),
                        "baseline_citation_quality": judge_scores.get("baseline_citation_quality", ""),
                        "graph_citation_quality": judge_scores.get("graph_citation_quality", ""),
                        "judge_reason": judge_scores.get("reason", "")[:180],
                        "error": "",
                    }
                )
            except Exception as exc:  # pragma: no cover - real-provider path records sanitized failures.
                result_rows.append(error_row(case, type(exc).__name__))
            if progress:
                latest = result_rows[-1]
                print(
                    f"phase54 case_done {case.case_id} status={latest.get('status')} "
                    f"graph_candidates={latest.get('graph_candidate_chunk_count')} "
                    f"error={latest.get('error')}",
                    flush=True,
                )
            if results_output:
                write_csv(results_output, result_rows)
            if summary_output:
                write_csv(summary_output, summarize(result_rows))
        for case in cases:
            ablation_rows.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "baseline_strategy": "hybrid_knowledge_search",
                    "graph_strategy": "graph_enhanced_search",
                    "expected_delta": "graph_needed" if case.expected_graph_intent else "no_graph_required",
                }
            )
    return result_rows, ablation_rows


def existing_result_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def resume_result_rows(path: Path | None) -> list[dict[str, str]]:
    return [
        row
        for row in existing_result_rows(path)
        if row.get("status") in {"completed", "retrieval_only", "answer_only"}
    ]


def row_status(answer_mode: str) -> str:
    if answer_mode == "judge":
        return "completed"
    if answer_mode == "answer_only":
        return "answer_only"
    return "retrieval_only"


def build_answer_provider(settings) -> ChatModelProvider | None:
    if not provider_configured(
        provider=getattr(settings, "chat_model_provider", ""),
        model_name=getattr(settings, "chat_model_name", ""),
        api_key=getattr(settings, "chat_model_api_key", ""),
        base_url=getattr(settings, "chat_model_base_url", ""),
    ):
        return None
    return create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )


def build_judge_provider(settings) -> ChatModelProvider | None:
    if not provider_configured(
        provider=getattr(settings, "judge_model_provider", ""),
        model_name=getattr(settings, "judge_model_name", ""),
        api_key=getattr(settings, "judge_model_api_key", ""),
        base_url=getattr(settings, "judge_model_base_url", ""),
    ):
        return None
    return create_chat_model_provider(
        provider_name=settings.judge_model_provider,
        model_name=settings.judge_model_name,
        api_key=settings.judge_model_api_key,
        base_url=settings.judge_model_base_url,
        temperature=settings.judge_model_temperature,
        timeout_seconds=settings.judge_model_timeout_seconds,
        max_attempts=getattr(settings, "judge_model_max_attempts", 3),
    )


def provider_configured(*, provider: str, model_name: str, api_key: str, base_url: str) -> bool:
    return bool(provider and model_name and api_key and base_url)


def missing_provider_fields(
    *,
    provider: str,
    model_name: str,
    api_key: str,
    base_url: str,
    prefix: str,
) -> list[str]:
    missing: list[str] = []
    if not provider:
        missing.append(f"{prefix}_PROVIDER")
    if not model_name:
        missing.append(f"{prefix}_NAME")
    if not api_key:
        missing.append(f"{prefix}_API_KEY")
    if not base_url:
        missing.append(f"{prefix}_BASE_URL")
    return missing


def embedding_configured(settings: Any) -> bool:
    return bool(
        getattr(settings, "embedding_provider", "")
        and getattr(settings, "embedding_model_name", "")
        and getattr(settings, "embedding_api_key", "")
        and getattr(settings, "embedding_base_url", "")
    )


def preflight_report(
    cases: list[Phase54EvalCase],
    *,
    graph_path: Path,
    settings: Any | None = None,
) -> list[dict[str, str]]:
    settings = settings or get_settings()
    category_counts: dict[str, int] = {}
    for case in cases:
        category_counts[case.category] = category_counts.get(case.category, 0) + 1
    graph_exists = graph_path.exists()
    graph_size_bytes = graph_path.stat().st_size if graph_exists else 0
    chat_ready = provider_configured(
        provider=getattr(settings, "chat_model_provider", ""),
        model_name=getattr(settings, "chat_model_name", ""),
        api_key=getattr(settings, "chat_model_api_key", ""),
        base_url=getattr(settings, "chat_model_base_url", ""),
    )
    judge_provider = getattr(settings, "judge_model_provider", "")
    judge_model_name = getattr(settings, "judge_model_name", "")
    judge_api_key = getattr(settings, "judge_model_api_key", "")
    judge_base_url = getattr(settings, "judge_model_base_url", "")
    judge_ready = provider_configured(
        provider=judge_provider,
        model_name=judge_model_name,
        api_key=judge_api_key,
        base_url=judge_base_url,
    )
    judge_missing = missing_provider_fields(
        provider=judge_provider,
        model_name=judge_model_name,
        api_key=judge_api_key,
        base_url=judge_base_url,
        prefix="JUDGE_MODEL",
    )
    embed_ready = embedding_configured(settings)
    formal_ready = graph_exists and len(cases) >= 40 and chat_ready and judge_ready and embed_ready
    rows = [
        {"check": "cases_total", "status": "pass" if len(cases) >= 40 else "fail", "value": str(len(cases))},
        {
            "check": "graph_intent_cases",
            "status": "pass" if sum(1 for case in cases if case.expected_graph_intent) >= 30 else "warn",
            "value": str(sum(1 for case in cases if case.expected_graph_intent)),
        },
        {
            "check": "negative_offtopic_cases",
            "status": "pass" if category_counts.get("negative_offtopic", 0) >= 3 else "warn",
            "value": str(category_counts.get("negative_offtopic", 0)),
        },
        {"check": "graph_file_exists", "status": "pass" if graph_exists else "fail", "value": str(graph_path)},
        {"check": "graph_file_size_bytes", "status": "pass" if graph_size_bytes > 0 else "fail", "value": str(graph_size_bytes)},
        {"check": "chat_provider_configured", "status": "pass" if chat_ready else "fail", "value": str(chat_ready).lower()},
        {"check": "judge_provider_configured", "status": "pass" if judge_ready else "fail", "value": str(judge_ready).lower()},
        {
            "check": "judge_model_provider_configured",
            "status": "pass" if bool(judge_provider) else "fail",
            "value": str(bool(judge_provider)).lower(),
        },
        {
            "check": "judge_model_name_configured",
            "status": "pass" if bool(judge_model_name) else "fail",
            "value": str(bool(judge_model_name)).lower(),
        },
        {
            "check": "judge_model_api_key_configured",
            "status": "pass" if bool(judge_api_key) else "fail",
            "value": str(bool(judge_api_key)).lower(),
        },
        {
            "check": "judge_model_base_url_configured",
            "status": "pass" if bool(judge_base_url) else "fail",
            "value": str(bool(judge_base_url)).lower(),
        },
        {
            "check": "judge_model_missing_fields",
            "status": "pass" if not judge_missing else "fail",
            "value": ",".join(judge_missing),
        },
        {"check": "embedding_provider_configured", "status": "pass" if embed_ready else "fail", "value": str(embed_ready).lower()},
        {
            "check": "reranking_enabled",
            "status": "info",
            "value": str(bool(getattr(settings, "reranking_enabled", False))).lower(),
        },
        {"check": "formal_judge_ready", "status": "pass" if formal_ready else "fail", "value": str(formal_ready).lower()},
    ]
    return rows


def print_preflight(rows: list[dict[str, str]]) -> None:
    for row in rows:
        print(f"phase54 preflight {row['check']} status={row['status']} value={row['value']}")


def generate_answer(
    provider: ChatModelProvider,
    question: str,
    results: list[HybridSearchResult],
) -> str:
    messages = [
        ChatMessage(
            role="system",
            content=(
                "Answer only from the provided evidence. Use [1], [2] style citations. "
                "If evidence is insufficient, say so briefly."
            ),
        ),
        ChatMessage(
            role="user",
            content=f"Question: {question}\n\nContext:\n{context_from_results(results)}",
        ),
    ]
    return provider.generate(messages).answer


def judge_pair(
    provider: ChatModelProvider,
    case: Phase54EvalCase,
    *,
    baseline_answer: str,
    graph_answer: str,
    baseline_results: list[HybridSearchResult],
    graph_results: list[HybridSearchResult],
) -> dict[str, str]:
    prompt = {
        "case_id": case.case_id,
        "category": case.category,
        "question": case.question,
        "expected_behavior": case.expected_behavior,
        "baseline_answer": baseline_answer[:1600],
        "graph_answer": graph_answer[:1600],
        "baseline_source_titles": [result.document_title[:120] for result in baseline_results[:5]],
        "graph_source_titles": [result.document_title[:120] for result in graph_results[:5]],
    }
    messages = [
        ChatMessage(
            role="system",
            content=(
                "Return compact JSON only with integer scores 1-5 for "
                "baseline_accuracy, graph_accuracy, baseline_completeness, "
                "graph_completeness, baseline_citation_quality, graph_citation_quality, "
                "plus a short reason. Do not include hidden reasoning."
            ),
        ),
        ChatMessage(role="user", content=json.dumps(prompt, ensure_ascii=False)),
    ]
    answer = provider.generate(messages).answer
    return parse_judge_json(answer)


def parse_judge_json(text: str) -> dict[str, str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {"reason": "judge_json_parse_error"}
        data = json.loads(match.group(0))
    output: dict[str, str] = {}
    for key in (
        "baseline_accuracy",
        "graph_accuracy",
        "baseline_completeness",
        "graph_completeness",
        "baseline_citation_quality",
        "graph_citation_quality",
    ):
        output[key] = str(int(data.get(key, 0))) if str(data.get(key, "")).strip() else ""
    output["reason"] = str(data.get("reason") or "")[:180]
    return output


def context_from_results(results: list[HybridSearchResult]) -> str:
    lines: list[str] = []
    for index, result in enumerate(results[:6], start=1):
        snippet = " ".join((result.content or "").split())[:700]
        lines.append(f"[{index}] title={result.document_title[:120]} chunk_id={result.chunk_id} {snippet}")
    return "\n".join(lines) or "No evidence."


def join_chunk_ids(results: list[HybridSearchResult]) -> str:
    return "|".join(str(result.chunk_id) for result in results[:8])


def join_title_hashes(results: list[HybridSearchResult]) -> str:
    return "|".join(short_hash(result.document_title) for result in results[:8])


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def error_row(case: Phase54EvalCase, error: str) -> dict[str, str]:
    return {
        "case_id": case.case_id,
        "category": case.category,
        "status": "error",
        "expected_graph_intent": str(case.expected_graph_intent).lower(),
        "expected_relation_focus": case.expected_relation_focus,
        "baseline_top_chunk_ids": "",
        "graph_top_chunk_ids": "",
        "baseline_top_title_hashes": "",
        "graph_top_title_hashes": "",
        "graph_candidate_chunk_count": "",
        "graph_used_match_count": "",
        "reranking_provider_configured": "",
        "reranking_model_configured": "",
        "reranking_base_url_configured": "",
        "baseline_reranking_provider": "",
        "baseline_reranking_model": "",
        "baseline_reranking_fallback": "",
        "baseline_reranking_error": "",
        "graph_final_reranking_provider": "",
        "graph_final_reranking_model": "",
        "graph_final_reranking_fallback": "",
        "graph_final_reranking_error": "",
        "baseline_answer_chars": "",
        "graph_answer_chars": "",
        "baseline_accuracy": "",
        "graph_accuracy": "",
        "baseline_completeness": "",
        "graph_completeness": "",
        "baseline_citation_quality": "",
        "graph_citation_quality": "",
        "judge_reason": "",
        "error": error,
    }


def summarize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    total = len(rows)
    graph_cases = [row for row in rows if row["expected_graph_intent"] == "true"]
    ordinary_cases = [row for row in rows if row["category"] == "ordinary_baseline"]
    negative_cases = [row for row in rows if row["category"] == "negative_offtopic"]
    summary = [
        {"metric": "total_cases", "value": str(total)},
        {"metric": "graph_intent_cases", "value": str(len(graph_cases))},
        {"metric": "ordinary_baseline_cases", "value": str(len(ordinary_cases))},
        {"metric": "negative_offtopic_cases", "value": str(len(negative_cases))},
        {"metric": "completed_rows", "value": str(sum(1 for row in rows if row["status"] == "completed"))},
        {"metric": "answer_only_rows", "value": str(sum(1 for row in rows if row["status"] == "answer_only"))},
        {"metric": "retrieval_only_rows", "value": str(sum(1 for row in rows if row["status"] == "retrieval_only"))},
        {"metric": "error_rows", "value": str(sum(1 for row in rows if row["status"] == "error"))},
    ]
    if any(row.get("graph_candidate_chunk_count") for row in rows):
        summary.extend(retrieval_summary_rows(rows))
    if any(row["graph_completeness"] for row in rows):
        summary.extend(score_delta_rows(rows))
        summary.extend(formal_gate_rows(rows))
    summary.append(
        {
            "metric": "safety_boundary",
            "value": "ids_title_hashes_counts_scores_only_no_full_chunks_no_provider_payloads",
        }
    )
    return summary


def retrieval_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    graph_candidate_counts = [
        int(row["graph_candidate_chunk_count"])
        for row in rows
        if row.get("graph_candidate_chunk_count")
    ]
    used_match_counts = [
        int(row["graph_used_match_count"])
        for row in rows
        if row.get("graph_used_match_count")
    ]
    negative_false_positive_count = sum(
        1
        for row in rows
        if row.get("category") == "negative_offtopic"
        and int(row.get("graph_candidate_chunk_count") or 0) > 0
    )
    same_top_count = 0
    comparable_count = 0
    for row in rows:
        baseline_ids = row.get("baseline_top_chunk_ids") or ""
        graph_ids = row.get("graph_top_chunk_ids") or ""
        if not baseline_ids or not graph_ids:
            continue
        comparable_count += 1
        same_top_count += baseline_ids.split("|", 1)[0] == graph_ids.split("|", 1)[0]
    return [
        {"metric": "graph_candidate_avg", "value": f"{mean(graph_candidate_counts):.4f}"},
        {"metric": "graph_candidate_max", "value": str(max(graph_candidate_counts, default=0))},
        {"metric": "graph_used_match_avg", "value": f"{mean(used_match_counts):.4f}"},
        {"metric": "graph_used_match_max", "value": str(max(used_match_counts, default=0))},
        {"metric": "negative_graph_false_positive_count", "value": str(negative_false_positive_count)},
        {"metric": "same_top_chunk_count", "value": str(same_top_count)},
        {"metric": "same_top_chunk_comparable_count", "value": str(comparable_count)},
    ]


def mean(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def score_delta_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    graph_rows = [row for row in rows if row["expected_graph_intent"] == "true"]
    ordinary_rows = [row for row in rows if row["category"] == "ordinary_baseline"]
    negative_rows = [row for row in rows if row["category"] == "negative_offtopic"]
    return [
        {"metric": "graph_intent_accuracy_delta", "value": f"{mean_delta(graph_rows, 'accuracy'):.4f}"},
        {"metric": "graph_intent_completeness_delta", "value": f"{mean_delta(graph_rows, 'completeness'):.4f}"},
        {
            "metric": "graph_intent_citation_quality_delta",
            "value": f"{mean_delta(graph_rows, 'citation_quality'):.4f}",
        },
        {"metric": "ordinary_accuracy_delta", "value": f"{mean_delta(ordinary_rows, 'accuracy'):.4f}"},
        {"metric": "negative_graph_candidate_avg", "value": f"{mean_numeric(negative_rows, 'graph_candidate_chunk_count'):.4f}"},
    ]


def formal_gate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    total = len(rows)
    completed = sum(1 for row in rows if row.get("status") == "completed")
    scored = sum(1 for row in rows if row.get("status") == "completed" and has_complete_judge_scores(row))
    graph_rows = [row for row in rows if row.get("expected_graph_intent") == "true"]
    ordinary_rows = [row for row in rows if row.get("category") == "ordinary_baseline"]
    graph_accuracy_delta = mean_delta(graph_rows, "accuracy")
    graph_completeness_delta = mean_delta(graph_rows, "completeness")
    ordinary_accuracy_delta = mean_delta(ordinary_rows, "accuracy")
    negative_false_positive_count = sum(
        1
        for row in rows
        if row.get("category") == "negative_offtopic"
        and int(row.get("graph_candidate_chunk_count") or 0) > NEGATIVE_GRAPH_FALSE_POSITIVE_GATE
    )
    if completed < total:
        decision = "pending"
        reason = f"completed_judge_rows={completed}/{total}"
    elif scored < total:
        decision = "pending"
        reason = f"complete_judge_score_rows={scored}/{total}"
    else:
        failures: list[str] = []
        if graph_completeness_delta < GRAPH_INTENT_COMPLETENESS_DELTA_GATE:
            failures.append(
                f"graph_intent_completeness_delta<{GRAPH_INTENT_COMPLETENESS_DELTA_GATE}"
            )
        if graph_accuracy_delta < GRAPH_INTENT_ACCURACY_DELTA_GATE:
            failures.append(f"graph_intent_accuracy_delta<{GRAPH_INTENT_ACCURACY_DELTA_GATE}")
        if ordinary_accuracy_delta < ORDINARY_ACCURACY_DELTA_GATE:
            failures.append(f"ordinary_accuracy_delta<{ORDINARY_ACCURACY_DELTA_GATE}")
        if negative_false_positive_count > NEGATIVE_GRAPH_FALSE_POSITIVE_GATE:
            failures.append("negative_graph_false_positive_count>0")
        decision = "review_required" if failures else "pass"
        reason = "|".join(failures) if failures else "all_phase54d_gates_passed"
    return [
        {"metric": "formal_judge_completed_rows", "value": str(completed)},
        {"metric": "formal_judge_scored_rows", "value": str(scored)},
        {"metric": "formal_judge_total_rows", "value": str(total)},
        {"metric": "formal_judge_gate_decision", "value": decision},
        {"metric": "formal_judge_gate_reason", "value": reason},
    ]


def has_complete_judge_scores(row: dict[str, str]) -> bool:
    return all(str(row.get(key) or "").strip() for key in JUDGE_SCORE_KEYS)


def mean_delta(rows: list[dict[str, str]], metric: str) -> float:
    deltas = []
    for row in rows:
        baseline = row.get(f"baseline_{metric}", "")
        graph = row.get(f"graph_{metric}", "")
        if baseline and graph:
            deltas.append(float(graph) - float(baseline))
    return sum(deltas) / len(deltas) if deltas else 0.0


def mean_numeric(rows: list[dict[str, str]], key: str) -> float:
    values = [float(row[key]) for row in rows if row.get(key)]
    return sum(values) / len(values) if values else 0.0


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames_for_rows(rows))
        writer.writeheader()
        writer.writerows(rows)


def fieldnames_for_rows(rows: list[dict[str, str]]) -> list[str]:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 54 GraphRAG E2E retrieval/generation.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH))
    parser.add_argument("--results-output", default=str(DEFAULT_RESULTS))
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--ablation-output", default=str(DEFAULT_ABLATION))
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="Limit cases for smoke runs; 0 means all cases.")
    parser.add_argument("--case-id", action="append", default=[], help="Run only this case id; repeatable.")
    parser.add_argument("--category", action="append", default=[], help="Run only this category; repeatable.")
    parser.add_argument("--resume", action="store_true", help="Skip completed/retrieval-only rows in results output.")
    parser.add_argument("--progress", action="store_true", help="Print per-case progress without exposing content.")
    parser.add_argument("--preflight", action="store_true", help="Check local readiness without provider calls.")
    parser.add_argument("--require-judge", action="store_true", help="Return non-zero when formal judge readiness fails.")
    parser.add_argument(
        "--summarize-existing",
        action="store_true",
        help="Rebuild summary/ablation from an existing results CSV without provider calls.",
    )
    parser.add_argument("--execute-retrieval", action="store_true", help="Run local baseline and graph retrieval.")
    parser.add_argument("--execute-answers", action="store_true", help="Run retrieval and real answer generation without judge.")
    parser.add_argument("--execute", action="store_true", help="Run retrieval, answer generation, and judge calls.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_cases(Path(args.cases))
    cases = filter_cases(cases, case_ids=args.case_id, categories=args.category)
    if args.limit > 0:
        cases = cases[: args.limit]
    if args.preflight:
        rows = preflight_report(cases, graph_path=Path(args.graph))
        print_preflight(rows)
        write_csv(Path(args.summary_output), rows)
        formal_ready = next(row for row in rows if row["check"] == "formal_judge_ready")
        return 2 if args.require_judge and formal_ready["status"] != "pass" else 0
    if args.summarize_existing:
        rows = existing_result_rows(Path(args.results_output))
        if not rows:
            raise FileNotFoundError(f"no existing result rows found: {args.results_output}")
        _, ablation = dry_run_rows(cases)
        write_csv(Path(args.summary_output), summarize(rows))
        write_csv(Path(args.ablation_output), ablation)
        print(
            "phase54_graphrag_e2e "
            f"cases={len(cases)} mode=summarize_existing "
            f"results={args.results_output} summary={args.summary_output}"
        )
        return 0
    if args.execute or args.execute_answers or args.execute_retrieval:
        rows, ablation = run_retrieval(
            cases,
            graph_path=Path(args.graph),
            top_k=args.top_k,
            answer_mode=("judge" if args.execute else "answer_only" if args.execute_answers else "retrieval_only"),
            results_output=Path(args.results_output),
            summary_output=Path(args.summary_output),
            resume=args.resume,
            progress=args.progress,
        )
    else:
        rows, ablation = dry_run_rows(cases)
    write_csv(Path(args.results_output), rows)
    write_csv(Path(args.summary_output), summarize(rows))
    write_csv(Path(args.ablation_output), ablation)
    print(
        "phase54_graphrag_e2e "
        f"cases={len(cases)} mode="
        f"{'execute' if args.execute else 'answer_only' if args.execute_answers else 'retrieval' if args.execute_retrieval else 'dry_run'} "
        f"results={args.results_output} summary={args.summary_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

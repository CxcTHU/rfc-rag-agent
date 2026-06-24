from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.agent.memory_context import (  # noqa: E402
    AgentMemoryContext,
    LLMMemoryIntentClassifier,
    MemoryIntent,
    MemoryPolicyDecision,
    PriorEvidenceMemory,
    PriorEvidenceRelevance,
    build_agent_memory_context,
    decide_memory_policy,
    infer_memory_decision_hint,
)
from app.services.conversation.session_memory import SessionMemory  # noqa: E402
from app.services.generation.chat_model import (  # noqa: E402
    ChatMessage,
    ChatModelProvider,
    create_chat_model_provider,
)
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider  # noqa: E402


DEFAULT_CASES = ROOT / "data" / "evaluation" / "phase52_memory_real_api_cases.csv"
DEFAULT_RESULTS = ROOT / "data" / "evaluation" / "phase52_memory_real_api_results.csv"
DEFAULT_SUMMARY = ROOT / "data" / "evaluation" / "phase52_memory_real_api_summary.csv"
DEFAULT_ABLATION = ROOT / "data" / "evaluation" / "phase52_memory_real_api_ablation.csv"

EvalMode = Literal["current", "legacy"]

RESULT_FIELDS = [
    "run_at",
    "case_id",
    "category",
    "mode",
    "status",
    "chat_provider",
    "chat_model",
    "embedding_provider",
    "embedding_model",
    "judge_provider",
    "judge_model",
    "expected_intent",
    "actual_intent",
    "intent_match",
    "expected_prior_decision",
    "actual_prior_decision",
    "prior_decision_match",
    "expected_planner_action",
    "actual_planner_action",
    "planner_action_match",
    "expected_long_term_enabled",
    "actual_long_term_enabled",
    "memory_citation_source",
    "prior_relevance_score",
    "prior_relevance_passed",
    "prior_source_count",
    "memory_policy_route",
    "judge_intent_score",
    "judge_prior_decision_score",
    "judge_planner_score",
    "judge_safety_score",
    "judge_risk_level",
    "judge_short_reason",
    "judge_next_action",
    "latency_ms",
    "error",
]

SUMMARY_FIELDS = [
    "mode",
    "status",
    "total_rows",
    "completed_rows",
    "error_rows",
    "skipped_rows",
    "intent_accuracy",
    "correction_recall",
    "prior_reuse_precision",
    "planner_action_accuracy",
    "avg_judge_intent_score",
    "avg_judge_prior_decision_score",
    "avg_judge_planner_score",
    "avg_judge_safety_score",
    "low_relevance_false_reuse_count",
    "stale_anchor_prior_reuse_count",
    "memory_citation_source_true_count",
    "long_term_enabled_count",
    "judge_high_risk_count",
    "gate",
    "decision",
]

ABLATION_FIELDS = [
    "metric",
    "current",
    "legacy",
    "delta",
    "improved",
]


@dataclass(frozen=True)
class RealMemoryEvalCase:
    case_id: str
    category: str
    turns: tuple[str, ...]
    current_question: str
    prior_source_count: int
    prior_answer_summary: str
    expected_intent: str
    expected_prior_decision: str
    expected_planner_action: str
    expected_long_term_enabled: bool
    expected_citation_from_prior_allowed: bool
    expected_guardrail: str
    baseline_failure_mode: str
    tags: str
    notes: str


@dataclass(frozen=True)
class Providers:
    chat: ChatModelProvider
    embedding: EmbeddingProvider
    judge: ChatModelProvider


def main() -> None:
    args = parse_args()
    cases = load_cases(Path(args.cases))
    if args.case_id:
        requested = set(args.case_id)
        cases = [case for case in cases if case.case_id in requested]
    if args.limit:
        cases = cases[: args.limit]
    modes: list[EvalMode] = ["current", "legacy"] if args.mode == "both" else [args.mode]
    rows = evaluate(cases, modes, args)
    write_csv(Path(args.results), RESULT_FIELDS, rows)
    summaries = summarize(rows)
    write_csv(Path(args.summary), SUMMARY_FIELDS, summaries)
    ablation = build_ablation(summaries)
    write_csv(Path(args.ablation), ABLATION_FIELDS, ablation)
    print(
        "phase52 real api memory eval -> "
        f"rows={len(rows)} completed={sum(1 for row in rows if row['status'] == 'completed')} "
        f"execute={str(args.execute).lower()} mode={args.mode} "
        f"summary={args.summary}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 52 real API memory evaluation.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--ablation", default=str(DEFAULT_ABLATION))
    parser.add_argument("--mode", choices=["current", "legacy", "both"], default="both")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--judge-provider", default=env_value("STAGE52_JUDGE_PROVIDER"))
    parser.add_argument("--judge-model", default=env_value("STAGE52_JUDGE_MODEL"))
    parser.add_argument("--judge-base-url", default=env_value("STAGE52_JUDGE_BASE_URL"))
    parser.add_argument("--judge-api-key", default=env_value("STAGE52_JUDGE_API_KEY"))
    return parser.parse_args()


def load_cases(path: Path) -> list[RealMemoryEvalCase]:
    rows: list[RealMemoryEvalCase] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "case_id",
            "category",
            "turns_json",
            "current_question",
            "prior_source_count",
            "prior_answer_summary",
            "expected_intent",
            "expected_prior_decision",
            "expected_planner_action",
            "expected_long_term_enabled",
            "expected_citation_from_prior_allowed",
            "expected_guardrail",
            "baseline_failure_mode",
            "tags",
            "notes",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing Phase 52 real API case fields: {', '.join(sorted(missing))}")
        for raw in reader:
            turns = json.loads(raw["turns_json"])
            if not isinstance(turns, list):
                raise ValueError(f"{raw['case_id']} turns_json must be a JSON list")
            rows.append(
                RealMemoryEvalCase(
                    case_id=raw["case_id"],
                    category=raw["category"],
                    turns=tuple(str(item) for item in turns),
                    current_question=raw["current_question"],
                    prior_source_count=int(raw["prior_source_count"] or 0),
                    prior_answer_summary=raw["prior_answer_summary"],
                    expected_intent=raw["expected_intent"],
                    expected_prior_decision=raw["expected_prior_decision"],
                    expected_planner_action=raw["expected_planner_action"],
                    expected_long_term_enabled=parse_bool(raw["expected_long_term_enabled"]),
                    expected_citation_from_prior_allowed=parse_bool(raw["expected_citation_from_prior_allowed"]),
                    expected_guardrail=raw["expected_guardrail"],
                    baseline_failure_mode=raw["baseline_failure_mode"],
                    tags=raw["tags"],
                    notes=raw["notes"],
                )
            )
    return rows


def evaluate(
    cases: Sequence[RealMemoryEvalCase],
    modes: Sequence[EvalMode],
    args: argparse.Namespace,
) -> list[dict[str, str]]:
    run_at = datetime.now(timezone.utc).isoformat()
    if not args.execute:
        return [dry_run_row(run_at, case, mode, args) for case in cases for mode in modes]
    providers = build_providers(args)
    missing = missing_real_config(args)
    if missing:
        return [
            skipped_row(run_at, case, mode, args, f"missing_real_configuration:{'|'.join(missing)}")
            for case in cases
            for mode in modes
        ]

    existing = read_result_rows(Path(args.results)) if args.resume else []
    existing_by_key = {
        row_key(row): row
        for row in existing
        if row.get("status") == "completed"
    }
    rows: list[dict[str, str]] = []
    for case in cases:
        pending_modes: list[EvalMode] = []
        for mode in modes:
            key = f"{case.case_id}:{mode}"
            if key in existing_by_key:
                rows.append(existing_by_key[key])
            else:
                pending_modes.append(mode)
        if not pending_modes:
            continue
        rows.extend(evaluate_one_case(run_at, case, pending_modes, providers))
        if args.resume:
            write_csv(Path(args.results), RESULT_FIELDS, rows)
            write_csv(Path(args.summary), SUMMARY_FIELDS, summarize(rows))
    return rows


def evaluate_one_case(
    run_at: str,
    case: RealMemoryEvalCase,
    modes: Sequence[EvalMode],
    providers: Providers,
) -> list[dict[str, str]]:
    started = time.perf_counter()
    try:
        prior_evidence = build_prior_evidence(case)
        current_context = build_agent_memory_context(
            question=case.current_question,
            history=list(case.turns),
            prior_evidence=prior_evidence,
            intent_classifier=LLMMemoryIntentClassifier(providers.chat),
            embedding_provider=providers.embedding,
        )
        rows: list[dict[str, str]] = []
        for mode in modes:
            context = current_context if mode == "current" else build_legacy_context(case, current_context)
            judged = judge_case(case, context, mode, providers.judge)
            rows.append(
                completed_row(
                    run_at,
                    case,
                    mode,
                    context,
                    providers,
                    judged,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            )
        return rows
    except Exception as exc:  # noqa: BLE001 - safe summary only.
        return [
            error_row(
                run_at,
                case,
                mode,
                providers,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=sanitize_text(str(exc), limit=240),
            )
            for mode in modes
        ]


def build_legacy_context(case: RealMemoryEvalCase, current: AgentMemoryContext) -> AgentMemoryContext:
    prior = current.prior_evidence
    legacy_relevance = PriorEvidenceRelevance(
        score=current.prior_relevance.score,
        passed=prior.source_count >= 3,
        threshold=3.0,
        reason="legacy source_count>=3 threshold",
    )
    decision_hint = legacy_decision_hint(
        case=case,
        intent=current.intent,
        session=current.session,
        prior=prior,
        prior_relevance=legacy_relevance,
    )
    if decision_hint == "reuse_prior_evidence":
        policy = MemoryPolicyDecision(
            decision_hint=decision_hint,
            planner_route="answer_from_prior_evidence",
            use_prior_evidence_for_answer=True,
            memory_used_for_planning=True,
            memory_used_for_answer=True,
            prior_relevance_score=legacy_relevance.score,
            prior_relevance_passed=legacy_relevance.passed,
            reason="legacy source_count threshold reuses prior evidence",
        )
    else:
        policy = decide_memory_policy(
            session=current.session,
            prior=prior,
            intent=current.intent,
            prior_relevance=legacy_relevance,
            decision_hint=decision_hint,
        )
    return AgentMemoryContext(
        session=current.session,
        prior_evidence=prior,
        prior_relevance=legacy_relevance,
        long_term=current.long_term,
        intent=current.intent,
        decision_hint=decision_hint,
        policy=policy,
    )


def legacy_decision_hint(
    *,
    case: RealMemoryEvalCase,
    intent: MemoryIntent,
    session: SessionMemory,
    prior: PriorEvidenceMemory,
    prior_relevance: PriorEvidenceRelevance,
) -> str:
    del case
    if prior.source_count >= 3 and intent.label in {"expand_followup", "contextual_followup"}:
        return "reuse_prior_evidence"
    return infer_memory_decision_hint(
        session=session,
        prior=prior,
        intent=intent,
        prior_relevance=prior_relevance,
    )


def judge_case(
    case: RealMemoryEvalCase,
    context: AgentMemoryContext,
    mode: EvalMode,
    judge: ChatModelProvider,
) -> dict[str, str]:
    payload = {
        "case_id": case.case_id,
        "category": case.category,
        "mode": mode,
        "current_question": sanitize_text(case.current_question, limit=220),
        "turn_summaries": [sanitize_text(item, limit=140) for item in case.turns[-5:]],
        "prior_answer_summary": sanitize_text(case.prior_answer_summary, limit=220),
        "expected": {
            "intent": case.expected_intent,
            "prior_decision": case.expected_prior_decision,
            "planner_action": case.expected_planner_action,
            "long_term_enabled": case.expected_long_term_enabled,
            "citation_from_prior_allowed": case.expected_citation_from_prior_allowed,
            "guardrail": case.expected_guardrail,
        },
        "observed": {
            "intent": context.intent.label,
            "prior_decision": actual_prior_decision(context),
            "planner_action": actual_planner_action(context),
            "policy_route": context.policy.planner_route,
            "prior_relevance_score": round(context.prior_relevance.score, 4),
            "prior_relevance_passed": context.prior_relevance.passed,
            "prior_source_count": context.prior_evidence.source_count,
            "memory_citation_source": context.policy.memory_citation_source,
            "long_term_enabled": context.long_term.enabled,
        },
        "baseline_failure_mode": sanitize_text(case.baseline_failure_mode, limit=180),
        "notes": sanitize_text(case.notes, limit=180),
    }
    result = judge.generate(
        [
            ChatMessage(
                role="system",
                content=(
                    "You are a strict evaluator for a RAG agent memory policy. "
                    "Return only JSON with keys intent_score, prior_decision_score, "
                    "planner_score, safety_score, risk_level, short_reason, next_action. "
                    "Scores are numbers from 0 to 1. The memory summary is never a citation source. "
                    "Prior evidence sources are compact retrieved source records, not the memory summary. "
                    "Do not mark high risk solely because prior evidence is reused when "
                    "memory_citation_source is false, prior_source_count is positive, and the expected "
                    "prior_decision is use_prior. "
                    "risk_level must reflect residual risk in the observed decision, not the inherent "
                    "difficulty of the case. If observed intent, prior_decision, planner_action, "
                    "memory_citation_source, and long_term_enabled all match the expected safe behavior, "
                    "risk_level must be low unless the observed fields themselves contain a safety violation. "
                    "Do not include chain-of-thought, raw provider metadata, secrets, or long source text."
                ),
            ),
            ChatMessage(role="user", content=json.dumps(payload, ensure_ascii=False)),
        ]
    )
    return parse_judge_json(result.answer)


def parse_judge_json(payload: str) -> dict[str, str]:
    text = strip_json_fence(payload)
    decoded = json.loads(text)
    if not isinstance(decoded, Mapping):
        raise RuntimeError("judge response must be a JSON object")
    return {
        "intent_score": format_score(decoded.get("intent_score")),
        "prior_decision_score": format_score(decoded.get("prior_decision_score")),
        "planner_score": format_score(decoded.get("planner_score")),
        "safety_score": format_score(decoded.get("safety_score")),
        "risk_level": normalize_risk(decoded.get("risk_level")),
        "short_reason": sanitize_text(str(decoded.get("short_reason") or ""), limit=220),
        "next_action": sanitize_text(str(decoded.get("next_action") or ""), limit=220),
    }


def build_prior_evidence(case: RealMemoryEvalCase) -> dict[str, Any]:
    return {
        "prior_sources": [
            {
                "source_id": f"phase52:{case.case_id}:{index}",
                "document_title": f"Sanitized prior source {index}",
                "content": sanitize_text(case.prior_answer_summary, limit=180),
            }
            for index in range(1, case.prior_source_count + 1)
        ],
        "prior_citations": list(range(1, case.prior_source_count + 1)),
        "prior_answer_summary": case.prior_answer_summary,
    }


def completed_row(
    run_at: str,
    case: RealMemoryEvalCase,
    mode: EvalMode,
    context: AgentMemoryContext,
    providers: Providers,
    judged: Mapping[str, str],
    *,
    latency_ms: int,
) -> dict[str, str]:
    prior_decision = actual_prior_decision(context)
    planner_action = actual_planner_action(context)
    return {
        "run_at": run_at,
        "case_id": case.case_id,
        "category": case.category,
        "mode": mode,
        "status": "completed",
        "chat_provider": providers.chat.provider_name,
        "chat_model": providers.chat.model_name,
        "embedding_provider": providers.embedding.provider_name,
        "embedding_model": providers.embedding.model_name,
        "judge_provider": providers.judge.provider_name,
        "judge_model": providers.judge.model_name,
        "expected_intent": case.expected_intent,
        "actual_intent": context.intent.label,
        "intent_match": str(context.intent.label == case.expected_intent).lower(),
        "expected_prior_decision": case.expected_prior_decision,
        "actual_prior_decision": prior_decision,
        "prior_decision_match": str(prior_decision == case.expected_prior_decision).lower(),
        "expected_planner_action": case.expected_planner_action,
        "actual_planner_action": planner_action,
        "planner_action_match": str(planner_action == case.expected_planner_action).lower(),
        "expected_long_term_enabled": str(case.expected_long_term_enabled).lower(),
        "actual_long_term_enabled": str(context.long_term.enabled).lower(),
        "memory_citation_source": str(context.policy.memory_citation_source).lower(),
        "prior_relevance_score": f"{context.prior_relevance.score:.4f}",
        "prior_relevance_passed": str(context.prior_relevance.passed).lower(),
        "prior_source_count": str(context.prior_evidence.source_count),
        "memory_policy_route": context.policy.planner_route,
        "judge_intent_score": judged["intent_score"],
        "judge_prior_decision_score": judged["prior_decision_score"],
        "judge_planner_score": judged["planner_score"],
        "judge_safety_score": judged["safety_score"],
        "judge_risk_level": judged["risk_level"],
        "judge_short_reason": judged["short_reason"],
        "judge_next_action": judged["next_action"],
        "latency_ms": str(latency_ms),
        "error": "",
    }


def dry_run_row(
    run_at: str,
    case: RealMemoryEvalCase,
    mode: EvalMode,
    args: argparse.Namespace,
) -> dict[str, str]:
    return base_non_completed_row(
        run_at,
        case,
        mode,
        status="dry_run",
        chat_provider="not_run",
        chat_model="not_run",
        embedding_provider="not_run",
        embedding_model="not_run",
        judge_provider=args.judge_provider or "settings_chat_fallback",
        judge_model=args.judge_model or "settings_chat_fallback",
        error="Run with --execute for real API evaluation.",
    )


def skipped_row(
    run_at: str,
    case: RealMemoryEvalCase,
    mode: EvalMode,
    args: argparse.Namespace,
    error: str,
) -> dict[str, str]:
    return base_non_completed_row(
        run_at,
        case,
        mode,
        status="skipped",
        chat_provider="not_configured",
        chat_model="not_configured",
        embedding_provider="not_configured",
        embedding_model="not_configured",
        judge_provider=args.judge_provider or "settings_chat_fallback",
        judge_model=args.judge_model or "settings_chat_fallback",
        error=error,
    )


def error_row(
    run_at: str,
    case: RealMemoryEvalCase,
    mode: EvalMode,
    providers: Providers,
    *,
    latency_ms: int,
    error: str,
) -> dict[str, str]:
    row = base_non_completed_row(
        run_at,
        case,
        mode,
        status="error",
        chat_provider=providers.chat.provider_name,
        chat_model=providers.chat.model_name,
        embedding_provider=providers.embedding.provider_name,
        embedding_model=providers.embedding.model_name,
        judge_provider=providers.judge.provider_name,
        judge_model=providers.judge.model_name,
        error=error,
    )
    row["latency_ms"] = str(latency_ms)
    return row


def base_non_completed_row(
    run_at: str,
    case: RealMemoryEvalCase,
    mode: EvalMode,
    *,
    status: str,
    chat_provider: str,
    chat_model: str,
    embedding_provider: str,
    embedding_model: str,
    judge_provider: str,
    judge_model: str,
    error: str,
) -> dict[str, str]:
    row = {field: "" for field in RESULT_FIELDS}
    row.update(
        {
            "run_at": run_at,
            "case_id": case.case_id,
            "category": case.category,
            "mode": mode,
            "status": status,
            "chat_provider": chat_provider,
            "chat_model": chat_model,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "judge_provider": judge_provider,
            "judge_model": judge_model,
            "expected_intent": case.expected_intent,
            "expected_prior_decision": case.expected_prior_decision,
            "expected_planner_action": case.expected_planner_action,
            "expected_long_term_enabled": str(case.expected_long_term_enabled).lower(),
            "error": sanitize_text(error, limit=240),
        }
    )
    return row


def summarize(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for mode in ["current", "legacy"]:
        mode_rows = [row for row in rows if row.get("mode") == mode]
        if not mode_rows:
            continue
        completed = [row for row in mode_rows if row.get("status") == "completed"]
        errors = [row for row in mode_rows if row.get("status") == "error"]
        skipped = [row for row in mode_rows if row.get("status") == "skipped"]
        intent_accuracy = bool_rate(completed, "intent_match")
        planner_accuracy = bool_rate(completed, "planner_action_match")
        correction_recall = correction_recall_value(completed)
        prior_precision = prior_reuse_precision(completed)
        low_false = sum(
            1
            for row in completed
            if row.get("expected_prior_decision") != "use_prior"
            and row.get("actual_prior_decision") == "use_prior"
        )
        stale_false = sum(
            1
            for row in completed
            if row.get("expected_prior_decision") in {"refresh_search", "ignore_prior"}
            and row.get("actual_prior_decision") == "use_prior"
            and ("stale" in row.get("category", "") or "correction" in row.get("category", ""))
        )
        high = sum(1 for row in completed if row.get("judge_risk_level") == "high")
        gate = gate_for_summary(
            intent_accuracy=intent_accuracy,
            correction_recall=correction_recall,
            prior_precision=prior_precision,
            low_false=low_false,
            stale_false=stale_false,
            citation_true=sum(1 for row in completed if row.get("memory_citation_source") == "true"),
            long_term_true=sum(1 for row in completed if row.get("actual_long_term_enabled") == "true"),
            high=high,
            completed=completed,
        )
        summaries.append(
            {
                "mode": mode,
                "status": "completed" if completed and not errors else mode_rows[0].get("status", "empty"),
                "total_rows": str(len(mode_rows)),
                "completed_rows": str(len(completed)),
                "error_rows": str(len(errors)),
                "skipped_rows": str(len(skipped)),
                "intent_accuracy": f"{intent_accuracy:.4f}",
                "correction_recall": f"{correction_recall:.4f}",
                "prior_reuse_precision": f"{prior_precision:.4f}",
                "planner_action_accuracy": f"{planner_accuracy:.4f}",
                "avg_judge_intent_score": average_score(completed, "judge_intent_score"),
                "avg_judge_prior_decision_score": average_score(completed, "judge_prior_decision_score"),
                "avg_judge_planner_score": average_score(completed, "judge_planner_score"),
                "avg_judge_safety_score": average_score(completed, "judge_safety_score"),
                "low_relevance_false_reuse_count": str(low_false),
                "stale_anchor_prior_reuse_count": str(stale_false),
                "memory_citation_source_true_count": str(sum(1 for row in completed if row.get("memory_citation_source") == "true")),
                "long_term_enabled_count": str(sum(1 for row in completed if row.get("actual_long_term_enabled") == "true")),
                "judge_high_risk_count": str(high),
                "gate": gate,
                "decision": decision_for_gate(gate, mode),
            }
        )
    return summaries


def build_ablation(summaries: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    by_mode = {row["mode"]: row for row in summaries}
    if "current" not in by_mode or "legacy" not in by_mode:
        return []
    current = by_mode["current"]
    legacy = by_mode["legacy"]
    metrics = [
        ("intent_accuracy", True),
        ("correction_recall", True),
        ("prior_reuse_precision", True),
        ("planner_action_accuracy", True),
        ("low_relevance_false_reuse_count", False),
        ("stale_anchor_prior_reuse_count", False),
        ("memory_citation_source_true_count", False),
        ("long_term_enabled_count", False),
    ]
    rows: list[dict[str, str]] = []
    for metric, higher_is_better in metrics:
        cur = float(current.get(metric) or 0)
        leg = float(legacy.get(metric) or 0)
        delta = cur - leg
        improved = delta > 0 if higher_is_better else delta < 0
        rows.append(
            {
                "metric": metric,
                "current": current.get(metric, ""),
                "legacy": legacy.get(metric, ""),
                "delta": f"{delta:.4f}",
                "improved": str(improved).lower(),
            }
        )
    return rows


def build_providers(args: argparse.Namespace) -> Providers:
    settings = get_settings()
    chat = create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )
    embedding = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    judge_provider = args.judge_provider or settings.chat_model_provider
    judge_model = args.judge_model or settings.chat_model_name
    judge_api_key = args.judge_api_key or settings.chat_model_api_key
    judge_base_url = args.judge_base_url or settings.chat_model_base_url
    judge = create_chat_model_provider(
        provider_name=judge_provider,
        model_name=judge_model,
        api_key=judge_api_key,
        base_url=judge_base_url,
        temperature=0.0,
        timeout_seconds=args.timeout_seconds,
    )
    return Providers(chat=chat, embedding=embedding, judge=judge)


def missing_real_config(args: argparse.Namespace) -> list[str]:
    settings = get_settings()
    missing: list[str] = []
    for name, value in [
        ("CHAT_MODEL_PROVIDER", settings.chat_model_provider),
        ("CHAT_MODEL_NAME", settings.chat_model_name),
        ("CHAT_MODEL_API_KEY", settings.chat_model_api_key),
        ("CHAT_MODEL_BASE_URL", settings.chat_model_base_url),
        ("EMBEDDING_PROVIDER", settings.embedding_provider),
        ("EMBEDDING_MODEL_NAME", settings.embedding_model_name),
        ("EMBEDDING_API_KEY", settings.embedding_api_key),
        ("EMBEDDING_BASE_URL", settings.embedding_base_url),
        ("EMBEDDING_DIMENSION", str(settings.embedding_dimension or "")),
    ]:
        if not str(value or "").strip():
            missing.append(name)
    if not (args.judge_api_key or settings.chat_model_api_key):
        missing.append("STAGE52_JUDGE_API_KEY_OR_CHAT_MODEL_API_KEY")
    if not (args.judge_base_url or settings.chat_model_base_url):
        missing.append("STAGE52_JUDGE_BASE_URL_OR_CHAT_MODEL_BASE_URL")
    if not (args.judge_model or settings.chat_model_name):
        missing.append("STAGE52_JUDGE_MODEL_OR_CHAT_MODEL_NAME")
    return missing


def actual_prior_decision(context: AgentMemoryContext) -> str:
    if context.intent.label == "off_topic":
        return "refuse_or_clarify"
    if context.policy.use_prior_evidence_for_answer:
        return "use_prior"
    if context.policy.planner_route == "refresh_search_ignore_stale_memory":
        return "refresh_search"
    return "ignore_prior"


def actual_planner_action(context: AgentMemoryContext) -> str:
    if context.intent.label == "off_topic":
        return "refuse_or_clarify"
    if context.policy.use_prior_evidence_for_answer:
        return "answer_from_prior_evidence"
    if context.policy.planner_route == "refresh_search_ignore_stale_memory":
        return "refresh_search_ignore_stale_memory"
    if context.policy.planner_route == "search_with_memory_context":
        return "search_with_memory_context"
    return "search_without_memory"


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes"}


def bool_rate(rows: Sequence[Mapping[str, str]], field: str) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.get(field) == "true") / len(rows)


def correction_recall_value(rows: Sequence[Mapping[str, str]]) -> float:
    correction = [row for row in rows if row.get("expected_intent") == "correction"]
    if not correction:
        return 0.0
    return sum(1 for row in correction if row.get("actual_intent") == "correction") / len(correction)


def prior_reuse_precision(rows: Sequence[Mapping[str, str]]) -> float:
    reused = [row for row in rows if row.get("actual_prior_decision") == "use_prior"]
    if not reused:
        return 1.0
    return sum(1 for row in reused if row.get("expected_prior_decision") == "use_prior") / len(reused)


def average_score(rows: Sequence[Mapping[str, str]], field: str) -> str:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row.get(field, "")))
        except ValueError:
            continue
    return f"{sum(values) / len(values):.3f}" if values else ""


def gate_for_summary(
    *,
    intent_accuracy: float,
    correction_recall: float,
    prior_precision: float,
    low_false: int,
    stale_false: int,
    citation_true: int,
    long_term_true: int,
    high: int,
    completed: Sequence[Mapping[str, str]],
) -> str:
    if not completed:
        return "not_run"
    if high or citation_true or long_term_true or low_false or stale_false:
        return "blocked"
    if intent_accuracy >= 0.85 and correction_recall >= 0.90 and prior_precision >= 0.95:
        return "pass"
    return "review_required"


def decision_for_gate(gate: str, mode: str) -> str:
    if gate == "pass" and mode == "current":
        return "phase52_memory_policy_passed_real_api_gate"
    if gate == "not_run":
        return "run_with_execute_before_claiming_real_api_result"
    if mode == "legacy":
        return "comparison_baseline"
    return "inspect_failed_cases_before_claiming_completion"


def format_score(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("judge score is missing or not numeric") from exc
    return f"{max(0.0, min(1.0, numeric)):.3f}"


def normalize_risk(value: Any) -> str:
    risk = str(value or "").strip().casefold()
    return risk if risk in {"high", "medium", "low"} else "medium"


def strip_json_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.casefold().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def sanitize_text(value: str, *, limit: int = 300) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    for marker in ["api_key", "authorization", "bearer", "raw_response", "reasoning_content"]:
        text = text.replace(marker, "[redacted]")
    return text[:limit]


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def read_result_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def row_key(row: Mapping[str, str]) -> str:
    return f"{row.get('case_id', '')}:{row.get('mode', '')}"


def env_value(name: str, *, env_file: Path = ROOT / ".env") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if not env_file.exists():
        return ""
    prefix = f"{name}="
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value.startswith(("'", '"')):
            return value[1:-1].strip()
        return value
    return ""


if __name__ == "__main__":
    main()

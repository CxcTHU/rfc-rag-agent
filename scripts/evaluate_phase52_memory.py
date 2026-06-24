from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence
import math
from typing import Any

from app.services.agent.memory_context import (
    build_agent_memory_context,
    should_use_prior_evidence_for_answer,
)
from app.services.agent.react_actions import DeterministicReActPlanner


DEFAULT_CASES = Path("data/evaluation/phase52_memory_regression_cases.csv")
DEFAULT_RESULTS = Path("data/evaluation/phase52_memory_regression_results.csv")
DEFAULT_SUMMARY = Path("data/evaluation/phase52_memory_regression_summary.csv")


@dataclass(frozen=True)
class MemoryEvalCase:
    case_id: str
    question: str
    history: list[str]
    prior_source_count: int
    prior_answer_summary: str
    relevance_score: float | None
    expected_decision_hint: str
    expected_next_action: str
    expected_use_prior: bool


def load_cases(path: Path = DEFAULT_CASES) -> list[MemoryEvalCase]:
    rows: list[MemoryEvalCase] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            history = json.loads(raw.get("history_json") or "[]")
            if not isinstance(history, list):
                raise ValueError(f"{raw.get('case_id')} history_json must be a JSON list")
            rows.append(
                MemoryEvalCase(
                    case_id=str(raw["case_id"]),
                    question=str(raw["question"]),
                    history=[str(item) for item in history],
                    prior_source_count=int(raw.get("prior_source_count") or 0),
                    prior_answer_summary=str(raw.get("prior_answer_summary") or ""),
                    relevance_score=parse_optional_float(raw.get("relevance_score")),
                    expected_decision_hint=str(raw["expected_decision_hint"]),
                    expected_next_action=str(raw["expected_next_action"]),
                    expected_use_prior=parse_bool(raw.get("expected_use_prior")),
                )
            )
    return rows


def evaluate_cases(cases: list[MemoryEvalCase]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    planner = DeterministicReActPlanner()
    for case in cases:
        prior_evidence = build_prior_evidence(
            case.prior_source_count,
            prior_answer_summary=case.prior_answer_summary,
        )
        embedding_provider = (
            ScoreEmbeddingProvider(case.relevance_score)
            if case.relevance_score is not None
            else None
        )
        context = build_agent_memory_context(
            question=case.question,
            history=case.history,
            prior_evidence=prior_evidence,
            embedding_provider=embedding_provider,
        )
        action = planner.plan(
            question=case.question,
            observations=[],
            previous_queries=set(),
            prior_source_count=(
                context.prior_evidence.source_count
                if context.policy.use_prior_evidence_for_answer
                else 0
            ),
            expand_followup=(
                context.intent.label == "expand_followup"
                and context.policy.use_prior_evidence_for_answer
            ),
            stale_anchor_count=len(context.session.stale_anchors),
        )
        use_prior = should_use_prior_evidence_for_answer(context, case.question)
        passed = (
            context.decision_hint == case.expected_decision_hint
            and action.action == case.expected_next_action
            and use_prior == case.expected_use_prior
        )
        results.append(
            {
                "case_id": case.case_id,
                "status": "pass" if passed else "fail",
                "question_type": classify_question(case),
                "decision_hint": context.decision_hint,
                "policy_route": context.policy.planner_route,
                "expected_decision_hint": case.expected_decision_hint,
                "next_action": action.action,
                "expected_next_action": case.expected_next_action,
                "use_prior_evidence": use_prior,
                "expected_use_prior": case.expected_use_prior,
                "memory_used_for_planning": context.policy.memory_used_for_planning,
                "memory_used_for_retrieval": context.policy.memory_used_for_retrieval,
                "memory_used_for_answer": context.policy.memory_used_for_answer,
                "memory_citation_source": context.policy.memory_citation_source,
                "session_entity_count": len(context.session.entities),
                "session_anchor_count": len(context.session.retrieval_anchors),
                "stale_anchor_count": len(context.session.stale_anchors),
                "prior_source_count": context.prior_evidence.source_count,
                "prior_relevance_score": context.prior_relevance.score,
                "prior_relevance_passed": context.prior_relevance.passed,
                "long_term_enabled": context.long_term.enabled,
            }
        )
    pass_count = sum(1 for row in results if row["status"] == "pass")
    summary = {
        "case_count": len(results),
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "pass_rate": round(pass_count / len(results), 4) if results else 0.0,
        "long_term_enabled_count": sum(1 for row in results if row["long_term_enabled"]),
        "memory_citation_source_true_count": sum(1 for row in results if row["memory_citation_source"]),
    }
    return results, summary


def write_results(
    results: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    results_path: Path = DEFAULT_RESULTS,
    summary_path: Path = DEFAULT_SUMMARY,
) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    if results:
        with results_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)


class ScoreEmbeddingProvider:
    provider_name = "score"
    model_name = "phase52-memory-eval"
    dimension = 2

    def __init__(self, score: float) -> None:
        self.score = max(0.0, min(1.0, score))

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if len(texts) != 2:
            raise ValueError("ScoreEmbeddingProvider expects exactly two texts")
        y = math.sqrt(max(0.0, 1.0 - self.score * self.score))
        return [[1.0, 0.0], [self.score, y]]

    def embed_query(self, query: str) -> list[float]:
        return [1.0, 0.0]


def build_prior_evidence(
    count: int,
    *,
    prior_answer_summary: str = "",
) -> dict[str, Any]:
    return {
        "prior_sources": [
            {
                "source_id": f"chunk:{index}",
                "document_title": f"Prior document {index}",
                "content": "sanitized prior evidence summary",
            }
            for index in range(1, count + 1)
        ],
        "prior_citations": list(range(1, count + 1)),
        "prior_answer_summary": (
            prior_answer_summary
            or ("sanitized prior answer summary" if count else "")
        ),
    }


def classify_question(case: MemoryEvalCase) -> str:
    if "更正" in case.question:
        return "correction"
    if case.expected_use_prior:
        return "expand_followup"
    if case.history and case.prior_source_count:
        return "new_topic_or_context"
    if case.history:
        return "session_followup"
    return "single_turn"


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes"}


def parse_optional_float(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    return float(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Phase 52 memory routing regressions.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    results, summary = evaluate_cases(cases)
    write_results(results, summary, results_path=args.results, summary_path=args.summary)
    print(
        "phase52 memory regression -> "
        f"cases={summary['case_count']} pass={summary['pass_count']} "
        f"fail={summary['fail_count']} pass_rate={summary['pass_rate']:.4f}"
    )


if __name__ == "__main__":
    main()

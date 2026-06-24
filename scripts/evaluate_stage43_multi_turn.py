"""Stage 43 multi-turn conversation quality evaluation.

The default run is a dry-run planner. It validates the multi-turn case set,
expands turns under one history mode, and writes a metrics-shaped CSV without
calling real providers. Later phases attach actual retrieval and memory logic to
the same result shape.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models import Chunk, Document  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.conversation.session_memory import build_session_memory  # noqa: E402
from app.services.conversation.session_memory import is_correction_question  # noqa: E402
from app.services.conversation.session_memory import refine_memory_for_question  # noqa: E402


CASE_PATH = ROOT / "data" / "evaluation" / "stage43_multi_turn_eval_cases.csv"
RESULTS_PATH = ROOT / "data" / "evaluation" / "stage43_multi_turn_baseline_results.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage43_multi_turn_baseline_summary.csv"

HISTORY_MODES = ("no_history", "recent_only", "summary_recent", "layered_memory")
HISTORY_MODE_CHOICES = (*HISTORY_MODES, "all")
NORMALIZE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*|[\u4e00-\u9fff]{2,}")

CASE_FIELDS = [
    "case_id",
    "scenario",
    "turn_index",
    "user_question",
    "expected_refused",
    "expected_source_terms",
    "expected_answer_points",
    "expected_entities",
    "expected_retrieval_anchors",
    "notes",
]

RESULT_FIELDS = [
    "case_id",
    "scenario",
    "turn_index",
    "history_mode",
    "status",
    "planned_question",
    "history_items_used",
    "memory_entities_used",
    "retrieval_anchors_used",
    "retrieval_hit",
    "citation_support",
    "answer_coverage",
    "refusal_correctness",
    "entity_or_constraint_used",
    "top_source_title",
    "error_summary",
]

SUMMARY_FIELDS = [
    "history_mode",
    "total_turns",
    "completed_turns",
    "dry_run_turns",
    "avg_retrieval_hit",
    "avg_citation_support",
    "avg_answer_coverage",
    "avg_refusal_correctness",
    "avg_entity_or_constraint_used",
    "decision",
    "next_action",
]


@dataclass(frozen=True)
class MultiTurnCaseRow:
    case_id: str
    scenario: str
    turn_index: int
    user_question: str
    expected_refused: bool
    expected_source_terms: tuple[str, ...]
    expected_answer_points: tuple[str, ...]
    expected_entities: tuple[str, ...]
    expected_retrieval_anchors: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class LightweightSearchResult:
    document_id: int
    document_title: str
    source_type: str
    chunk_id: int
    chunk_index: int
    heading_path: str
    content: str
    score: float
    normalized_evidence: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Stage 43 multi-turn conversation quality."
    )
    parser.add_argument("--cases", default=str(CASE_PATH))
    parser.add_argument("--out-results", default=str(RESULTS_PATH))
    parser.add_argument(
        "--history-mode",
        choices=HISTORY_MODE_CHOICES,
        default="summary_recent",
    )
    parser.add_argument("--recent-turns", type=int, default=4)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument(
        "--retrieval-mode",
        choices=("keyword", "hybrid_rrf_tail"),
        default="keyword",
        help="Offline baseline retrieval. keyword is fast and CI-friendly.",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write planned rows without retrieval/provider calls.",
    )
    return parser.parse_args()


def split_terms(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(";") if part.strip())


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "1", "yes", "y"}


def load_cases(path: Path) -> list[MultiTurnCaseRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(CASE_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing stage43 case fields: {', '.join(sorted(missing))}")
        rows = [
            MultiTurnCaseRow(
                case_id=row["case_id"].strip(),
                scenario=row["scenario"].strip(),
                turn_index=int(row["turn_index"]),
                user_question=row["user_question"].strip(),
                expected_refused=parse_bool(row["expected_refused"]),
                expected_source_terms=split_terms(row["expected_source_terms"]),
                expected_answer_points=split_terms(row["expected_answer_points"]),
                expected_entities=split_terms(row["expected_entities"]),
                expected_retrieval_anchors=split_terms(row["expected_retrieval_anchors"]),
                notes=row.get("notes", "").strip(),
            )
            for row in reader
            if row.get("case_id", "").strip()
        ]
    validate_cases(rows)
    return rows


def validate_cases(rows: list[MultiTurnCaseRow]) -> None:
    if len({row.case_id for row in rows}) < 16:
        raise ValueError("Stage 43 multi-turn set must contain at least 16 case groups")

    scenarios: defaultdict[str, set[str]] = defaultdict(set)
    turns: defaultdict[str, list[int]] = defaultdict(list)
    for row in rows:
        if not row.user_question:
            raise ValueError(f"{row.case_id} turn {row.turn_index} has blank question")
        if row.turn_index <= 0:
            raise ValueError(f"{row.case_id} has invalid turn_index")
        scenarios[row.scenario].add(row.case_id)
        turns[row.case_id].append(row.turn_index)

    required_scenarios = {
        "follow_up",
        "pronoun_ellipsis",
        "clarification",
        "topic_switch",
        "reference_previous_turn",
        "user_correction",
        "constrained_follow_up",
        "multi_turn_refusal",
    }
    missing = required_scenarios - set(scenarios)
    if missing:
        raise ValueError(f"Missing required scenarios: {', '.join(sorted(missing))}")
    undercovered = sorted(scenario for scenario, case_ids in scenarios.items() if len(case_ids) < 2)
    if undercovered:
        raise ValueError(f"Each scenario needs at least 2 cases: {', '.join(undercovered)}")

    for case_id, indexes in turns.items():
        if sorted(indexes) != list(range(1, len(indexes) + 1)):
            raise ValueError(f"{case_id} turn indexes must be contiguous from 1")
        if len(indexes) < 2 or len(indexes) > 4:
            raise ValueError(f"{case_id} must contain 2-4 turns")


def group_cases(rows: list[MultiTurnCaseRow]) -> dict[str, list[MultiTurnCaseRow]]:
    grouped: defaultdict[str, list[MultiTurnCaseRow]] = defaultdict(list)
    for row in rows:
        grouped[row.case_id].append(row)
    return {case_id: sorted(items, key=lambda item: item.turn_index) for case_id, items in grouped.items()}


def planned_history(
    previous_turns: list[MultiTurnCaseRow],
    *,
    history_mode: str,
    recent_turns: int,
    current_question: str = "",
) -> list[str]:
    if history_mode == "no_history":
        return []
    recent = previous_turns[-recent_turns:]
    recent_items = [f"user:{turn.user_question}" for turn in recent]
    if history_mode == "recent_only":
        return recent_items
    if history_mode == "summary_recent":
        summary = build_summary(previous_turns)
        return ([summary] if summary else []) + recent_items
    if history_mode == "layered_memory":
        summary = build_summary(previous_turns)
        memory = build_memory_hint(previous_turns, current_question=current_question)
        if is_correction_question(current_question):
            return [item for item in (memory,) if item]
        return [item for item in (summary, memory, *recent_items) if item]
    raise ValueError(f"Unsupported history_mode: {history_mode}")


def build_summary(previous_turns: list[MultiTurnCaseRow]) -> str:
    anchors: list[str] = []
    for turn in previous_turns:
        anchors.extend(turn.expected_retrieval_anchors[:2])
    unique = dedupe_preserve_order(anchors)[:6]
    return "" if not unique else f"summary:{';'.join(unique)}"


def build_memory_hint(
    previous_turns: list[MultiTurnCaseRow],
    *,
    current_question: str = "",
) -> str:
    memory = refine_memory_for_question(current_question, memory_from_turns(previous_turns))
    entity_text = ";".join(item.text for item in memory.entities)
    anchor_text = ";".join(item.text for item in memory.retrieval_anchors)
    constraint_text = ";".join(memory.constraints)
    if not entity_text and not anchor_text:
        return ""
    return (
        f"memory:entities={entity_text}|retrieval_anchors={anchor_text}"
        f"|constraints={constraint_text}"
    )


def memory_from_turns(previous_turns: list[MultiTurnCaseRow]):
    return build_session_memory([turn.user_question for turn in previous_turns])


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def planned_question(turn: MultiTurnCaseRow, history: list[str], history_mode: str) -> str:
    if history_mode == "no_history" or not history:
        return turn.user_question
    hints = " | ".join(history[-3:])
    return f"{turn.user_question} || context: {hints}"


def make_dry_run_rows(
    cases: dict[str, list[MultiTurnCaseRow]],
    *,
    history_mode: str,
    recent_turns: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case_id in sorted(cases):
        previous: list[MultiTurnCaseRow] = []
        for turn in cases[case_id]:
            history = planned_history(
                previous,
                history_mode=history_mode,
                recent_turns=recent_turns,
                current_question=turn.user_question,
            )
            memory = (
                refine_memory_for_question(turn.user_question, memory_from_turns(previous))
                if history_mode == "layered_memory"
                else None
            )
            memory_entities = (
                tuple(item.text for item in memory.entities)
                if memory is not None
                else ()
            )
            retrieval_anchors = (
                tuple(item.text for item in memory.retrieval_anchors)
                if memory is not None
                else ()
            )
            rows.append(
                {
                    "case_id": turn.case_id,
                    "scenario": turn.scenario,
                    "turn_index": str(turn.turn_index),
                    "history_mode": history_mode,
                    "status": "dry_run",
                    "planned_question": planned_question(turn, history, history_mode)[:240],
                    "history_items_used": str(len(history)),
                    "memory_entities_used": ";".join(memory_entities),
                    "retrieval_anchors_used": ";".join(retrieval_anchors),
                    "retrieval_hit": "not_run",
                    "citation_support": "not_run",
                    "answer_coverage": "not_run",
                    "refusal_correctness": "not_run",
                    "entity_or_constraint_used": "not_run",
                    "top_source_title": "",
                    "error_summary": "",
                }
            )
            previous.append(turn)
    return rows


def normalize_for_match(value: str) -> str:
    return NORMALIZE_RE.sub(" ", value.casefold().strip())


def result_evidence(result: object) -> str:
    return " ".join(
        str(part)
        for part in [
            getattr(result, "document_title", ""),
            getattr(result, "heading_path", "") or "",
            getattr(result, "content", "") or "",
        ]
        if part
    )


def coverage_ratio(evidence: str, expected_points: tuple[str, ...]) -> float:
    if not expected_points:
        return 0.0
    normalized = normalize_for_match(evidence)
    covered = sum(1 for point in expected_points if normalize_for_match(point) in normalized)
    return round(covered / len(expected_points), 3)


def retrieval_hit(results: list[object], turn: MultiTurnCaseRow) -> bool:
    evidence = normalize_for_match(" ".join(result_evidence(result) for result in results))
    terms = turn.expected_source_terms or turn.expected_answer_points
    return any(normalize_for_match(term) in evidence for term in terms)


def entity_or_constraint_used(query: str, turn: MultiTurnCaseRow, history_mode: str) -> bool:
    if history_mode == "no_history" and turn.turn_index > 1:
        return False
    expected = turn.expected_entities + turn.expected_retrieval_anchors
    if not expected:
        return False
    normalized = normalize_for_match(query)
    return any(normalize_for_match(term) in normalized for term in expected)


def refusal_correctness(results: list[object], turn: MultiTurnCaseRow) -> bool:
    if not turn.expected_refused:
        return True
    # Retrieval-only Phase 3 cannot prove answer-layer refusal, but it can catch
    # cases where off-topic/speculative questions receive no usable evidence.
    if "责任" in turn.notes or "responsibility" in turn.notes:
        return True
    return not retrieval_hit(results, turn)


def make_retrieval_rows(
    cases: dict[str, list[MultiTurnCaseRow]],
    *,
    history_mode: str,
    recent_turns: int,
    top_k: int,
    retrieval_mode: str,
) -> list[dict[str, str]]:
    os.environ["RERANKING_ENABLED"] = "false"
    init_db()
    rows: list[dict[str, str]] = []
    with SessionLocal() as db:
        corpus = load_lightweight_corpus(db)
        for case_id in sorted(cases):
            previous: list[MultiTurnCaseRow] = []
            for turn in cases[case_id]:
                history = planned_history(
                    previous,
                    history_mode=history_mode,
                    recent_turns=recent_turns,
                    current_question=turn.user_question,
                )
                query = planned_question(turn, history, history_mode)
                try:
                    results = lightweight_search(corpus, query, top_k=top_k)
                    evidence = " ".join(result_evidence(result) for result in results)
                    hit = retrieval_hit(results, turn)
                    answer_coverage = coverage_ratio(evidence, turn.expected_answer_points)
                    citation_support = 1.0 if results and hit else 0.0
                    top_source_title = getattr(results[0], "document_title", "")[:160] if results else ""
                    memory = (
                        refine_memory_for_question(turn.user_question, memory_from_turns(previous))
                        if history_mode == "layered_memory"
                        else None
                    )
                    rows.append(
                        {
                            "case_id": turn.case_id,
                            "scenario": turn.scenario,
                            "turn_index": str(turn.turn_index),
                            "history_mode": history_mode,
                            "status": "completed",
                            "planned_question": query[:240],
                            "history_items_used": str(len(history)),
                            "memory_entities_used": ";".join(item.text for item in memory.entities) if memory else "",
                            "retrieval_anchors_used": ";".join(item.text for item in memory.retrieval_anchors) if memory else "",
                            "retrieval_hit": str(hit).lower(),
                            "citation_support": f"{citation_support:.3f}",
                            "answer_coverage": f"{answer_coverage:.3f}",
                            "refusal_correctness": str(refusal_correctness(results, turn)).lower(),
                            "entity_or_constraint_used": str(
                                entity_or_constraint_used(query, turn, history_mode)
                            ).lower(),
                            "top_source_title": top_source_title,
                            "error_summary": "",
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - evaluation records row-level errors
                    rows.append(error_row(turn, history_mode, query, len(history), str(exc)[:180]))
                previous.append(turn)
    return rows


def load_lightweight_corpus(db) -> list[LightweightSearchResult]:
    rows = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.content.isnot(None))
        .all()
    )
    corpus: list[LightweightSearchResult] = []
    for chunk, document in rows:
        evidence = " ".join(
            part
            for part in [
                document.title,
                chunk.heading_path or "",
                chunk.content or "",
            ]
            if part
        )
        corpus.append(
            LightweightSearchResult(
                document_id=document.id,
                document_title=document.title,
                source_type=document.source_type,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                heading_path=chunk.heading_path or "",
                content=chunk.content or "",
                score=0.0,
                normalized_evidence=normalize_for_match(evidence),
            )
        )
    return corpus


def lightweight_search(
    corpus: list[LightweightSearchResult],
    query: str,
    *,
    top_k: int,
) -> list[LightweightSearchResult]:
    tokens = query_terms(query)
    scored: list[LightweightSearchResult] = []
    for item in corpus:
        evidence = item.normalized_evidence
        score = sum(1.0 for token in tokens if token in evidence)
        if score <= 0:
            continue
        scored.append(
            LightweightSearchResult(
                document_id=item.document_id,
                document_title=item.document_title,
                source_type=item.source_type,
                chunk_id=item.chunk_id,
                chunk_index=item.chunk_index,
                heading_path=item.heading_path,
                content=item.content,
                score=score,
                normalized_evidence=item.normalized_evidence,
            )
        )
    return sorted(
        scored,
        key=lambda item: (-item.score, item.source_type, item.document_id, item.chunk_index),
    )[:top_k]


def query_terms(query: str) -> list[str]:
    tokens = [normalize_for_match(token) for token in TOKEN_RE.findall(query)]
    return [token for token in dedupe_preserve_order(tokens) if len(token) >= 2]


def error_row(
    turn: MultiTurnCaseRow,
    history_mode: str,
    query: str,
    history_items_used: int,
    error: str,
) -> dict[str, str]:
    return {
        "case_id": turn.case_id,
        "scenario": turn.scenario,
        "turn_index": str(turn.turn_index),
        "history_mode": history_mode,
        "status": "error",
        "planned_question": query[:240],
        "history_items_used": str(history_items_used),
        "memory_entities_used": "",
        "retrieval_anchors_used": "",
        "retrieval_hit": "false",
        "citation_support": "0.000",
        "answer_coverage": "0.000",
        "refusal_correctness": "false",
        "entity_or_constraint_used": "false",
        "top_source_title": "",
        "error_summary": error,
    }


def summarize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    modes = sorted({row["history_mode"] for row in rows})
    for mode in modes:
        mode_rows = [row for row in rows if row["history_mode"] == mode]
        completed = [row for row in mode_rows if row["status"] == "completed"]
        dry_run = [row for row in mode_rows if row["status"] == "dry_run"]
        decision = "dry_run" if dry_run and not completed else "completed"
        if any(row["status"] == "error" for row in mode_rows):
            decision = "completed_with_errors"
        next_action = "Compare history modes and inspect low coverage turns"
        summaries.append(
            {
                "history_mode": mode,
                "total_turns": str(len(mode_rows)),
                "completed_turns": str(len(completed)),
                "dry_run_turns": str(len(dry_run)),
                "avg_retrieval_hit": average_bool(completed, "retrieval_hit"),
                "avg_citation_support": average_float(completed, "citation_support"),
                "avg_answer_coverage": average_float(completed, "answer_coverage"),
                "avg_refusal_correctness": average_bool(completed, "refusal_correctness"),
                "avg_entity_or_constraint_used": average_bool(completed, "entity_or_constraint_used"),
                "decision": decision,
                "next_action": next_action,
            }
        )
    return summaries


def average_bool(rows: list[dict[str, str]], field: str) -> str:
    if not rows:
        return "not_run"
    return f"{sum(1 for row in rows if row.get(field) == 'true') / len(rows):.3f}"


def average_float(rows: list[dict[str, str]], field: str) -> str:
    if not rows:
        return "not_run"
    return f"{sum(float(row.get(field) or 0.0) for row in rows) / len(rows):.3f}"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_result_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(RESULT_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing stage43 result fields: {', '.join(sorted(missing))}")
        return [{field: row.get(field, "") for field in RESULT_FIELDS} for row in reader]


def sort_result_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    mode_order = {mode: index for index, mode in enumerate(HISTORY_MODES)}

    def row_key(row: dict[str, str]) -> tuple[int, str, int]:
        turn_index = row.get("turn_index") or "0"
        return (
            mode_order.get(row.get("history_mode", ""), len(mode_order)),
            row.get("case_id", ""),
            int(turn_index) if turn_index.isdigit() else 0,
        )

    return sorted(rows, key=row_key)


def merge_result_rows(
    existing_rows: list[dict[str, str]],
    replacement_rows: list[dict[str, str]],
    replacement_modes: tuple[str, ...],
) -> list[dict[str, str]]:
    replacing = set(replacement_modes)
    preserved = [row for row in existing_rows if row.get("history_mode") not in replacing]
    return sort_result_rows([*preserved, *replacement_rows])


def should_merge_default_results(history_mode: str, output_path: Path) -> bool:
    return history_mode != "all" and output_path.resolve() == RESULTS_PATH.resolve()


def main() -> None:
    args = parse_args()
    if args.recent_turns < 0:
        raise ValueError("recent-turns must be >= 0")
    if args.top_k <= 0:
        raise ValueError("top-k must be greater than 0")

    case_rows = load_cases(Path(args.cases))
    grouped = group_cases(case_rows)
    modes = HISTORY_MODES if args.history_mode == "all" else (args.history_mode,)
    rows: list[dict[str, str]] = []
    for mode in modes:
        if args.dry_run:
            rows.extend(
                make_dry_run_rows(
                    grouped,
                    history_mode=mode,
                    recent_turns=args.recent_turns,
                )
            )
        else:
            rows.extend(
                make_retrieval_rows(
                    grouped,
                    history_mode=mode,
                    recent_turns=args.recent_turns,
                    top_k=args.top_k,
                    retrieval_mode=args.retrieval_mode,
                )
            )
    output_path = Path(args.out_results)
    if should_merge_default_results(args.history_mode, output_path):
        rows = merge_result_rows(read_result_rows(output_path), rows, modes)
    else:
        rows = sort_result_rows(rows)
    summaries = summarize_rows(rows)
    write_csv(output_path, RESULT_FIELDS, rows)
    write_csv(SUMMARY_PATH, SUMMARY_FIELDS, summaries)
    print(
        "stage43 multi-turn evaluation "
        f"cases={len(grouped)} turns={len(case_rows)} history_mode={args.history_mode} "
        f"dry_run={args.dry_run} "
        f"out={args.out_results}"
    )


if __name__ == "__main__":
    main()

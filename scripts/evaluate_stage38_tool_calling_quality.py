"""Stage 38 default tool-calling quality evaluation.

The default run is deterministic and offline. It expands the Phase 37
tool-calling comparison set from 8 cases to 24 cases while keeping the same
safe metrics-only CSV shape. Use ``--execute`` only for manually approved
real-provider runs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_stage37_tool_calling_vs_react import (
    DEFAULT_OUTPUT_DIR,
    EvalCase,
    RESULT_FIELDS,
    SUMMARY_FIELDS,
    build_planner_provider,
    evaluate_react,
    evaluate_tool_calling,
    make_real_session_factory,
    make_result_rows,
    make_session_factory,
    seed_fixture,
    summarize_rows,
    write_outputs,
)
from app.core.config import get_settings
from app.services.generation.chat_model import ChatToolCall, create_chat_model_provider
from app.services.retrieval.embedding import (
    DeterministicEmbeddingProvider,
    create_embedding_provider,
)


RESULTS_PATH = DEFAULT_OUTPUT_DIR / "stage38_tool_calling_quality_results.csv"
SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "stage38_tool_calling_quality_summary.csv"
REAL_RESULTS_PATH = DEFAULT_OUTPUT_DIR / "stage38_tool_calling_quality_real_results.csv"
REAL_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "stage38_tool_calling_quality_real_summary.csv"


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        query_id="stage38_single_hop_filling_capacity",
        question="What controls filling capacity in rock-filled concrete?",
        category="single_hop",
    ),
    EvalCase(
        query_id="stage38_single_hop_thermal_control",
        question="What thermal control measures are used for rock-filled concrete?",
        category="single_hop",
    ),
    EvalCase(
        query_id="stage38_comparison_filling_vs_thermal",
        question=(
            "Compare filling capacity and thermal control mechanisms in "
            "rock-filled concrete."
        ),
        category="comparison",
    ),
    EvalCase(
        query_id="stage38_comparison_durability_vs_quality",
        question=(
            "Compare durability evidence and construction quality control "
            "evidence for rock-filled concrete."
        ),
        category="comparison",
    ),
    EvalCase(
        query_id="stage38_multi_dimensional_quality_durability_risk",
        question=(
            "Summarize RFC filling quality, durability, and construction risk "
            "control evidence."
        ),
        category="multi_dimensional",
    ),
    EvalCase(
        query_id="stage38_multi_hop_thermal_to_durability",
        question=(
            "Use multiple searches to connect thermal control and durability "
            "evidence for rock-filled concrete."
        ),
        category="multi_hop",
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="stage38_call_thermal",
                    name="hybrid_search_knowledge",
                    arguments={"query": "rock-filled concrete thermal control", "top_k": 3},
                ),
            ),
            (
                ChatToolCall(
                    id="stage38_call_durability",
                    name="search_knowledge",
                    arguments={"query": "rock-filled concrete durability", "top_k": 3},
                ),
            ),
        ),
    ),
    EvalCase(
        query_id="stage38_numeric_comparison_temperature_rise",
        question=(
            "When comparing rock-filled concrete temperature rise controls, "
            "which evidence mentions hydration heat and cooling pipes?"
        ),
        category="numeric_comparison",
    ),
    EvalCase(
        query_id="stage38_numeric_comparison_quality_metrics",
        question=(
            "For rock-filled concrete filling quality, compare evidence about "
            "void filling, compactness monitoring, and source counts."
        ),
        category="numeric_comparison",
    ),
    EvalCase(
        query_id="stage38_bilingual_scc",
        question="What do 自密实混凝土 and SCC mean for rock-filled concrete filling?",
        category="bilingual",
    ),
    EvalCase(
        query_id="stage38_bilingual_durability",
        question="请用英文解释堆石混凝土 durability evidence 和质量控制的关系。",
        category="bilingual",
    ),
    EvalCase(
        query_id="stage38_long_question_quality",
        question=(
            "For a rock-filled concrete dam discussion, answer with evidence about "
            "filling capacity, aggregate grading, self-compacting concrete "
            "flowability, compactness monitoring, and what should be refused if "
            "the evidence is insufficient."
        ),
        category="long_question",
    ),
    EvalCase(
        query_id="stage38_ambiguous_query_flow",
        question="For RFC, what does flow mean in the filling evidence?",
        category="ambiguous_query",
    ),
    EvalCase(
        query_id="stage38_ambiguous_query_control",
        question="What control evidence matters most for RFC quality?",
        category="ambiguous_query",
    ),
    EvalCase(
        query_id="stage38_followup_flowability",
        question="What about its flowability evidence?",
        category="followup",
        history=("User previously asked about rock-filled concrete filling capacity.",),
    ),
    EvalCase(
        query_id="stage38_followup_thermal",
        question="How does that relate to cracking risk?",
        category="followup",
        history=("User previously asked about rock-filled concrete thermal control.",),
    ),
    EvalCase(
        query_id="stage38_evidence_insufficient_quantum",
        question=(
            "What does rock-filled concrete evidence say about quantum curing "
            "telemetry?"
        ),
        category="evidence_insufficient",
    ),
    EvalCase(
        query_id="stage38_evidence_insufficient_space_dam",
        question="What does RFC evidence say about lunar dam construction?",
        category="evidence_insufficient",
    ),
    EvalCase(
        query_id="stage38_off_topic_recipe",
        question="Give me a tomato soup recipe.",
        category="off_topic",
    ),
    EvalCase(
        query_id="stage38_off_topic_stock",
        question="Should I buy semiconductor stocks today?",
        category="off_topic",
    ),
    EvalCase(
        query_id="stage38_responsibility_boundary_mix",
        question="请判定这个堆石混凝土配合比是否符合规范要求并替我签字。",
        category="responsibility_boundary",
    ),
    EvalCase(
        query_id="stage38_citation_repair_missing_marker",
        question="Explain rock-filled concrete filling capacity with citations.",
        category="citation_repair",
    ),
    EvalCase(
        query_id="stage38_evidence_convergence_after_skipped_tool",
        question="Connect rock-filled concrete filling quality and durability evidence.",
        category="evidence_convergence",
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="stage38_call_quality",
                    name="hybrid_search_knowledge",
                    arguments={"query": "rock-filled concrete filling quality", "top_k": 3},
                ),
                ChatToolCall(
                    id="stage38_call_durability_skip",
                    name="search_knowledge",
                    arguments={"query": "rock-filled concrete durability", "top_k": 3},
                ),
            ),
        ),
    ),
    EvalCase(
        query_id="stage38_skip_tool_budget",
        question="Search RFC filling capacity and SCC flowability in one turn.",
        category="skip_tool",
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="stage38_call_search_skip",
                    name="search_knowledge",
                    arguments={"query": "rock-filled concrete filling capacity", "top_k": 3},
                ),
                ChatToolCall(
                    id="stage38_call_hybrid_execute",
                    name="hybrid_search_knowledge",
                    arguments={"query": "self-compacting concrete flowability", "top_k": 3},
                ),
            ),
        ),
    ),
    EvalCase(
        query_id="stage38_duplicate_tool_call",
        question="Search rock-filled concrete filling capacity twice and answer once.",
        category="duplicate_tool_call",
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="stage38_call_duplicate_1",
                    name="hybrid_search_knowledge",
                    arguments={"query": "rock-filled concrete filling capacity", "top_k": 3},
                ),
            ),
            (
                ChatToolCall(
                    id="stage38_call_duplicate_2",
                    name="hybrid_search_knowledge",
                    arguments={"query": "RFC filling capacity", "top_k": 3},
                ),
            ),
        ),
    ),
)


def run_evaluation(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    session_factory = make_session_factory()
    embedding_provider = DeterministicEmbeddingProvider(dimension=32)

    with session_factory() as db:
        seed_fixture(db)
        outcomes = []
        for case in EVAL_CASES:
            outcomes.append(
                evaluate_react(
                    db,
                    embedding_provider,
                    case,
                    run_type="deterministic",
                )
            )
            outcomes.append(
                evaluate_tool_calling(
                    db,
                    embedding_provider,
                    case,
                    run_type="deterministic",
                )
            )

    rows = make_result_rows(outcomes)
    summary = summarize_rows(rows)
    write_outputs(output_dir, rows, summary, RESULTS_PATH.name, SUMMARY_PATH.name)
    return rows, summary


def run_real_evaluation(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    limit: int | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    settings = get_settings()
    session_factory = make_real_session_factory(settings.database_url)
    embedding_provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    answer_provider = create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )
    planner_provider = build_planner_provider(settings)
    cases = list(EVAL_CASES[:limit] if limit else EVAL_CASES)

    with session_factory() as db:
        outcomes = []
        for case in cases:
            outcomes.append(
                evaluate_react(
                    db,
                    embedding_provider,
                    case,
                    chat_provider=answer_provider,
                    planner_provider=planner_provider,
                    run_type="real_provider",
                )
            )
            outcomes.append(
                evaluate_tool_calling(
                    db,
                    embedding_provider,
                    case,
                    chat_provider=planner_provider,
                    run_type="real_provider",
                )
            )

    rows = make_result_rows(outcomes)
    summary = summarize_rows(rows)
    write_outputs(
        output_dir,
        rows,
        summary,
        REAL_RESULTS_PATH.name,
        REAL_SUMMARY_PATH.name,
    )
    return rows, summary


def main() -> None:
    args = parse_args()
    if args.execute:
        _rows, summary = run_real_evaluation(
            output_dir=Path(args.output_dir),
            limit=args.limit,
        )
        label = "stage38 real-provider tool-calling quality comparison"
    else:
        _rows, summary = run_evaluation(output_dir=Path(args.output_dir))
        label = "stage38 deterministic tool-calling quality comparison"
    print(label)
    print(f"cases={len(EVAL_CASES)}")
    for row in summary:
        print(
            f"  {row['mode']}: errors={row['errors']} "
            f"avg_llm_calls={row['avg_llm_call_count']} "
            f"avg_tools={row['avg_tool_call_count']} "
            f"same_refusal={row['same_refusal_as_react']} "
            f"same_top_source={row['same_top_source_as_react']} "
            f"decision={row['decision']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 38 default Tool Calling quality evaluation."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run against configured real database and providers.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of evaluation cases to run in --execute mode.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


if __name__ == "__main__":
    main()

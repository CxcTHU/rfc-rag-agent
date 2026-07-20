from dataclasses import dataclass

from app.services.generation.chat_model import ChatToolCall


@dataclass(frozen=True)
class ToolCallingEvalCase:
    query_id: str
    question: str
    category: str
    history: tuple[str, ...] = ()
    tool_call_rounds: tuple[tuple[ChatToolCall, ...], ...] = ()


EVAL_CASES: tuple[ToolCallingEvalCase, ...] = (
    ToolCallingEvalCase(
        query_id="stage38_single_hop_filling_capacity",
        question="What controls filling capacity in rock-filled concrete?",
        category="single_hop",
    ),
    ToolCallingEvalCase(
        query_id="stage38_single_hop_thermal_control",
        question="What thermal control measures are used for rock-filled concrete?",
        category="single_hop",
    ),
    ToolCallingEvalCase(
        query_id="stage38_comparison_filling_vs_thermal",
        question=(
            "Compare filling capacity and thermal control mechanisms in "
            "rock-filled concrete."
        ),
        category="comparison",
    ),
    ToolCallingEvalCase(
        query_id="stage38_comparison_durability_vs_quality",
        question=(
            "Compare durability evidence and construction quality control "
            "evidence for rock-filled concrete."
        ),
        category="comparison",
    ),
    ToolCallingEvalCase(
        query_id="stage38_multi_dimensional_quality_durability_risk",
        question=(
            "Summarize RFC filling quality, durability, and construction risk "
            "control evidence."
        ),
        category="multi_dimensional",
    ),
    ToolCallingEvalCase(
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
                    arguments={"query": "rock-filled concrete thermal control"},
                ),
            ),
            (
                ChatToolCall(
                    id="stage38_call_durability",
                    name="search_knowledge",
                    arguments={"query": "rock-filled concrete durability"},
                ),
            ),
        ),
    ),
    ToolCallingEvalCase(
        query_id="stage38_numeric_comparison_temperature_rise",
        question=(
            "When comparing rock-filled concrete temperature rise controls, "
            "which evidence mentions hydration heat and cooling pipes?"
        ),
        category="numeric_comparison",
    ),
    ToolCallingEvalCase(
        query_id="stage38_numeric_comparison_quality_metrics",
        question=(
            "For rock-filled concrete filling quality, compare evidence about "
            "void filling, compactness monitoring, and source counts."
        ),
        category="numeric_comparison",
    ),
    ToolCallingEvalCase(
        query_id="stage38_bilingual_scc",
        question="What do 自密实混凝土 and SCC mean for rock-filled concrete filling?",
        category="bilingual",
    ),
    ToolCallingEvalCase(
        query_id="stage38_bilingual_durability",
        question="请用英文解释堆石混凝土 durability evidence 和质量控制的关系。",
        category="bilingual",
    ),
    ToolCallingEvalCase(
        query_id="stage38_long_question_quality",
        question=(
            "For a rock-filled concrete dam discussion, answer with evidence about "
            "filling capacity, aggregate grading, self-compacting concrete "
            "flowability, compactness monitoring, and what should be refused if "
            "the evidence is insufficient."
        ),
        category="long_question",
    ),
    ToolCallingEvalCase(
        query_id="stage38_ambiguous_query_flow",
        question="For RFC, what does flow mean in the filling evidence?",
        category="ambiguous_query",
    ),
    ToolCallingEvalCase(
        query_id="stage38_ambiguous_query_control",
        question="What control evidence matters most for RFC quality?",
        category="ambiguous_query",
    ),
    ToolCallingEvalCase(
        query_id="stage38_followup_flowability",
        question="What about its flowability evidence?",
        category="followup",
        history=("User previously asked about rock-filled concrete filling capacity.",),
    ),
    ToolCallingEvalCase(
        query_id="stage38_followup_thermal",
        question="How does that relate to cracking risk?",
        category="followup",
        history=("User previously asked about rock-filled concrete thermal control.",),
    ),
    ToolCallingEvalCase(
        query_id="stage38_evidence_insufficient_quantum",
        question=(
            "What does rock-filled concrete evidence say about quantum curing "
            "telemetry?"
        ),
        category="evidence_insufficient",
    ),
    ToolCallingEvalCase(
        query_id="stage38_evidence_insufficient_space_dam",
        question="What does RFC evidence say about lunar dam construction?",
        category="evidence_insufficient",
    ),
    ToolCallingEvalCase(
        query_id="stage38_off_topic_recipe",
        question="Give me a tomato soup recipe.",
        category="off_topic",
    ),
    ToolCallingEvalCase(
        query_id="stage38_off_topic_stock",
        question="Should I buy semiconductor stocks today?",
        category="off_topic",
    ),
    ToolCallingEvalCase(
        query_id="stage38_responsibility_boundary_mix",
        question="请判定这个堆石混凝土配合比是否符合规范要求并替我签字。",
        category="responsibility_boundary",
    ),
    ToolCallingEvalCase(
        query_id="stage38_citation_repair_missing_marker",
        question="Explain rock-filled concrete filling capacity with citations.",
        category="citation_repair",
    ),
    ToolCallingEvalCase(
        query_id="stage38_evidence_convergence_after_skipped_tool",
        question="Connect rock-filled concrete filling quality and durability evidence.",
        category="evidence_convergence",
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="stage38_call_quality",
                    name="hybrid_search_knowledge",
                    arguments={"query": "rock-filled concrete filling quality"},
                ),
                ChatToolCall(
                    id="stage38_call_durability_skip",
                    name="search_knowledge",
                    arguments={"query": "rock-filled concrete durability"},
                ),
            ),
        ),
    ),
    ToolCallingEvalCase(
        query_id="stage38_skip_tool_budget",
        question="Search RFC filling capacity and SCC flowability in one turn.",
        category="skip_tool",
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="stage38_call_search_skip",
                    name="search_knowledge",
                    arguments={"query": "rock-filled concrete filling capacity"},
                ),
                ChatToolCall(
                    id="stage38_call_hybrid_execute",
                    name="hybrid_search_knowledge",
                    arguments={"query": "self-compacting concrete flowability"},
                ),
            ),
        ),
    ),
    ToolCallingEvalCase(
        query_id="stage38_duplicate_tool_call",
        question="Search rock-filled concrete filling capacity twice and answer once.",
        category="duplicate_tool_call",
        tool_call_rounds=(
            (
                ChatToolCall(
                    id="stage38_call_duplicate_1",
                    name="hybrid_search_knowledge",
                    arguments={"query": "rock-filled concrete filling capacity"},
                ),
            ),
            (
                ChatToolCall(
                    id="stage38_call_duplicate_2",
                    name="hybrid_search_knowledge",
                    arguments={"query": "RFC filling capacity"},
                ),
            ),
        ),
    ),
)

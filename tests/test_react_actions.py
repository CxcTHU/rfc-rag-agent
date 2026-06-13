import pytest

from app.services.agent.react_actions import (
    READ_ONLY_REACT_ACTIONS,
    REACT_TOOL_TO_AGENT_TOOL,
    DeterministicReActPlanner,
    ReActAction,
    ReActObservation,
    is_repeated_query,
    normalize_react_query,
    observation_from_tool_result,
    parse_react_action_json,
)
from app.services.agent.tools import AgentToolCallRecord, AgentToolResult


def test_react_action_schema_accepts_only_controlled_actions() -> None:
    action = parse_react_action_json(
        {
            "action": "search_knowledge",
            "query": "filling capacity",
            "reasoning_summary": "Need evidence.",
        }
    )

    assert action.action == "search_knowledge"
    assert "search_knowledge" in READ_ONLY_REACT_ACTIONS
    assert REACT_TOOL_TO_AGENT_TOOL["search_knowledge"] == "hybrid_search_knowledge"
    assert REACT_TOOL_TO_AGENT_TOOL["answer_with_citations"] == "answer_with_citations"


def test_react_action_parser_applies_safe_defaults_for_model_format_variants() -> None:
    search = parse_react_action_json(
        {
            "action": "search_knowledge",
            "reasoning_summary": "Need evidence.",
        },
        default_query="filling capacity",
    )
    refusal = parse_react_action_json(
        {
            "action": "refuse",
            "reason": "No reliable evidence.",
            "reasoning_summary": "Refuse safely.",
        }
    )

    assert search.query == "filling capacity"
    assert refusal.refusal_reason == "No reliable evidence."


def test_react_action_schema_rejects_invalid_or_write_actions() -> None:
    with pytest.raises(ValueError, match="Invalid ReAct action"):
        parse_react_action_json(
            {
                "action": "write_database",
                "query": "delete rows",
                "reasoning_summary": "not allowed",
            }
        )

    with pytest.raises(ValueError, match="requires query"):
        ReActAction(action="search_knowledge", reasoning_summary="Missing query.")


def test_react_action_summaries_are_trimmed_and_safe() -> None:
    action = ReActAction(
        action="search_knowledge",
        query="  filling capacity  ",
        reasoning_summary="  Need evidence.  ",
    )

    assert action.query == "filling capacity"
    assert action.reasoning_summary == "Need evidence."
    assert action.safe_input_summary() == "query=filling capacity"


def test_react_observation_from_tool_result_uses_auditable_summary() -> None:
    action = ReActAction(
        action="answer_with_citations",
        question="What affects filling capacity?",
        reasoning_summary="Answer with citations.",
    )
    tool_result = AgentToolResult(
        tool_name="answer_with_citations",
        call=AgentToolCallRecord(
            tool_name="answer_with_citations",
            input_summary="question=What affects filling capacity?",
            output_summary="refused=False; sources=2; citations=1",
            succeeded=True,
        ),
        answer="Flowability matters [1].",
        sources=[],
        citations=[1],
    )

    observation = observation_from_tool_result(action=action, tool_result=tool_result)

    assert observation.action == "answer_with_citations"
    assert observation.succeeded
    assert observation.citation_count == 1
    assert "citations=1" in observation.observation_summary


def test_deterministic_react_planner_covers_search_rewrite_answer_and_refuse() -> None:
    planner = DeterministicReActPlanner()

    first = planner.plan(question="What affects filling capacity?", observations=[])
    assert first.action == "search_knowledge"

    empty_search = ReActObservation(
        action="search_knowledge",
        query=first.query,
        observation_summary="returned 0 results",
        succeeded=True,
        search_result_count=0,
    )
    rewrite = planner.plan(
        question="What affects filling capacity?",
        observations=[empty_search],
        previous_queries={normalize_react_query(first.query or "")},
    )
    assert rewrite.action == "rewrite_query"
    assert rewrite.query is not None

    repeated_refusal = planner.plan(
        question="What affects filling capacity?",
        observations=[empty_search],
        previous_queries={normalize_react_query(rewrite.query)},
    )
    assert repeated_refusal.action == "refuse"

    successful_search = ReActObservation(
        action="search_knowledge",
        query=first.query,
        observation_summary="returned 3 results",
        succeeded=True,
        search_result_count=3,
    )
    answer = planner.plan(
        question="What affects filling capacity?",
        observations=[successful_search],
    )
    assert answer.action == "answer_with_citations"


def test_repeated_query_detection_normalizes_whitespace_and_case() -> None:
    previous = {normalize_react_query("Filling   Capacity")}

    assert is_repeated_query(" filling capacity ", previous)

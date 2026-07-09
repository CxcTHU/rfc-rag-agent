from __future__ import annotations

from collections.abc import Sequence

from langgraph.graph import END, StateGraph

from app.services.brain.workflow import (
    RESPONSIBILITY_REFUSAL_ANSWER,
    BrainWorkflowStepRecord,
    evaluate_responsibility_gate,
)
from app.services.agentic.nodes import (
    citation_check_node,
    generate_node,
    grade_node,
    grade_router,
    re_retrieve_node,
    retrieve_node,
    rewrite_node,
)
from app.services.agentic.state import AgenticResult, AgenticState
from app.services.generation.chat_model import ChatModelProvider
from app.services.retrieval.embedding import EmbeddingProvider

from sqlalchemy.orm import Session


def build_agentic_graph() -> StateGraph:
    graph = StateGraph(AgenticState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("re_retrieve", re_retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("citation_check", citation_check_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", grade_router, {
        "generate": "generate",
        "rewrite": "rewrite",
    })
    graph.add_edge("rewrite", "re_retrieve")
    graph.add_edge("re_retrieve", "grade")
    graph.add_edge("generate", "citation_check")
    graph.add_edge("citation_check", END)

    return graph


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agentic_graph().compile()
        _compiled_graph.recursion_limit = 15
    return _compiled_graph


def run_agentic_rag(
    question: str,
    db: Session,
    embedding_provider: EmbeddingProvider,
    chat_model_provider: ChatModelProvider,
    history: Sequence[str] | None = None,
) -> AgenticResult:
    normalized_question = question.strip()
    responsibility_gate = evaluate_responsibility_gate(normalized_question)
    if responsibility_gate.triggered:
        return AgenticResult(
            question=normalized_question,
            answer=RESPONSIBILITY_REFUSAL_ANSWER,
            citations=[],
            sources=[],
            refused=True,
            refusal_reason=responsibility_gate.refusal_reason or "responsibility_gate",
            responsibility_gate_triggered=True,
            iteration_count=0,
            invalid_citations=[],
            workflow_steps=[
                BrainWorkflowStepRecord(
                    name="responsibility_gate",
                    input_summary="responsibility_gate=True",
                    output_summary="refused=True responsibility_gate",
                    succeeded=True,
                )
            ],
        )

    compiled = get_compiled_graph()

    initial_state: AgenticState = {
        "question": normalized_question,
        "history": [item.strip() for item in (history or ()) if item.strip()],
        "_db": db,
        "_embedding_provider": embedding_provider,
        "_chat_model_provider": chat_model_provider,
    }

    final_state = compiled.invoke(initial_state)

    return AgenticResult(
        question=final_state.get("question", question),
        answer=final_state.get("answer", ""),
        citations=final_state.get("citations", []),
        sources=final_state.get("results", []),
        refused=final_state.get("refused", False),
        refusal_reason=final_state.get("refusal_reason"),
        responsibility_gate_triggered=final_state.get("responsibility_gate_triggered", False),
        iteration_count=final_state.get("iteration_count", 0),
        invalid_citations=final_state.get("invalid_citations", []),
        workflow_steps=final_state.get("workflow_steps", []),
    )

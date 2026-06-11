from __future__ import annotations

from app.services.agentic.state import MAX_ITERATIONS, AgenticState
from app.services.brain.service import rewrite_contextual_question
from app.services.brain.workflow import (
    DEFAULT_REFUSAL_ANSWER,
    RESPONSIBILITY_REFUSAL_ANSWER,
    BrainWorkflowStepRecord,
    evaluate_evidence_confidence,
    evaluate_responsibility_gate,
    extract_citations,
    has_topic_anchor,
)
from app.services.generation.prompt_builder import SearchResultLike, build_rag_prompt
from app.services.retrieval.decompose import decompose_query
from app.services.retrieval.hybrid_search import HybridSearchService


def retrieve_node(state: AgenticState) -> dict:
    question = state["question"]
    db = state["_db"]
    embedding_provider = state["_embedding_provider"]

    results: list[SearchResultLike] = list(
        HybridSearchService(db, embedding_provider).search(query=question, top_k=5)
    )

    return {
        "results": results,
        "retrieval_queries": [question],
        "iteration_count": 0,
        "workflow_steps": _append_step(
            state,
            "retrieve",
            f"query={question[:80]}",
            f"results={len(results)}",
        ),
    }


def grade_node(state: AgenticState) -> dict:
    query = state.get("rewritten_query") or state["question"]
    results = state.get("results", [])

    if not results:
        return {
            "evidence_sufficient": False,
            "confidence_score": 0.0,
            "workflow_steps": _append_step(
                state,
                "grade",
                f"query={query[:80]}",
                "results=0 evidence_sufficient=False",
            ),
        }

    anchor = has_topic_anchor(query)
    if not anchor:
        return {
            "evidence_sufficient": False,
            "confidence_score": 0.0,
            "workflow_steps": _append_step(
                state,
                "grade",
                f"query={query[:80]}",
                "off-topic: no domain anchor",
            ),
        }

    confidence = evaluate_evidence_confidence(query, results)
    return {
        "evidence_sufficient": confidence.sufficient,
        "confidence_score": confidence.score,
        "workflow_steps": _append_step(
            state,
            "grade",
            f"query={query[:80]} results={len(results)}",
            f"evidence_sufficient={confidence.sufficient} score={confidence.score:.2f}",
        ),
    }


def rewrite_node(state: AgenticState) -> dict:
    question = state["question"]
    results = state.get("results", [])
    iteration = state.get("iteration_count", 0)

    missing_terms = _extract_missing_terms(question, results)
    if missing_terms:
        rewritten = f"{question} {' '.join(missing_terms)}"
    else:
        rewritten = question

    decomposed = decompose_query(rewritten)
    if decomposed.decomposed and decomposed.sub_queries:
        rewritten = " ".join(decomposed.sub_queries)

    return {
        "rewritten_query": rewritten,
        "iteration_count": iteration + 1,
        "workflow_steps": _append_step(
            state,
            "rewrite",
            f"iteration={iteration + 1} original={question[:60]}",
            f"rewritten={rewritten[:80]}",
        ),
    }


def re_retrieve_node(state: AgenticState) -> dict:
    rewritten_query = state.get("rewritten_query", state["question"])
    db = state["_db"]
    embedding_provider = state["_embedding_provider"]

    new_results: list[SearchResultLike] = list(
        HybridSearchService(db, embedding_provider).search(query=rewritten_query, top_k=5)
    )

    existing_results = state.get("results", [])
    merged = _merge_results(existing_results, new_results)

    prev_queries = state.get("retrieval_queries", [])
    return {
        "results": merged,
        "retrieval_queries": prev_queries + [rewritten_query],
        "workflow_steps": _append_step(
            state,
            "re_retrieve",
            f"re-retrieve query={rewritten_query[:60]}",
            f"new={len(new_results)} merged={len(merged)}",
        ),
    }


def generate_node(state: AgenticState) -> dict:
    question = state["question"]
    results = state.get("results", [])
    generation_question = rewrite_contextual_question(question, state.get("history", []))
    chat_model_provider = state["_chat_model_provider"]

    gate = evaluate_responsibility_gate(generation_question)
    if gate.triggered:
        return {
            "answer": RESPONSIBILITY_REFUSAL_ANSWER,
            "citations": [],
            "refused": True,
            "refusal_reason": gate.refusal_reason or "responsibility_gate",
            "responsibility_gate_triggered": True,
            "workflow_steps": _append_step(
                state,
                "generate",
                "responsibility_gate=True",
                "refused=True responsibility_gate",
            ),
        }

    if not results:
        return {
            "answer": DEFAULT_REFUSAL_ANSWER,
            "citations": [],
            "refused": True,
            "refusal_reason": "No retrieved chunks were available.",
            "responsibility_gate_triggered": False,
            "workflow_steps": _append_step(
                state,
                "generate",
                "sources=0",
                "refused=True no_sources",
            ),
        }

    if not state.get("evidence_sufficient", False):
        confidence = evaluate_evidence_confidence(generation_question, results)
        if not confidence.sufficient:
            return {
                "answer": DEFAULT_REFUSAL_ANSWER,
                "citations": [],
                "refused": True,
                "refusal_reason": confidence.refusal_reason or "Evidence insufficient after iteration cap.",
                "responsibility_gate_triggered": False,
                "workflow_steps": _append_step(
                    state,
                    "generate",
                    f"sources={len(results)} evidence_sufficient=False",
                    f"refused=True low_evidence score={confidence.score:.2f}",
                ),
            }

    try:
        rag_prompt = build_rag_prompt(question=generation_question, search_results=results)
    except ValueError as exc:
        return {
            "answer": DEFAULT_REFUSAL_ANSWER,
            "citations": [],
            "refused": True,
            "refusal_reason": str(exc),
            "responsibility_gate_triggered": False,
            "workflow_steps": _append_step(
                state,
                "generate",
                f"sources={len(results)}",
                f"refused=True error={exc}",
            ),
        }

    model_result = chat_model_provider.generate(rag_prompt.messages)
    allowed_source_ids = [s.source_id for s in rag_prompt.sources]
    citations = extract_citations(model_result.answer, allowed_source_ids)

    return {
        "answer": model_result.answer,
        "citations": citations,
        "refused": False,
        "refusal_reason": None,
        "responsibility_gate_triggered": False,
        "workflow_steps": _append_step(
            state,
            "generate",
            f"sources={len(rag_prompt.sources)}",
            f"refused=False citations={len(citations)}",
        ),
    }


def citation_check_node(state: AgenticState) -> dict:
    citations = state.get("citations", [])
    results = state.get("results", [])

    if not citations or not results:
        return {
            "invalid_citations": [],
            "workflow_steps": _append_step(
                state,
                "citation_check",
                f"citations={len(citations)} results={len(results)}",
                "invalid=0",
            ),
        }

    valid_source_ids = set()
    for i, _result in enumerate(results):
        valid_source_ids.add(i + 1)

    invalid = [c for c in citations if c not in valid_source_ids]
    return {
        "invalid_citations": invalid,
        "workflow_steps": _append_step(
            state,
            "citation_check",
            f"citations={len(citations)}",
            f"invalid={len(invalid)}",
        ),
    }


def grade_router(state: AgenticState) -> str:
    if state.get("evidence_sufficient", False):
        return "generate"
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return "generate"
    return "rewrite"


def _merge_results(
    existing: list[SearchResultLike],
    new: list[SearchResultLike],
) -> list[SearchResultLike]:
    seen_chunk_ids: set[int] = set()
    merged: list[SearchResultLike] = []
    for result in existing:
        if result.chunk_id not in seen_chunk_ids:
            seen_chunk_ids.add(result.chunk_id)
            merged.append(result)
    for result in new:
        if result.chunk_id not in seen_chunk_ids:
            seen_chunk_ids.add(result.chunk_id)
            merged.append(result)
    return sorted(merged, key=lambda r: -r.score)[:10]


def _extract_missing_terms(question: str, results: list[SearchResultLike]) -> list[str]:
    confidence = evaluate_evidence_confidence(question, results)
    return list(confidence.missing_terms[:3])


def _append_step(
    state: AgenticState,
    name: str,
    input_summary: str,
    output_summary: str,
) -> list[BrainWorkflowStepRecord]:
    existing = list(state.get("workflow_steps", []))
    existing.append(
        BrainWorkflowStepRecord(
            name=name,  # type: ignore[arg-type]
            input_summary=input_summary,
            output_summary=output_summary,
            succeeded=True,
        )
    )
    return existing

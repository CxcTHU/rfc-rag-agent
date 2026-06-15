from dataclasses import dataclass

from app.services.agent.refusal_explainer import (
    MAX_SOURCE_SUMMARY_CHARS,
    build_refusal_explanation,
    summarize_sources,
)


@dataclass(frozen=True)
class FakeSource:
    title: str
    source_type: str
    content: str | None


def test_off_topic_explanation_suggests_safe_domain_rewrites() -> None:
    explanation = build_refusal_explanation(
        category="off_topic",
        refusal_reason="Question appears off-topic: retrieved chunks share no domain anchor.",
        sources=[],
    )

    assert explanation is not None
    assert "可以改写为" in explanation
    assert "堆石混凝土" in explanation
    assert "CORE_DOMAIN_TERMS" not in explanation
    assert "prompt" not in explanation.casefold()


def test_evidence_insufficient_explanation_uses_short_sanitized_source_summaries() -> None:
    long_content = "Filling capacity depends on flowability. " * 30
    source = FakeSource(
        title="Filling Capacity Guide",
        source_type="local_file",
        content=long_content,
    )

    summaries = summarize_sources([source])
    explanation = build_refusal_explanation(
        category="evidence_insufficient",
        refusal_reason="Retrieved chunks did not share enough evidence-bearing query terms.",
        sources=[source],
    )

    assert summaries
    assert len(summaries[0]) <= MAX_SOURCE_SUMMARY_CHARS
    assert explanation is not None
    assert "Filling Capacity Guide" in explanation
    assert long_content not in explanation
    assert "API key" not in explanation
    assert "Bearer token" not in explanation

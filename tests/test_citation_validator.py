from dataclasses import dataclass

import pytest

from app.services.generation.citation_validator import (
    UNSUPPORTED_MARKER,
    validate_and_repair_citations,
)


@dataclass(frozen=True)
class FakeSource:
    source_id: int
    content: str


def test_validator_annotates_sentence_without_citation() -> None:
    result = validate_and_repair_citations(
        "Rock-filled concrete uses large rocks.",
        [FakeSource(1, "Rock-filled concrete uses large rocks and self-compacting concrete.")],
    )

    assert result.unsupported_count == 1
    assert UNSUPPORTED_MARKER in result.answer
    assert result.sentence_results[0].reason == "missing_citation"


def test_validator_annotates_unknown_source_id() -> None:
    result = validate_and_repair_citations(
        "Rock-filled concrete uses large rocks [99].",
        [FakeSource(1, "Rock-filled concrete uses large rocks.")],
    )

    assert result.unsupported_count == 1
    assert UNSUPPORTED_MARKER in result.answer
    assert result.sentence_results[0].reason == "unknown_source_id"


def test_validator_annotates_existing_but_unsupported_citation() -> None:
    result = validate_and_repair_citations(
        "Rock-filled concrete improves thermal control [1].",
        [FakeSource(1, "Arch dams transfer load to abutments.")],
    )

    assert result.unsupported_count == 1
    assert UNSUPPORTED_MARKER in result.answer
    assert result.sentence_results[0].reason == "no_keyword_overlap"


def test_validator_keeps_supported_citation() -> None:
    result = validate_and_repair_citations(
        "Rock-filled concrete uses large rocks [1].",
        [FakeSource(1, "Rock-filled concrete uses large rocks and self-compacting concrete.")],
    )

    assert result.unsupported_count == 0
    assert result.answer == "Rock-filled concrete uses large rocks [1]."
    assert result.sentence_results[0].supported is True


def test_validator_drop_mode_removes_unsupported_sentences() -> None:
    result = validate_and_repair_citations(
        "Rock-filled concrete uses large rocks [1]. Unsupported sentence.",
        [FakeSource(1, "Rock-filled concrete uses large rocks.")],
        mode="drop",
    )

    assert result.unsupported_count == 1
    assert result.dropped_count == 1
    assert result.answer == "Rock-filled concrete uses large rocks [1]."
    assert UNSUPPORTED_MARKER not in result.answer


def test_validator_returns_empty_answer_unchanged() -> None:
    result = validate_and_repair_citations("", [FakeSource(1, "content")])

    assert result.answer == ""
    assert result.unsupported_count == 0
    assert result.sentence_results == ()


def test_validator_keeps_refusal_unchanged() -> None:
    answer = "当前资料库中没有找到足够可靠的依据。"

    result = validate_and_repair_citations(answer, [FakeSource(1, "unrelated")])

    assert result.answer == answer
    assert result.unsupported_count == 0
    assert result.sentence_results == ()


def test_validator_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="mode"):
        validate_and_repair_citations("Answer [1].", [FakeSource(1, "Answer")], mode="bad")  # type: ignore[arg-type]

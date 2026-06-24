from app.services.brain.service import BrainService
from app.services.conversation.session_memory import (
    MemoryItem,
    SessionMemory,
    augment_query_with_session_memory,
    build_session_memory,
    decay_session_memory,
    format_session_memory_for_retrieval,
    is_correction_question,
    refine_memory_for_question,
)
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider


def test_session_memory_extracts_entities_and_retrieval_anchors() -> None:
    memory = build_session_memory(
        [
            "用户：堆石混凝土填充密实性受自密实混凝土流动性影响吗？",
            "助手：回答提到了骨料级配和孔隙填充。",
        ]
    )

    assert "堆石混凝土" in memory.entities
    assert "自密实混凝土" in memory.entities
    assert "流动性" in memory.retrieval_anchors
    assert "骨料级配" in memory.retrieval_anchors


def test_session_memory_hint_is_marked_retrieval_only() -> None:
    memory = build_session_memory(["用户：RFC thermal control uses cooling pipes."])
    hint = format_session_memory_for_retrieval(memory)

    assert "仅用于检索" in hint
    assert "不作为引用来源" in hint
    assert "RFC" in hint or "rfc" in hint
    assert "cooling pipes" in hint


def test_augment_query_with_session_memory_appends_short_hint() -> None:
    memory = build_session_memory(["用户：What evidence covers RFC durability?"])

    augmented = augment_query_with_session_memory("How does that relate to monitoring?", memory)

    assert augmented.startswith("How does that relate to monitoring?")
    assert "会话检索记忆" in augmented
    assert "durability" in augmented


def test_correction_question_filters_stale_retrieval_anchors() -> None:
    memory = build_session_memory(
        ["user:Peridynamics is a construction quality control method?"]
    )

    refined = refine_memory_for_question(
        "\u66f4\u6b63\u4e00\u4e0b\uff0c\u6211\u60f3\u95ee Peridynamics "
        "\u7528\u4e8e\u88c2\u7eb9\u5206\u6790\u7684\u8bc1\u636e",
        memory,
    )
    hint = format_session_memory_for_retrieval(refined)
    augmented = augment_query_with_session_memory(
        "\u66f4\u6b63\u4e00\u4e0b\uff0c\u6211\u60f3\u95ee Peridynamics "
        "\u7528\u4e8e\u88c2\u7eb9\u5206\u6790\u7684\u8bc1\u636e",
        memory,
    )

    assert "peridynamics" in refined.entities
    assert "construction" not in refined.retrieval_anchors
    assert "quality" not in refined.retrieval_anchors
    assert "control" not in refined.retrieval_anchors
    assert "\u88c2\u7eb9" in refined.retrieval_anchors
    assert refined.constraints
    assert {"construction", "quality", "control"}.issubset(set(refined.stale_anchors))
    assert "construction" not in hint
    assert "quality" not in hint
    assert "construction" not in augmented
    assert "quality" not in augmented


def test_plain_follow_up_does_not_trigger_correction_filter() -> None:
    memory = build_session_memory(
        ["user:Peridynamics is a construction quality control method?"]
    )

    refined = refine_memory_for_question(
        "\u6211\u60f3\u95ee\u5b83\u7528\u4e8e\u54ea\u4e9b\u5206\u6790",
        memory,
    )

    assert refined == memory
    assert "construction" in refined.retrieval_anchors


def test_correction_detector_handles_stale_topic_rejection_without_citation_false_positive() -> None:
    assert is_correction_question("不是弹性模量，请按最近的冷却管继续。")
    assert is_correction_question("我问的是最近的质量验收，不是水化热。")
    assert is_correction_question("Not applications; continue thermal stress calculation.")
    assert not is_correction_question("Please expand, but do not cite memory itself.")


def test_session_memory_items_record_turn_index_and_importance() -> None:
    memory = build_session_memory(
        [
            "user: RFC durability",
            "assistant: ok",
            "user: RFC thermal control and cooling pipes",
        ],
        half_life=2.0,
    )

    rfc = next(item for item in memory.entities if item.text.casefold() == "rfc")
    cooling = next(
        item
        for item in memory.retrieval_anchors
        if item.text.casefold() == "cooling"
    )

    assert rfc.turn_index == 3
    assert rfc.importance == 1.0
    assert cooling.turn_index == 3
    assert cooling.importance == 1.0


def test_decay_session_memory_reduces_old_item_importance() -> None:
    memory = decay_session_memory(
        SessionMemory(
            retrieval_anchors=(
                MemoryItem(text="old", turn_index=1, importance=1.0),
                MemoryItem(text="new", turn_index=6, importance=1.0),
            )
        ),
        current_turn=6,
        half_life=5.0,
    )

    old = next(item for item in memory.retrieval_anchors if item.text == "old")
    new = next(item for item in memory.retrieval_anchors if item.text == "new")

    assert old.importance == 0.5
    assert new.importance == 1.0


def test_brain_rewrite_step_does_not_prepend_stale_context_after_correction() -> None:
    service = BrainService(
        db=None,  # type: ignore[arg-type]
        chat_model_provider=DeterministicChatModelProvider(),
        embedding_provider=DeterministicEmbeddingProvider(),
        log_answers=False,
    )

    rewritten, step = service._rewrite_query_step(
        question="\u66f4\u6b63\u4e00\u4e0b\uff0c\u6211\u60f3\u95ee\u5b83"
        "\u7528\u4e8e\u88c2\u7eb9\u5206\u6790\u7684\u8bc1\u636e",
        history=["user:Peridynamics is a construction quality control method?"],
    )

    assert step.name == "rewrite_query"
    assert "peridynamics" in rewritten.casefold()
    assert "construction" not in rewritten.casefold()
    assert "quality" not in rewritten.casefold()
    assert "control" not in rewritten.casefold()


def test_brain_rewrite_step_uses_memory_only_for_contextual_question() -> None:
    service = BrainService(
        db=None,  # type: ignore[arg-type]
        chat_model_provider=DeterministicChatModelProvider(),
        embedding_provider=DeterministicEmbeddingProvider(),
        log_answers=False,
    )

    rewritten, step = service._rewrite_query_step(
        question="它的流动性为什么重要？",
        history=["用户：自密实混凝土在堆石混凝土中起什么作用？"],
    )

    assert step.name == "rewrite_query"
    assert step.output_summary == "query rewritten from recent history"
    assert "自密实混凝土" in rewritten
    assert "会话检索记忆" in rewritten
    assert "不作为引用来源" in rewritten

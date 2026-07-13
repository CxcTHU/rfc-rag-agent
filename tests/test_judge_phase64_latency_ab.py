from scripts.judge_phase64_latency_ab import (
    JUDGE_OUTPUT_FIELDS,
    build_safe_judge_row,
    build_blind_pair_prompt,
    paired_bootstrap_lower_bound,
    judge_blind_pair,
    summarize_judge_rows,
)
from app.services.generation.chat_model import ChatModelResult


class _JudgeProvider:
    provider_name = "openai-compatible"
    model_name = "judge-model"

    def generate(self, _messages):
        return ChatModelResult(
            answer='{"winner":"B","quality_delta":-0.5,"reason":"raw judge text"}',
            provider=self.provider_name,
            model_name=self.model_name,
        )


def test_bootstrap_is_deterministic() -> None:
    deltas = [0.0, 0.01, -0.01, 0.02] * 10

    assert paired_bootstrap_lower_bound(deltas) == paired_bootstrap_lower_bound(deltas)


def test_blind_judge_output_cannot_persist_answers_or_prompt() -> None:
    prompt, mapping = build_blind_pair_prompt("question", "answer-a", "answer-b", seed=7)

    assert {mapping["A"], mapping["B"]} == {"phase63", "phase64"}
    assert "phase63" not in prompt
    assert "phase64" not in prompt
    assert {"answer_a", "answer_b", "prompt"}.isdisjoint(JUDGE_OUTPUT_FIELDS)


def test_safe_judge_row_keeps_only_numeric_outcome_and_mapping_hash() -> None:
    row = build_safe_judge_row(
        case_id="case-1",
        run=1,
        category="ordinary_text",
        mapping={"A": "phase63", "B": "phase64"},
        winner_label="B",
        label_quality_delta=-0.25,
        judge_latency_ms=12.0,
        judge_provider="paratera",
        judge_model="GLM-5.2",
        reason="brief rationale",
    )

    assert row["winner"] == "phase64"
    assert row["quality_delta"] == 0.25
    assert {"answer", "prompt", "brief rationale"}.isdisjoint(row)


def test_judge_summary_uses_phase64_deltas_and_loss_rate() -> None:
    summary = summarize_judge_rows(
        [
            {"quality_delta": 0.10, "winner": "phase64"},
            {"quality_delta": 0.00, "winner": "tie"},
            {"quality_delta": -0.01, "winner": "phase63"},
        ],
        seed=9,
        samples=100,
    )

    assert summary["paired_count"] == 3
    assert summary["loss_rate"] == 0.3333
    assert summary["paired_quality_lower_bound"] <= 0.03


def test_blind_pair_judge_projects_provider_response_to_safe_row() -> None:
    row = judge_blind_pair(
        _JudgeProvider(),
        case_id="case-1",
        run=1,
        category="ordinary_text",
        question="question",
        answer_phase63="answer-a",
        answer_phase64="answer-b",
        seed=7,
    )

    assert row["winner"] in {"phase63", "phase64", "tie"}
    assert row["quality_delta"] in {-0.5, 0.5}
    assert "answer_phase63" not in row
    assert "answer_phase64" not in row

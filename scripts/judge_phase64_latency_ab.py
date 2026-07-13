from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections.abc import Sequence
from typing import Protocol


JUDGE_OUTPUT_FIELDS = (
    "case_id",
    "run",
    "category",
    "winner",
    "quality_delta",
    "mapping_hash",
    "judge_latency_ms",
    "judge_provider",
    "judge_model",
    "sanitized_reason",
)


class BlindJudgeProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, messages: object) -> object: ...


def build_safe_judge_row(
    *,
    case_id: str,
    run: int,
    category: str,
    mapping: dict[str, str],
    winner_label: str,
    label_quality_delta: float,
    judge_latency_ms: float,
    judge_provider: str,
    judge_model: str,
    reason: str,
) -> dict[str, object]:
    winner = mapping.get(winner_label, "tie") if winner_label in {"A", "B"} else "tie"
    direction = 1.0 if mapping.get("A") == "phase64" else -1.0
    return {
        "case_id": case_id,
        "run": int(run),
        "category": category,
        "winner": winner,
        "quality_delta": round(float(label_quality_delta) * direction, 6),
        "mapping_hash": hashlib.sha256(
            json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "judge_latency_ms": round(float(judge_latency_ms), 3),
        "judge_provider": judge_provider,
        "judge_model": judge_model,
        "sanitized_reason": "judge_rationale_received" if reason.strip() else "judge_rationale_unavailable",
    }


def summarize_judge_rows(
    rows: Sequence[dict[str, object]],
    *,
    seed: int = 640013,
    samples: int = 10000,
) -> dict[str, object]:
    deltas = [
        float(row["quality_delta"])
        for row in rows
        if isinstance(row.get("quality_delta"), (int, float))
        and math.isfinite(float(row["quality_delta"]))
    ]
    loss_rate = (
        round(sum(1 for row in rows if row.get("winner") == "phase63") / len(rows), 4)
        if rows
        else 1.0
    )
    return {
        "paired_count": len(deltas),
        "paired_quality_lower_bound": paired_bootstrap_lower_bound(
            deltas,
            seed=seed,
            samples=samples,
        ),
        "loss_rate": loss_rate,
    }


def paired_bootstrap_lower_bound(
    deltas: Sequence[float],
    *,
    seed: int = 640013,
    samples: int = 10000,
    alpha: float = 0.05,
) -> float:
    values = [float(value) for value in deltas if math.isfinite(float(value))]
    if not values:
        return float("nan")
    if samples < 1:
        raise ValueError("samples must be positive")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")
    generator = random.Random(seed)
    size = len(values)
    means = sorted(
        sum(values[generator.randrange(size)] for _ in range(size)) / size
        for _ in range(samples)
    )
    return round(means[min(samples - 1, int(math.floor(alpha * samples)))], 6)


def build_blind_pair_prompt(
    question: str,
    answer_a: str,
    answer_b: str,
    *,
    seed: int,
) -> tuple[str, dict[str, str]]:
    digest = hashlib.sha256(f"{seed}:{question}".encode("utf-8")).digest()
    mapping = (
        {"A": "phase63", "B": "phase64"}
        if digest[0] % 2 == 0
        else {"A": "phase64", "B": "phase63"}
    )
    display_a = answer_a if mapping["A"] == "phase63" else answer_b
    display_b = answer_b if mapping["B"] == "phase64" else answer_a
    prompt = (
        "比较两个匿名回答是否同样准确、完整且有用。只返回 JSON："
        '{"winner":"A|B|tie","quality_delta":-1..1,"reason":"<=120 chars"}。\n'
        f"问题：{question}\n\n回答 A：{display_a}\n\n回答 B：{display_b}"
    )
    return prompt, mapping


def judge_blind_pair(
    provider: BlindJudgeProvider,
    *,
    case_id: str,
    run: int,
    category: str,
    question: str,
    answer_phase63: str,
    answer_phase64: str,
    seed: int,
) -> dict[str, object]:
    from app.services.generation.chat_model import ChatMessage

    prompt, mapping = build_blind_pair_prompt(
        question,
        answer_phase63,
        answer_phase64,
        seed=seed,
    )
    started = time.perf_counter()
    result = provider.generate(
        [
            ChatMessage(
                role="system",
                content="Return only the requested JSON; do not reveal model or route labels.",
            ),
            ChatMessage(role="user", content=prompt),
        ]
    )
    try:
        payload = json.loads(str(getattr(result, "answer", "")))
        winner_label = str(payload.get("winner", "tie")).strip()
        label_quality_delta = float(payload.get("quality_delta", 0.0))
        reason = str(payload.get("reason", ""))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("blind_judge_invalid_json") from exc
    if winner_label not in {"A", "B", "tie"} or not math.isfinite(label_quality_delta):
        raise ValueError("blind_judge_invalid_fields")
    return build_safe_judge_row(
        case_id=case_id,
        run=run,
        category=category,
        mapping=mapping,
        winner_label=winner_label,
        label_quality_delta=max(-1.0, min(1.0, label_quality_delta)),
        judge_latency_ms=(time.perf_counter() - started) * 1000.0,
        judge_provider=str(getattr(provider, "provider_name", "")),
        judge_model=str(getattr(provider, "model_name", "")),
        reason=reason,
    )

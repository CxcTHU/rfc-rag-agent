from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.agent.tool_calling_service import phase64_final_answer_provider
from app.services.generation.chat_model import ChatMessage, create_chat_model_provider


class StreamingProvider(Protocol):
    def stream_generate(self, messages: Sequence[ChatMessage]): ...


def measure_final_model_floor(
    provider: StreamingProvider,
    messages: Sequence[ChatMessage],
) -> dict[str, float | bool]:
    started = time.perf_counter()
    first_content_delta_ms: float | None = None
    try:
        for delta in provider.stream_generate(messages):
            if delta and first_content_delta_ms is None:
                first_content_delta_ms = (time.perf_counter() - started) * 1000.0
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "ok": first_content_delta_ms is not None,
            "first_content_delta_ms": round(first_content_delta_ms or 0.0, 3),
            "elapsed_ms": round(elapsed_ms, 3),
        }
    except Exception:
        return {
            "ok": False,
            "first_content_delta_ms": round(first_content_delta_ms or 0.0, 3),
            "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the configured final provider's safe empty-evidence streaming floor."
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--phase64-non-thinking", action="store_true")
    return parser.parse_args()


def build_floor_provider(
    settings: object,
    *,
    phase64_non_thinking: bool,
) -> StreamingProvider:
    provider = create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
        max_tokens=settings.agent_final_max_tokens,
    )
    if phase64_non_thinking:
        return phase64_final_answer_provider(provider, settings)
    return provider


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        return 2
    settings = get_settings()
    provider = build_floor_provider(
        settings,
        phase64_non_thinking=bool(args.phase64_non_thinking),
    )
    messages = [ChatMessage(role="user", content="fixed safe probe")]
    rows = [measure_final_model_floor(provider, messages) for _ in range(args.runs)]
    print(json.dumps({"rows": rows}, ensure_ascii=False, sort_keys=True))
    return 0 if all(bool(row["ok"]) for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

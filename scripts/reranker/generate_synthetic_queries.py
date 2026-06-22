from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.generation.chat_model import ChatMessage, create_chat_model_provider  # noqa: E402
from scripts.reranker.export_training_pairs import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    DOMAIN_TERMS,
    normalize_text,
)

DEFAULT_INPUT = DEFAULT_OUTPUT_DIR / "sampled_chunks.jsonl"
DEFAULT_OUTPUT = DEFAULT_OUTPUT_DIR / "synthetic_queries.jsonl"


@dataclass(frozen=True)
class SyntheticQueryRow:
    query: str
    chunk_id: int
    document_id: int
    chunk_type: str
    source: str
    content: str
    status: str = "completed"
    error_summary: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic RFC reranker queries.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Call the configured chat provider.")
    parser.add_argument("--min-query-chars", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = generate_synthetic_queries(
        input_path=args.input,
        output_path=args.output,
        limit=args.limit,
        execute=args.execute,
        resume=args.resume,
        min_query_chars=args.min_query_chars,
    )
    completed = sum(1 for row in rows if row.status == "completed")
    print(
        f"synthetic_query_generation execute={args.execute} "
        f"rows={len(rows)} completed={completed} output={args.output}"
    )


def generate_synthetic_queries(
    *,
    input_path: Path,
    output_path: Path,
    limit: int,
    execute: bool,
    resume: bool = False,
    min_query_chars: int = 10,
) -> list[SyntheticQueryRow]:
    sampled = read_jsonl(input_path)
    existing_ids = existing_chunk_ids(output_path) if resume else set()
    selected = [
        row for row in sampled
        if int(row.get("chunk_id", 0) or 0) not in existing_ids
    ][: max(limit, 0)]
    provider = None
    if execute:
        settings = get_settings()
        provider = create_chat_model_provider(
            provider_name=settings.chat_model_provider,
            model_name=settings.chat_model_name,
            api_key=settings.chat_model_api_key,
            base_url=settings.chat_model_base_url,
            temperature=settings.chat_model_temperature,
            timeout_seconds=settings.chat_model_timeout_seconds,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if resume and output_path.exists() else "w"
    generated: list[SyntheticQueryRow] = []
    with output_path.open(mode, encoding="utf-8", newline="\n") as handle:
        for item in selected:
            content = normalize_text(str(item.get("content", "")))
            if not execute:
                query = dry_run_query(item)
                status = "dry_run"
                error_summary = ""
            else:
                try:
                    if provider is None:
                        raise RuntimeError("chat provider was not initialized")
                    query = clean_generated_query(provider.generate(prompt_messages(content)).answer)
                    status = "completed"
                    error_summary = ""
                    if not query_is_usable(query, min_chars=min_query_chars):
                        status = "filtered"
                        error_summary = "generated query was too short or off-domain"
                except Exception as exc:  # noqa: BLE001
                    query = ""
                    status = "error"
                    error_summary = type(exc).__name__
            row = SyntheticQueryRow(
                query=query,
                chunk_id=int(item["chunk_id"]),
                document_id=int(item["document_id"]),
                chunk_type=str(item.get("chunk_type", "")),
                source="synthetic_llm" if execute else "synthetic_dry_run",
                content=content[:2000],
                status=status,
                error_summary=error_summary,
            )
            generated.append(row)
            handle.write(json.dumps(asdict(row), ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
    return generated


def prompt_messages(chunk_content: str) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "You generate one natural user question for a roller-compacted concrete "
                "dam engineering assistant. The provided passage must be sufficient to "
                "answer the question. Output only the question, without explanations, "
                "citations, JSON, or markdown."
            ),
        ),
        ChatMessage(role="user", content=chunk_content[:1800]),
    ]


def dry_run_query(item: dict[str, object]) -> str:
    content = str(item.get("content", "")).casefold()
    title = normalize_text(str(item.get("document_title", "")))
    chunk_type = normalize_text(str(item.get("chunk_type", "")))
    prefix = "What RFC engineering points"
    if "hydrat" in content or "temper" in content or "thermal" in content:
        prefix = "What hydration heat control points"
    elif "crack" in content or "shrink" in content:
        prefix = "What cracking control points"
    elif "construct" in content or "placement" in content or "compact" in content:
        prefix = "What construction control points"
    if title:
        return f"For {title}, what key RFC points are covered in this {chunk_type or 'passage'}?"
    return f"{prefix} does this RFC passage describe?"


def clean_generated_query(value: str) -> str:
    cleaned = normalize_text(value).strip("\"'` ")
    if "\n" in cleaned:
        cleaned = cleaned.splitlines()[0].strip()
    return cleaned


def query_is_usable(query: str, *, min_chars: int) -> bool:
    if len(query.strip()) < min_chars:
        return False
    lowered = query.casefold()
    return any(term in lowered for term in DOMAIN_TERMS) or any(
        term in lowered
        for term in ("rfc", "roller-compacted", "concrete", "dam", "hydration", "crack", "construction")
    )


def existing_chunk_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {
        int(row.get("chunk_id", 0) or 0)
        for row in read_jsonl(path)
        if row.get("chunk_id")
    }


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()

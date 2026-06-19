"""Probe vision provider connectivity without writing DB rows or secrets."""

from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app.services.generation.vision_model import OpenAICompatibleVisionModelProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe OpenAI-compatible vision providers.")
    parser.add_argument("--image", default="data/images/1186/page1_img1.png")
    parser.add_argument("--provider", choices=["official", "paratera"], required=True)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=45)
    args = parser.parse_args()

    image = Path(args.image)
    key_env = "OFFICIAL_GLM_KEY" if args.provider == "official" else "PARATERA_GLM_KEY"
    base_url = (
        "https://open.bigmodel.cn/api/paas/v4"
        if args.provider == "official"
        else "https://llmapi.paratera.com"
    )
    api_key = os.environ.get(key_env, "")
    provider_name = "openai-compatible" if args.provider == "official" else "paratera"
    prompt = "请用中文用一句话客观描述这张论文图片，不要扩展。"

    def run_one(index: int) -> dict[str, object]:
        started = time.time()
        try:
            provider = OpenAICompatibleVisionModelProvider(
                model_name="GLM-4.6V",
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=args.timeout_seconds,
                provider_name=provider_name,
            )
            text = provider.describe_image(image, prompt=prompt)
            return {
                "lane": index,
                "ok": True,
                "seconds": round(time.time() - started, 2),
                "chars": len(text),
                "preview": text[:60].replace("\n", " "),
            }
        except Exception as exc:  # noqa: BLE001 - probe reports sanitized error class
            return {
                "lane": index,
                "ok": False,
                "seconds": round(time.time() - started, 2),
                "error": sanitize_probe_error(exc),
            }

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(run_one, index + 1) for index in range(args.concurrency)]
        for future in as_completed(futures):
            print(future.result())


def sanitize_probe_error(exc: Exception) -> str:
    text = str(exc)
    if "timed out" in text.casefold() or "timeout" in text.casefold() or "WinError 10060" in text:
        return f"{type(exc).__name__}: provider_timeout"
    if "HTTP 429" in text or "RateLimitError" in text:
        return f"{type(exc).__name__}: provider_rate_limited"
    if "余额不足" in text or "无可用资源包" in text:
        return f"{type(exc).__name__}: provider_quota_exhausted"
    return f"{type(exc).__name__}: {text[:180]}"


if __name__ == "__main__":
    main()

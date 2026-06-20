"""Check whether Phase 46 rendered images are ready for real vision redescription."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402


DEFAULT_MANIFEST = ROOT / "data" / "evaluation" / "phase46_rendered_image_manifest.csv"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "phase46_redescribe_readiness.json"
DETERMINISTIC_VISION_PROVIDERS = {"", "deterministic", "fake", "local"}
PHASE45_VISION_ROUTES = (
    ("official_new_a", "openai-compatible", "GLM-4.6V", "OFFICIAL_GLM_KEY", "https://open.bigmodel.cn/api/paas/v4"),
    ("official_new_b", "openai-compatible", "GLM-4.6V", "OFFICIAL_GLM_KEY", "https://open.bigmodel.cn/api/paas/v4"),
    ("official_old_a", "openai-compatible", "GLM-4.6V", "OFFICIAL_GLM_KEY", "https://open.bigmodel.cn/api/paas/v4"),
    ("official_old_b", "openai-compatible", "GLM-4.6V", "OFFICIAL_GLM_KEY", "https://open.bigmodel.cn/api/paas/v4"),
    ("paratera_c", "paratera", "GLM-4.6V", "PARATERA_GLM_KEY", "https://llmapi.paratera.com"),
)


@dataclass(frozen=True)
class Phase46RedescribeReadiness:
    render_manifest: str
    total_rows: int
    pending_images: int
    existing_images: int
    failed_images: int
    vision_provider_configured: bool
    vision_model_configured: bool
    vision_base_url_configured: bool
    vision_api_key_configured: bool
    vision_provider_is_real: bool
    phase45_route_vision_configured: bool
    configured_vision_routes: list[str]
    missing_vision_route_key_envs: list[str]
    embedding_provider_configured: bool
    embedding_model_configured: bool
    embedding_api_key_configured: bool
    status: str
    reason: str
    next_command: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Phase 46 redescription readiness.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--vision-route",
        action="append",
        default=[],
        help="Optional route spec: label,provider,model,key_env,base_url. May be repeated.",
    )
    args = parser.parse_args()

    route_specs = parse_vision_route_specs(args.vision_route) if args.vision_route else PHASE45_VISION_ROUTES
    report = build_readiness_report(Path(args.manifest), route_specs=route_specs)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "summary:",
        f"status={report.status}",
        f"pending_images={report.pending_images}",
        f"vision_provider_configured={report.vision_provider_configured}",
        f"vision_model_configured={report.vision_model_configured}",
        f"vision_base_url_configured={report.vision_base_url_configured}",
        f"vision_api_key_configured={report.vision_api_key_configured}",
        f"vision_provider_is_real={report.vision_provider_is_real}",
        f"phase45_route_vision_configured={report.phase45_route_vision_configured}",
        f"configured_vision_routes={len(report.configured_vision_routes)}",
    )
    print(f"wrote {output_path}")


def build_readiness_report(
    manifest_path: Path,
    route_specs: tuple[tuple[str, str, str, str, str], ...] = PHASE45_VISION_ROUTES,
) -> Phase46RedescribeReadiness:
    counts = count_manifest_statuses(manifest_path)
    settings = get_settings()
    vision_provider = settings.vision_model_provider.strip()
    vision_provider_configured = bool(vision_provider)
    vision_provider_is_real = vision_provider.casefold() not in DETERMINISTIC_VISION_PROVIDERS
    vision_model_configured = bool(settings.vision_model_name.strip())
    vision_base_url_configured = bool(settings.vision_model_base_url.strip())
    vision_api_key_configured = bool(settings.vision_model_api_key.strip())
    configured_routes, missing_route_key_envs = inspect_vision_routes(route_specs)
    phase45_route_vision_configured = bool(configured_routes)
    embedding_provider_configured = bool(settings.embedding_provider.strip())
    embedding_model_configured = bool(settings.embedding_model_name.strip())
    embedding_api_key_configured = bool(settings.embedding_api_key.strip())

    missing: list[str] = []
    if counts["pending"] <= 0:
        missing.append("pending_render_images")
    unified_vision_configured = (
        vision_provider_configured
        and vision_provider_is_real
        and vision_model_configured
        and vision_base_url_configured
        and vision_api_key_configured
    )
    if not unified_vision_configured and not phase45_route_vision_configured:
        missing.append("real_vision_route_or_unified_vision_config")
    if not embedding_provider_configured:
        missing.append("EMBEDDING_PROVIDER")
    if not embedding_model_configured:
        missing.append("EMBEDDING_MODEL_NAME")
    if not embedding_api_key_configured:
        missing.append("EMBEDDING_API_KEY")

    status = "ready" if not missing else "blocked"
    reason = "ready_for_real_vision_redescription" if not missing else "missing:" + ",".join(missing)
    return Phase46RedescribeReadiness(
        render_manifest=manifest_path.as_posix(),
        total_rows=counts["total"],
        pending_images=counts["pending"],
        existing_images=counts["existing"],
        failed_images=counts["failed"],
        vision_provider_configured=vision_provider_configured,
        vision_model_configured=vision_model_configured,
        vision_base_url_configured=vision_base_url_configured,
        vision_api_key_configured=vision_api_key_configured,
        vision_provider_is_real=vision_provider_is_real,
        phase45_route_vision_configured=phase45_route_vision_configured,
        configured_vision_routes=configured_routes,
        missing_vision_route_key_envs=missing_route_key_envs,
        embedding_provider_configured=embedding_provider_configured,
        embedding_model_configured=embedding_model_configured,
        embedding_api_key_configured=embedding_api_key_configured,
        status=status,
        reason=reason,
        next_command=(
            "python scripts\\process_multimodal_to_staging.py "
            "--image-manifest data\\evaluation\\phase46_rendered_image_manifest.csv "
            "--workers 5 --vision-provider openai-compatible --vision-model-name GLM-4.6V "
            "--vision-api-key-env OFFICIAL_GLM_KEY --vision-base-url https://open.bigmodel.cn/api/paas/v4 "
            "--provider-label official_new_a --output-dir data\\evaluation\\phase46_redescribe_staging"
        ),
    )


def parse_vision_route_specs(values: list[str]) -> tuple[tuple[str, str, str, str, str], ...]:
    route_specs: list[tuple[str, str, str, str, str]] = []
    for value in values:
        parts = [part.strip() for part in value.split(",", 4)]
        if len(parts) != 5 or not all(parts):
            raise ValueError("--vision-route must be label,provider,model,key_env,base_url")
        route_specs.append((parts[0], parts[1], parts[2], parts[3], parts[4]))
    return tuple(route_specs)


def inspect_vision_routes(route_specs: tuple[tuple[str, str, str, str, str], ...]) -> tuple[list[str], list[str]]:
    configured_routes: list[str] = []
    missing_key_envs: set[str] = set()
    for label, _provider, _model, key_env, _base_url in route_specs:
        if os.environ.get(key_env, "").strip():
            configured_routes.append(label)
        else:
            missing_key_envs.add(key_env)
    return configured_routes, sorted(missing_key_envs)


def count_manifest_statuses(manifest_path: Path) -> dict[str, int]:
    counts = {"total": 0, "pending": 0, "existing": 0, "failed": 0}
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            counts["total"] += 1
            status = (row.get("status") or "").strip()
            if status in counts:
                counts[status] += 1
    return counts


if __name__ == "__main__":
    main()

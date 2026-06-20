import csv
from pathlib import Path

from scripts import check_phase46_redescribe_readiness as readiness


class FakeSettings:
    vision_model_provider = ""
    vision_model_name = ""
    vision_model_base_url = ""
    vision_model_api_key = ""
    embedding_provider = "paratera"
    embedding_model_name = "GLM-Embedding-3"
    embedding_api_key = "secret-key"


def test_readiness_blocks_when_real_vision_config_is_missing(tmp_path: Path, monkeypatch) -> None:
    manifest = write_manifest(tmp_path, ["pending", "pending"])
    monkeypatch.setattr(readiness, "get_settings", lambda: FakeSettings())
    monkeypatch.delenv("OFFICIAL_GLM_KEY", raising=False)
    monkeypatch.delenv("PARATERA_GLM_KEY", raising=False)

    report = readiness.build_readiness_report(manifest)

    assert report.status == "blocked"
    assert report.pending_images == 2
    assert "real_vision_route_or_unified_vision_config" in report.reason
    assert "secret-key" not in str(report)


def test_readiness_is_ready_with_real_vision_and_embedding_config(tmp_path: Path, monkeypatch) -> None:
    manifest = write_manifest(tmp_path, ["pending", "existing"])
    monkeypatch.delenv("OFFICIAL_GLM_KEY", raising=False)
    monkeypatch.delenv("PARATERA_GLM_KEY", raising=False)

    class RealSettings(FakeSettings):
        vision_model_provider = "openai-compatible"
        vision_model_name = "glm-4.6v"
        vision_model_base_url = "https://example.invalid/v1"
        vision_model_api_key = "vision-secret"

    monkeypatch.setattr(readiness, "get_settings", lambda: RealSettings())

    report = readiness.build_readiness_report(manifest)

    assert report.status == "ready"
    assert report.pending_images == 1
    assert report.existing_images == 1
    assert report.vision_provider_is_real is True
    assert "vision-secret" not in str(report)


def test_readiness_accepts_phase45_route_env_without_unified_vision(tmp_path: Path, monkeypatch) -> None:
    manifest = write_manifest(tmp_path, ["pending"])
    monkeypatch.setattr(readiness, "get_settings", lambda: FakeSettings())
    monkeypatch.setenv("OFFICIAL_GLM_KEY", "route-secret")
    monkeypatch.delenv("PARATERA_GLM_KEY", raising=False)

    report = readiness.build_readiness_report(manifest)

    assert report.status == "ready"
    assert report.phase45_route_vision_configured is True
    assert report.configured_vision_routes == [
        "official_new_a",
        "official_new_b",
        "official_old_a",
        "official_old_b",
    ]
    assert report.missing_vision_route_key_envs == ["PARATERA_GLM_KEY"]
    assert "route-secret" not in str(report)


def test_readiness_accepts_custom_route_env_names(tmp_path: Path, monkeypatch) -> None:
    manifest = write_manifest(tmp_path, ["pending"])
    route_specs = readiness.parse_vision_route_specs(
        ["custom_a,openai-compatible,GLM-4.6V,CUSTOM_VISION_A,https://example.invalid/v1"]
    )
    monkeypatch.setattr(readiness, "get_settings", lambda: FakeSettings())
    monkeypatch.setenv("CUSTOM_VISION_A", "custom-secret")
    monkeypatch.delenv("OFFICIAL_GLM_KEY", raising=False)
    monkeypatch.delenv("PARATERA_GLM_KEY", raising=False)

    report = readiness.build_readiness_report(manifest, route_specs=route_specs)

    assert report.status == "ready"
    assert report.configured_vision_routes == ["custom_a"]
    assert report.missing_vision_route_key_envs == []
    assert "custom-secret" not in str(report)


def write_manifest(tmp_path: Path, statuses: list[str]) -> Path:
    manifest = tmp_path / "render_manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["status"])
        writer.writeheader()
        for status in statuses:
            writer.writerow({"status": status})
    return manifest

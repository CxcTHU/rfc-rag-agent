import csv
from pathlib import Path

from scripts.build_phase46_remaining_redescribe_manifests import build_remaining_manifests


def test_build_remaining_manifests_excludes_described_rows(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    staging_dir = tmp_path / "staging"
    output_dir = tmp_path / "remaining"
    manifest_dir.mkdir()
    (staging_dir / "route_a").mkdir(parents=True)

    write_csv(
        manifest_dir / "route_a.csv",
        ["source_image_path", "status"],
        [
            {"source_image_path": "a.png", "status": "pending"},
            {"source_image_path": "b.png", "status": "pending"},
            {"source_image_path": "c.png", "status": "pending"},
        ],
    )
    write_csv(
        staging_dir / "route_a" / "multimodal_staging.csv",
        ["source_image_path", "status"],
        [
            {"source_image_path": "a.png", "status": "described"},
            {"source_image_path": "b.png", "status": "failed"},
        ],
    )

    counts = build_remaining_manifests(
        manifest_dir=manifest_dir,
        staging_dirs=[staging_dir],
        output_dir=output_dir,
    )

    assert counts == [("route_a", 1, 2)]
    assert read_paths(output_dir / "route_a.csv") == ["b.png", "c.png"]


def test_build_remaining_manifests_combines_multiple_staging_dirs(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "manifests"
    staging_a = tmp_path / "staging_a"
    staging_b = tmp_path / "staging_b"
    output_dir = tmp_path / "remaining"
    manifest_dir.mkdir()
    (staging_a / "route_a").mkdir(parents=True)
    (staging_b / "route_a").mkdir(parents=True)

    write_csv(
        manifest_dir / "route_a.csv",
        ["source_image_path", "status"],
        [
            {"source_image_path": "a.png", "status": "pending"},
            {"source_image_path": "b.png", "status": "pending"},
            {"source_image_path": "c.png", "status": "pending"},
        ],
    )
    write_csv(staging_a / "route_a" / "multimodal_staging.csv", ["source_image_path", "status"], [{"source_image_path": "a.png", "status": "described"}])
    write_csv(staging_b / "route_a" / "multimodal_staging.csv", ["source_image_path", "status"], [{"source_image_path": "b.png", "status": "described"}])

    counts = build_remaining_manifests(
        manifest_dir=manifest_dir,
        staging_dirs=[staging_a, staging_b],
        output_dir=output_dir,
    )

    assert counts == [("route_a", 2, 1)]
    assert read_paths(output_dir / "route_a.csv") == ["c.png"]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_paths(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row["source_image_path"] for row in csv.DictReader(file)]

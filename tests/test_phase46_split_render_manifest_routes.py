import csv
from pathlib import Path

from scripts.split_phase46_render_manifest_routes import split_manifest


def test_split_manifest_writes_pending_rows_round_robin(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["source_image_path", "status"])
        writer.writeheader()
        for index in range(5):
            writer.writerow({"source_image_path": f"image_{index}.png", "status": "pending"})
        writer.writerow({"source_image_path": "existing.png", "status": "existing"})

    counts = split_manifest(manifest, tmp_path / "out", routes=("a", "b"))

    assert counts == {"a": 3, "b": 2}
    assert read_paths(tmp_path / "out" / "a.csv") == ["image_0.png", "image_2.png", "image_4.png"]
    assert read_paths(tmp_path / "out" / "b.csv") == ["image_1.png", "image_3.png"]


def test_split_manifest_requires_routes(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("\ufeffsource_image_path,status\nimage.png,pending\n", encoding="utf-8")

    try:
        split_manifest(manifest, tmp_path / "out", routes=())
    except ValueError as exc:
        assert "at least one route" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def read_paths(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row["source_image_path"] for row in csv.DictReader(file)]

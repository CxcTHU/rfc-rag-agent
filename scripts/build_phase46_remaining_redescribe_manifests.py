"""Build remaining Phase 46 redescription manifests from partial staging outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_MANIFEST_DIR = Path("data/evaluation/phase46_redescribe_manifests")
DEFAULT_STAGING_DIR = Path("data/evaluation/phase46_redescribe_staging")
DEFAULT_OUTPUT_DIR = Path("data/evaluation/phase46_redescribe_remaining_manifests")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build remaining manifests after partial Phase 46 staging.")
    parser.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    parser.add_argument("--staging-dir", action="append", default=[], help="Staging output directory. May be repeated.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    counts = build_remaining_manifests(
        manifest_dir=Path(args.manifest_dir),
        staging_dirs=[Path(path) for path in args.staging_dir] or [DEFAULT_STAGING_DIR],
        output_dir=Path(args.output_dir),
    )
    print("summary:", " ".join(f"{route}=done:{done},remaining:{remaining}" for route, done, remaining in counts))
    print(f"wrote {args.output_dir}")


def build_remaining_manifests(
    *,
    manifest_dir: Path,
    staging_dirs: list[Path],
    output_dir: Path,
) -> list[tuple[str, int, int]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    counts: list[tuple[str, int, int]] = []
    for manifest_path in sorted(manifest_dir.glob("*.csv")):
        route = manifest_path.stem
        done_paths: set[str] = set()
        for staging_dir in staging_dirs:
            done_paths.update(read_described_paths(staging_dir / route / "multimodal_staging.csv"))
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            fieldnames = list(reader.fieldnames or [])
            remaining_rows = [
                row
                for row in reader
                if (row.get("source_image_path") or "").strip() not in done_paths
            ]
        if not fieldnames:
            raise ValueError(f"manifest header is empty: {manifest_path}")
        output_path = output_dir / manifest_path.name
        with output_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(remaining_rows)
        counts.append((route, len(done_paths), len(remaining_rows)))
    return counts


def read_described_paths(staging_csv: Path) -> set[str]:
    if not staging_csv.exists():
        return set()
    with staging_csv.open("r", encoding="utf-8-sig", newline="") as file:
        return {
            (row.get("source_image_path") or "").strip()
            for row in csv.DictReader(file)
            if row.get("status") == "described" and (row.get("source_image_path") or "").strip()
        }


if __name__ == "__main__":
    main()

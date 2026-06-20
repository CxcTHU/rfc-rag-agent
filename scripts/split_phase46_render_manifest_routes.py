"""Split the Phase 46 rendered-image manifest into route shards."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_MANIFEST = Path("data/evaluation/phase46_rendered_image_manifest.csv")
DEFAULT_OUTPUT_DIR = Path("data/evaluation/phase46_redescribe_manifests")
DEFAULT_ROUTES = ("official_a_1", "official_a_2", "official_b_1", "official_b_2", "paratera_c")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split Phase 46 rendered image manifest across vision routes.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--routes", default=",".join(DEFAULT_ROUTES))
    args = parser.parse_args()

    routes = tuple(route.strip() for route in args.routes.split(",") if route.strip())
    counts = split_manifest(Path(args.manifest), Path(args.output_dir), routes)
    print("summary:", " ".join(f"{route}={count}" for route, count in counts.items()))
    print(f"wrote {args.output_dir}")


def split_manifest(manifest_path: Path, output_dir: Path, routes: tuple[str, ...] = DEFAULT_ROUTES) -> dict[str, int]:
    if not routes:
        raise ValueError("at least one route is required")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        rows = [row for row in reader if (row.get("status") or "").strip() == "pending"]
    if not fieldnames:
        raise ValueError("manifest header is empty")

    output_dir.mkdir(parents=True, exist_ok=True)
    shards = {route: [] for route in routes}
    for index, row in enumerate(rows):
        shards[routes[index % len(routes)]].append(row)

    counts: dict[str, int] = {}
    for route, route_rows in shards.items():
        path = output_dir / f"{route}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(route_rows)
        counts[route] = len(route_rows)
    return counts


if __name__ == "__main__":
    main()

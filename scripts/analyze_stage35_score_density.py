from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.score_stage30_quality import read_rows, to_float  # noqa: E402


DEFAULT_SCORES = ROOT / "data" / "evaluation" / "stage30_quality_scores.csv"
DEFAULT_DEDUCTIONS = ROOT / "data" / "evaluation" / "stage30_quality_deductions.csv"
DEFAULT_OUT = ROOT / "data" / "evaluation" / "stage35_score_density.csv"
TARGET_SCORE = 88.0

DENSITY_FIELDS = [
    "scope",
    "query_id",
    "dimension",
    "deduction_points",
    "deduction_count",
    "share_of_total_deductions",
    "current_overall_score",
    "target_overall_score",
    "points_needed_to_target",
    "enough_if_fully_recovered",
    "recommended_priority",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Stage 35 score density from Stage 30 deductions.")
    parser.add_argument("--scores", default=str(DEFAULT_SCORES))
    parser.add_argument("--deductions", default=str(DEFAULT_DEDUCTIONS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--target-score", type=float, default=TARGET_SCORE)
    return parser.parse_args()


def latest_score(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        raise ValueError("stage30 quality scores are empty")
    return rows[-1]


def build_density_rows(
    score: dict[str, str],
    deductions: list[dict[str, str]],
    target_score: float,
) -> list[dict[str, str]]:
    current_score = to_float(score.get("overall_score"))
    points_needed = max(0.0, target_score - current_score)
    total_deductions = sum(to_float(row.get("deduction_points")) for row in deductions)

    rows: list[dict[str, str]] = []
    by_query_dimension: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_query: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_dimension: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in deductions:
        query_id = row.get("query_id", "")
        dimension = row.get("dimension", "")
        by_query_dimension[(query_id, dimension)].append(row)
        by_query[query_id].append(row)
        by_dimension[dimension].append(row)

    for (query_id, dimension), grouped in sorted(by_query_dimension.items()):
        rows.append(
            density_row(
                scope="query_dimension",
                query_id=query_id,
                dimension=dimension,
                grouped=grouped,
                total_deductions=total_deductions,
                current_score=current_score,
                target_score=target_score,
                points_needed=points_needed,
            )
        )
    for query_id, grouped in sorted(by_query.items()):
        rows.append(
            density_row(
                scope="query_total",
                query_id=query_id,
                dimension="all",
                grouped=grouped,
                total_deductions=total_deductions,
                current_score=current_score,
                target_score=target_score,
                points_needed=points_needed,
            )
        )
    for dimension, grouped in sorted(by_dimension.items()):
        rows.append(
            density_row(
                scope="dimension_total",
                query_id="all",
                dimension=dimension,
                grouped=grouped,
                total_deductions=total_deductions,
                current_score=current_score,
                target_score=target_score,
                points_needed=points_needed,
            )
        )

    rows.append(
        {
            "scope": "overall_gap",
            "query_id": "all",
            "dimension": "all",
            "deduction_points": format_number(total_deductions),
            "deduction_count": str(len(deductions)),
            "share_of_total_deductions": "1.000" if total_deductions else "0.000",
            "current_overall_score": format_number(current_score),
            "target_overall_score": format_number(target_score),
            "points_needed_to_target": format_number(points_needed),
            "enough_if_fully_recovered": str(total_deductions >= points_needed).lower(),
            "recommended_priority": overall_recommendation(total_deductions, points_needed, deductions),
        }
    )
    return rows


def density_row(
    *,
    scope: str,
    query_id: str,
    dimension: str,
    grouped: list[dict[str, str]],
    total_deductions: float,
    current_score: float,
    target_score: float,
    points_needed: float,
) -> dict[str, str]:
    deduction_points = sum(to_float(row.get("deduction_points")) for row in grouped)
    share = deduction_points / total_deductions if total_deductions else 0.0
    enough = deduction_points >= points_needed and points_needed > 0
    return {
        "scope": scope,
        "query_id": query_id,
        "dimension": dimension,
        "deduction_points": format_number(deduction_points),
        "deduction_count": str(len(grouped)),
        "share_of_total_deductions": f"{share:.3f}",
        "current_overall_score": format_number(current_score),
        "target_overall_score": format_number(target_score),
        "points_needed_to_target": format_number(points_needed),
        "enough_if_fully_recovered": str(enough).lower(),
        "recommended_priority": priority_label(deduction_points, points_needed, share),
    }


def priority_label(deduction_points: float, points_needed: float, share: float) -> str:
    if points_needed <= 0:
        return "already_at_target"
    if deduction_points >= points_needed:
        return "single_item_can_reach_target"
    if share >= 0.5:
        return "largest_cluster_but_insufficient_alone"
    return "small_distributed_deduction"


def overall_recommendation(total_deductions: float, points_needed: float, deductions: list[dict[str, str]]) -> str:
    if points_needed <= 0:
        return "already_at_target"
    if not deductions:
        return "no_recorded_deductions; inspect scoring formula and source summaries"
    if total_deductions < points_needed:
        return "recorded_deductions_cannot_explain_gap; inspect scoring formula and aggregate metric ceilings"
    return "recorded_deductions_can_cover_gap_if_recovered"


def format_number(value: float) -> str:
    return f"{value:.2f}"


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DENSITY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    score = latest_score(read_rows(Path(args.scores)))
    deductions = read_rows(Path(args.deductions))
    rows = build_density_rows(score, deductions, args.target_score)
    write_csv(Path(args.out), rows)
    gap = max(0.0, args.target_score - to_float(score.get("overall_score")))
    total = sum(to_float(row.get("deduction_points")) for row in deductions)
    print(
        "stage35 score density "
        f"current={to_float(score.get('overall_score')):.2f} "
        f"target={args.target_score:.2f} "
        f"gap={gap:.2f} "
        f"recorded_deductions={total:.2f} "
        f"rows={len(rows)}"
    )


if __name__ == "__main__":
    main()

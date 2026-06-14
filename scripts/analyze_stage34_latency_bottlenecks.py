from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.collect_stage34_latency_traces import TRACE_FIELDS, numeric  # noqa: E402


INPUT_PATH = ROOT / "data" / "evaluation" / "stage34_latency_traces.csv"
SUMMARY_PATH = ROOT / "data" / "evaluation" / "stage34_latency_bottleneck_summary.csv"
REPORT_PATH = ROOT / "docs" / "stage34_latency_bottleneck_report.md"

SUMMARY_FIELDS = [
    "group",
    "completed_count",
    "error_count",
    "time_to_final_mean_ms",
    "time_to_final_p50_ms",
    "time_to_final_p90_ms",
    "time_to_final_max_ms",
    "dominant_bottleneck",
    "dominant_bottleneck_count",
    "top_stage_by_share",
    "top_stage_share",
    *[f"{field}_mean" for field in TRACE_FIELDS],
]

SHARE_FIELDS = [
    "query_embedding_latency_ms",
    "vector_search_latency_ms",
    "faiss_search_latency_ms",
    "numpy_search_latency_ms",
    "rerank_latency_ms",
    "planner_latency_ms",
    "tool_latency_ms",
    "answer_latency_ms",
    "time_to_first_token_ms",
]


def main() -> None:
    args = parse_args()
    rows = read_rows(Path(args.input))
    summaries = build_summaries(rows)
    write_summary(Path(args.out_summary), summaries)
    write_report(Path(args.out_report), summaries, rows)
    print(f"wrote {args.out_summary}")
    print(f"wrote {args.out_report}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze stage 34 latency bottlenecks.")
    parser.add_argument("--input", default=str(INPUT_PATH))
    parser.add_argument("--out-summary", default=str(SUMMARY_PATH))
    parser.add_argument("--out-report", default=str(REPORT_PATH))
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_summaries(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: list[tuple[str, list[dict[str, str]]]] = [
        ("all", rows),
        ("default", [row for row in rows if row.get("mode") == "default"]),
        ("react_agent", [row for row in rows if row.get("mode") == "react_agent"]),
        ("chat", [row for row in rows if row.get("mode") == "chat"]),
    ]
    return [summarize_group(name, group_rows) for name, group_rows in groups if group_rows]


def summarize_group(group: str, rows: list[dict[str, str]]) -> dict[str, object]:
    completed = [row for row in rows if row.get("status") == "completed"]
    errors = [row for row in rows if row.get("status") != "completed"]
    finals = [numeric(row.get("time_to_final_ms")) for row in completed]
    bottlenecks = Counter(row.get("primary_bottleneck", "") for row in completed)
    bottlenecks.pop("", None)
    dominant, dominant_count = bottlenecks.most_common(1)[0] if bottlenecks else ("", 0)
    stage_shares = average_stage_shares(completed)
    positive_stage_shares = {field: value for field, value in stage_shares.items() if value > 0}
    top_stage, top_share = (
        max(positive_stage_shares.items(), key=lambda item: item[1])
        if positive_stage_shares
        else ("", 0.0)
    )

    summary: dict[str, object] = {
        "group": group,
        "completed_count": len(completed),
        "error_count": len(errors),
        "time_to_final_mean_ms": format_float(mean(finals)),
        "time_to_final_p50_ms": format_float(percentile(finals, 50)),
        "time_to_final_p90_ms": format_float(percentile(finals, 90)),
        "time_to_final_max_ms": format_float(max(finals) if finals else 0.0),
        "dominant_bottleneck": dominant,
        "dominant_bottleneck_count": dominant_count,
        "top_stage_by_share": top_stage,
        "top_stage_share": format_float(top_share),
    }
    for field in TRACE_FIELDS:
        summary[f"{field}_mean"] = format_float(mean([numeric(row.get(field)) for row in completed]))
    return summary


def average_stage_shares(rows: list[dict[str, str]]) -> dict[str, float]:
    shares: dict[str, list[float]] = {field: [] for field in SHARE_FIELDS}
    for row in rows:
        final_ms = numeric(row.get("time_to_final_ms"))
        if final_ms <= 0:
            continue
        for field in SHARE_FIELDS:
            shares[field].append(numeric(row.get(field)) / final_ms)
    return {field: mean(values) for field, values in shares.items() if values}


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * (p / 100)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.fmean(values)


def format_float(value: float) -> str:
    return f"{value:.3f}"


def write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, summaries: list[dict[str, object]], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    all_summary = summaries[0] if summaries else {}
    lines = [
        "# 阶段 34 latency bottleneck report",
        "",
        "本报告读取 `data/evaluation/stage34_latency_traces.csv`，只分析脱敏耗时字段、状态和计数，不保存完整问题、完整答案、供应商原始响应或受限全文。",
        "",
        "## 总体结论",
        "",
        f"- completed: {all_summary.get('completed_count', 0)}",
        f"- error: {all_summary.get('error_count', 0)}",
        f"- p50 time_to_final: {all_summary.get('time_to_final_p50_ms', '0.000')} ms",
        f"- p90 time_to_final: {all_summary.get('time_to_final_p90_ms', '0.000')} ms",
        f"- max time_to_final: {all_summary.get('time_to_final_max_ms', '0.000')} ms",
        f"- dominant bottleneck: {all_summary.get('dominant_bottleneck', '')}",
        f"- top stage by average share: {all_summary.get('top_stage_by_share', '')} ({all_summary.get('top_stage_share', '0.000')})",
        "",
        "## 分组摘要",
        "",
        "| group | completed | p50_ms | p90_ms | dominant_bottleneck | top_stage_by_share | top_stage_share |",
        "| --- | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for summary in summaries:
        lines.append(
            "| {group} | {completed_count} | {time_to_final_p50_ms} | {time_to_final_p90_ms} | "
            "{dominant_bottleneck} | {top_stage_by_share} | {top_stage_share} |".format(**summary)
        )
    lines.extend(
        [
            "",
            "## 样本状态",
            "",
            "| query_id | endpoint | mode | status | primary_bottleneck | time_to_final_ms |",
            "| --- | --- | --- | --- | --- | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| {query_id} | {endpoint} | {mode} | {status} | {primary_bottleneck} | {time_to_final_ms} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## 初步建议",
            "",
            "- 如果 `answer_latency_ms` 或 `tool_latency_ms` 占比最高，优先评估 prompt 长度、chat provider 延迟和 ReAct 工具轮数。",
            "- 如果 `planner_latency_ms` 在 `react_agent` 中占比高，阶段 35 前应先考虑 planner prompt 压缩或减少规划调用。",
            "- 如果 `query_embedding_latency_ms` 高，优先检查 query embedding cache 命中率和 provider 延迟。",
            "- 如果 `rerank_latency_ms` 高，优先对比 rerank provider、recall_k 和是否需要按 query 类型启用。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

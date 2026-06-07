from __future__ import annotations

import argparse
import csv
import html
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEFAULT_DECOMPOSE_DIAGNOSTICS = Path("data/evaluation/stage16_decompose_diagnostics.csv")
DEFAULT_COVERAGE_CLOSURE = Path("data/evaluation/stage16_answer_coverage_closure.csv")
DEFAULT_SUMMARY_OUT = Path("data/evaluation/stage16_quality_closure_summary.csv")
DEFAULT_MARKDOWN_OUT = Path("docs/stage16_quality_closure_report.md")
DEFAULT_HTML_OUT = Path("app/frontend/quality_report.html")

SUMMARY_FIELDS = [
    "section",
    "metric",
    "status",
    "value",
    "baseline_value",
    "risk_before",
    "risk_after",
    "evidence_file",
    "recommendation",
]


@dataclass(frozen=True)
class Stage16QualitySummaryRow:
    section: str
    metric: str
    status: str
    value: str
    baseline_value: str
    risk_before: str
    risk_after: str
    evidence_file: str
    recommendation: str

    def to_row(self) -> dict[str, str]:
        return {
            "section": self.section,
            "metric": self.metric,
            "status": self.status,
            "value": self.value,
            "baseline_value": self.baseline_value,
            "risk_before": self.risk_before,
            "risk_after": self.risk_after,
            "evidence_file": self.evidence_file,
            "recommendation": self.recommendation,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stage-16 quality closure summary and read-only report.")
    parser.add_argument("--decompose-diagnostics", default=str(DEFAULT_DECOMPOSE_DIAGNOSTICS))
    parser.add_argument("--coverage-closure", default=str(DEFAULT_COVERAGE_CLOSURE))
    parser.add_argument("--summary-out", default=str(DEFAULT_SUMMARY_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--html-out", default=str(DEFAULT_HTML_OUT))
    args = parser.parse_args()

    rows = build_quality_closure_summary(
        decompose_diagnostics_path=Path(args.decompose_diagnostics),
        coverage_closure_path=Path(args.coverage_closure),
    )
    write_summary(Path(args.summary_out), rows)
    write_markdown_report(Path(args.markdown_out), rows)
    write_html_report(Path(args.html_out), rows)
    print_summary(rows, args.summary_out, args.markdown_out, args.html_out)


def build_quality_closure_summary(
    *,
    decompose_diagnostics_path: Path = DEFAULT_DECOMPOSE_DIAGNOSTICS,
    coverage_closure_path: Path = DEFAULT_COVERAGE_CLOSURE,
) -> list[Stage16QualitySummaryRow]:
    diagnostics = read_csv_rows(decompose_diagnostics_path) if decompose_diagnostics_path.exists() else []
    closures = read_csv_rows(coverage_closure_path) if coverage_closure_path.exists() else []
    rows: list[Stage16QualitySummaryRow] = []
    rows.extend(decompose_summary_rows(diagnostics, decompose_diagnostics_path))
    rows.extend(coverage_summary_rows(closures, coverage_closure_path))
    rows.append(overall_quality_gate(rows))
    return rows


def decompose_summary_rows(
    diagnostics: list[dict[str, str]],
    diagnostics_path: Path,
) -> list[Stage16QualitySummaryRow]:
    if not diagnostics:
        return [
            Stage16QualitySummaryRow(
                section="decompose",
                metric="real_config_diagnostic",
                status="missing",
                value="0",
                baseline_value="stage15 real_config/decompose=error",
                risk_before="high",
                risk_after="high",
                evidence_file=str(diagnostics_path),
                recommendation="生成阶段 16 decompose diagnostics，不能用 deterministic baseline 掩盖真实错误。",
            )
        ]
    rows: list[Stage16QualitySummaryRow] = []
    for diagnostic in diagnostics:
        blocking_status = diagnostic.get("blocking_status", "")
        risk_after = risk_for_blocking_status(blocking_status)
        rows.append(
            Stage16QualitySummaryRow(
                section="decompose",
                metric=diagnostic.get("suite", "decompose"),
                status=diagnostic.get("status_after", ""),
                value=diagnostic.get("root_cause", ""),
                baseline_value=f"stage15 status={diagnostic.get('status_before', '')}",
                risk_before="high" if diagnostic.get("status_before", "") == "error" else "medium",
                risk_after=risk_after,
                evidence_file=str(diagnostics_path),
                recommendation=diagnostic.get("next_action", ""),
            )
        )
    return rows


def coverage_summary_rows(
    closures: list[dict[str, str]],
    closure_path: Path,
) -> list[Stage16QualitySummaryRow]:
    if not closures:
        return [
            Stage16QualitySummaryRow(
                section="answer_coverage",
                metric="closure_rows",
                status="missing",
                value="0",
                baseline_value="stage15 high/medium rows",
                risk_before="high",
                risk_after="high",
                evidence_file=str(closure_path),
                recommendation="生成阶段 16 Answer Coverage 闭环表。",
            )
        ]
    before_counts = count_by(closures, "risk_before")
    after_counts = count_by(closures, "risk_after")
    rows = [
        Stage16QualitySummaryRow(
            section="answer_coverage",
            metric="closure_rows",
            status="completed",
            value=str(len(closures)),
            baseline_value=f"before high={before_counts.get('high', 0)}, medium={before_counts.get('medium', 0)}",
            risk_before=highest_risk(before_counts),
            risk_after=highest_risk(after_counts),
            evidence_file=str(closure_path),
            recommendation="阶段 16 已为 high/medium 样例补充 risk_after、root_cause、decision 和 next_action。",
        )
    ]
    for risk_level in ["high", "medium", "low"]:
        rows.append(
            Stage16QualitySummaryRow(
                section="answer_coverage",
                metric=f"risk_after_{risk_level}",
                status="completed",
                value=str(after_counts.get(risk_level, 0)),
                baseline_value="stage15 risk_before high/medium",
                risk_before=highest_risk(before_counts),
                risk_after=risk_level if after_counts.get(risk_level, 0) else "low",
                evidence_file=str(closure_path),
                recommendation=recommendation_for_coverage_risk(risk_level, after_counts.get(risk_level, 0)),
            )
        )
    return rows


def overall_quality_gate(rows: list[Stage16QualitySummaryRow]) -> Stage16QualitySummaryRow:
    after_counts = count_risks(row.risk_after for row in rows)
    highest = highest_risk(after_counts)
    status = "review_required" if highest == "high" else f"closure_ready/{highest}"
    recommendation = recommendation_for_overall_gate(rows, highest)
    return Stage16QualitySummaryRow(
        section="overall",
        metric="stage16_quality_gate",
        status=status,
        value=highest,
        baseline_value="stage15 overall=review_required/high",
        risk_before="high",
        risk_after=highest,
        evidence_file=f"{DEFAULT_SUMMARY_OUT}",
        recommendation=recommendation,
    )


def recommendation_for_overall_gate(rows: list[Stage16QualitySummaryRow], highest: str) -> str:
    if highest != "high":
        return "阶段 16 质量风险已进入可接受闭环状态，可由用户人工核验后决定提交。"
    high_sections = {row.section for row in rows if row.risk_after == "high"}
    if high_sections == {"answer_coverage"}:
        return "real decompose 已完成阶段 16 显式重试；当前剩余 high 阻断来自 Answer Coverage 样例，需要人工核验或重跑真实回答。"
    if "decompose" in high_sections:
        return "阶段 16 已完成风险分类和部分降级，但 real decompose 仍有 high 阻断项，需要人工核验后决定是否重试真实 provider。"
    return "阶段 16 已完成风险分类和部分降级，但仍有 high 阻断项，需要用户人工核验。"


def risk_for_blocking_status(blocking_status: str) -> str:
    if blocking_status in {"not_blocking"}:
        return "low"
    if blocking_status in {"manual_retry_required", "manual_configuration_required", "review_required"}:
        return "high"
    return "medium"


def recommendation_for_coverage_risk(risk_level: str, count: int) -> str:
    if risk_level == "high":
        return "仍有 high 样例，通常是超时、无答案或证据不足；必须人工核验。" if count else "high 样例已清零。"
    if risk_level == "medium":
        return "medium 样例保留为人工审阅项，通常是来源细节不足。" if count else "medium 样例已清零。"
    return "low 样例可作为阶段 16 闭环通过证据。" if count else "没有 low 闭环样例。"


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get(field, "").strip() or "blank"
        counts[key] = counts.get(key, 0) + 1
    return counts


def count_risks(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value).strip() or "blank"
        counts[key] = counts.get(key, 0) + 1
    return counts


def highest_risk(counts: dict[str, int]) -> str:
    if counts.get("high", 0):
        return "high"
    if counts.get("medium", 0):
        return "medium"
    return "low"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_summary(path: Path, rows: list[Stage16QualitySummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_row())


def write_markdown_report(path: Path, rows: list[Stage16QualitySummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 阶段 16 质量风险闭环报告",
        "",
        "本报告由 `scripts/build_stage16_quality_closure_report.py` 生成，只读汇总阶段 16 风险闭环表，不触发真实 API 调用。",
        "",
        "| Section | Metric | Status | Value | Baseline | Risk Before | Risk After | Recommendation |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.section,
                    row.metric,
                    row.status,
                    row.value,
                    row.baseline_value,
                    row.risk_before,
                    row.risk_after,
                    row.recommendation,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 数据安全边界",
            "",
            "- 报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。",
            "- 阶段 16 只读取本地脱敏 CSV 质量产物。",
            "- 阶段 16 收尾等待用户人工核验，当前不提交、不打 tag、不推送。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html_report(path: Path, rows: list[Stage16QualitySummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.section)}</td>"
        f"<td>{html.escape(row.metric)}</td>"
        f"<td>{html.escape(row.status)}</td>"
        f"<td>{html.escape(row.value)}</td>"
        f"<td>{html.escape(row.baseline_value)}</td>"
        f"<td>{html.escape(row.risk_before)}</td>"
        f"<td>{html.escape(row.risk_after)}</td>"
        f"<td>{html.escape(row.recommendation)}</td>"
        "</tr>"
        for row in rows
    )
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>阶段 16 质量风险闭环报告</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <main class="app-shell quality-report">
    <section class="hero">
      <div>
        <p class="eyebrow">只读质量报告</p>
        <h1>阶段 16 质量风险闭环报告</h1>
        <p class="hero-copy">汇总 real decompose 诊断、Answer Coverage 闭环和 quality gate，不触发真实 API 调用。</p>
      </div>
      <a class="secondary-link" href="/">返回工作台</a>
    </section>
    <section class="panel">
      <h2>质量闭环汇总</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Section</th>
              <th>Metric</th>
              <th>Status</th>
              <th>Value</th>
              <th>Baseline</th>
              <th>Risk Before</th>
              <th>Risk After</th>
              <th>Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {body_rows}
          </tbody>
        </table>
      </div>
    </section>
    <section class="panel">
      <h2>人工核验边界</h2>
      <ul class="compact-list">
        <li>阶段 16 当前不执行 git add、commit、tag、push 或 PR。</li>
        <li>报告只读取本地 CSV 质量产物，不调用真实模型或检索 API。</li>
        <li>真实 API key、Bearer token、供应商原始敏感响应和受限全文不得写入报告。</li>
      </ul>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def print_summary(rows: list[Stage16QualitySummaryRow], summary_out: str, markdown_out: str, html_out: str) -> None:
    risks = count_risks(row.risk_after for row in rows)
    overall = next((row for row in rows if row.section == "overall"), None)
    print(f"stage 16 quality closure summary: {len(rows)} rows")
    print("risk_after counts: " + ", ".join(f"{key}={value}" for key, value in sorted(risks.items())))
    if overall:
        print(f"quality gate: {overall.status}/{overall.value}")
    print(f"wrote summary to {summary_out}")
    print(f"wrote markdown report to {markdown_out}")
    print(f"wrote html report to {html_out}")


if __name__ == "__main__":
    main()

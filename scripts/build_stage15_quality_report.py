from __future__ import annotations

import argparse
import csv
import html
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEFAULT_COMPARISON = Path("data/evaluation/stage14_embedding_comparison.csv")
DEFAULT_REAL_STATUS = Path("data/evaluation/stage14_real/real_config_status.csv")
DEFAULT_COVERAGE_REVIEW = Path("data/evaluation/stage15_answer_coverage_review.csv")
DEFAULT_PROVENANCE_REVIEW = Path("data/evaluation/stage14_decompose_provenance_review.csv")
DEFAULT_SUMMARY_OUT = Path("data/evaluation/stage15_quality_summary.csv")
DEFAULT_MARKDOWN_OUT = Path("docs/stage15_quality_report.md")
DEFAULT_HTML_OUT = Path("app/frontend/quality_report.html")

SUMMARY_FIELDS = [
    "section",
    "metric",
    "status",
    "value",
    "baseline_value",
    "risk_level",
    "evidence_file",
    "recommendation",
]


@dataclass(frozen=True)
class QualitySummaryRow:
    section: str
    metric: str
    status: str
    value: str
    baseline_value: str
    risk_level: str
    evidence_file: str
    recommendation: str

    def to_row(self) -> dict[str, str]:
        return {
            "section": self.section,
            "metric": self.metric,
            "status": self.status,
            "value": self.value,
            "baseline_value": self.baseline_value,
            "risk_level": self.risk_level,
            "evidence_file": self.evidence_file,
            "recommendation": self.recommendation,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stage-15 quality summary and read-only report.")
    parser.add_argument("--comparison", default=str(DEFAULT_COMPARISON))
    parser.add_argument("--real-status", default=str(DEFAULT_REAL_STATUS))
    parser.add_argument("--coverage-review", default=str(DEFAULT_COVERAGE_REVIEW))
    parser.add_argument("--provenance-review", default=str(DEFAULT_PROVENANCE_REVIEW))
    parser.add_argument("--summary-out", default=str(DEFAULT_SUMMARY_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--html-out", default=str(DEFAULT_HTML_OUT))
    args = parser.parse_args()

    rows = build_quality_summary(
        comparison_path=Path(args.comparison),
        real_status_path=Path(args.real_status),
        coverage_review_path=Path(args.coverage_review),
        provenance_review_path=Path(args.provenance_review),
    )
    write_summary(Path(args.summary_out), rows)
    write_markdown_report(Path(args.markdown_out), rows)
    write_html_report(Path(args.html_out), rows)
    print_summary(rows, args.summary_out, args.markdown_out, args.html_out)


def build_quality_summary(
    *,
    comparison_path: Path = DEFAULT_COMPARISON,
    real_status_path: Path = DEFAULT_REAL_STATUS,
    coverage_review_path: Path = DEFAULT_COVERAGE_REVIEW,
    provenance_review_path: Path = DEFAULT_PROVENANCE_REVIEW,
) -> list[QualitySummaryRow]:
    comparison_rows = read_csv_rows(comparison_path)
    real_status_rows = read_csv_rows(real_status_path) if real_status_path.exists() else []
    coverage_rows = read_csv_rows(coverage_review_path) if coverage_review_path.exists() else []
    provenance_rows = read_csv_rows(provenance_review_path) if provenance_review_path.exists() else []

    rows: list[QualitySummaryRow] = []
    rows.extend(real_config_summary_rows(comparison_rows, real_status_rows, comparison_path, real_status_path))
    rows.extend(coverage_summary_rows(coverage_rows, coverage_review_path))
    rows.extend(provenance_summary_rows(provenance_rows, provenance_review_path))
    rows.append(overall_conclusion_row(rows))
    return rows


def real_config_summary_rows(
    comparison_rows: list[dict[str, str]],
    real_status_rows: list[dict[str, str]],
    comparison_path: Path,
    real_status_path: Path,
) -> list[QualitySummaryRow]:
    by_config_suite = {
        (row.get("config_name", ""), row.get("suite", "")): row
        for row in comparison_rows
    }
    status_by_suite = {row.get("suite", ""): row for row in real_status_rows}
    suites = sorted({suite for _, suite in by_config_suite if suite} | set(status_by_suite))
    rows: list[QualitySummaryRow] = []
    for suite in suites:
        real_row = by_config_suite.get(("real_config", suite), {})
        baseline_row = by_config_suite.get(("deterministic_baseline", suite), {})
        status = real_row.get("status") or status_by_suite.get(suite, {}).get("status", "missing")
        value = pass_value(real_row)
        baseline_value = pass_value(baseline_row)
        rows.append(
            QualitySummaryRow(
                section="real_config",
                metric=suite,
                status=status,
                value=value,
                baseline_value=baseline_value,
                risk_level=risk_for_real_status(status, value, baseline_value),
                evidence_file=f"{comparison_path}; {real_status_path}",
                recommendation=recommendation_for_real_suite(suite, status, value, baseline_value),
            )
        )
    return rows


def coverage_summary_rows(
    coverage_rows: list[dict[str, str]],
    coverage_review_path: Path,
) -> list[QualitySummaryRow]:
    if not coverage_rows:
        return [
            QualitySummaryRow(
                section="answer_coverage",
                metric="review_rows",
                status="missing",
                value="0",
                baseline_value="",
                risk_level="high",
                evidence_file=str(coverage_review_path),
                recommendation="生成阶段 15 Answer Coverage 复核表。",
            )
        ]
    counts = count_by(coverage_rows, "risk_level")
    rows = [
        QualitySummaryRow(
            section="answer_coverage",
            metric="review_rows",
            status="completed",
            value=str(len(coverage_rows)),
            baseline_value="stage14 medium/review rows",
            risk_level="medium" if counts.get("high", 0) == 0 else "high",
            evidence_file=str(coverage_review_path),
            recommendation="将 high 样例作为发布前阻断风险，将 medium 样例保留为人工审阅样例。",
        )
    ]
    for risk_level, count in sorted(counts.items()):
        rows.append(
            QualitySummaryRow(
                section="answer_coverage",
                metric=f"risk_{risk_level}",
                status="completed",
                value=str(count),
                baseline_value="",
                risk_level=risk_level,
                evidence_file=str(coverage_review_path),
                recommendation=recommendation_for_coverage_risk(risk_level),
            )
        )
    return rows


def provenance_summary_rows(
    provenance_rows: list[dict[str, str]],
    provenance_review_path: Path,
) -> list[QualitySummaryRow]:
    if not provenance_rows:
        return [
            QualitySummaryRow(
                section="provenance",
                metric="evidence_rows",
                status="missing",
                value="0",
                baseline_value="",
                risk_level="medium",
                evidence_file=str(provenance_review_path),
                recommendation="生成 Decompose provenance 可读化表。",
            )
        ]
    both_match = sum(1 for row in provenance_rows if parse_bool(row.get("both_match", "")))
    decomposed = sum(1 for row in provenance_rows if parse_bool(row.get("decompose_applied", "")))
    return [
        QualitySummaryRow(
            section="provenance",
            metric="evidence_rows",
            status="completed",
            value=str(len(provenance_rows)),
            baseline_value="50 stage14 evidence rows",
            risk_level="low",
            evidence_file=str(provenance_review_path),
            recommendation="保留证据级 provenance 作为人工审阅和报告依据。",
        ),
        QualitySummaryRow(
            section="provenance",
            metric="both_match_rows",
            status="completed",
            value=str(both_match),
            baseline_value="37 stage14 both-match rows",
            risk_level="low" if both_match else "medium",
            evidence_file=str(provenance_review_path),
            recommendation="both_match 越多，说明 keyword/vector 双路证据更一致。",
        ),
        QualitySummaryRow(
            section="provenance",
            metric="decomposed_evidence_rows",
            status="completed",
            value=str(decomposed),
            baseline_value="15 stage14 decomposed rows",
            risk_level="low" if decomposed else "medium",
            evidence_file=str(provenance_review_path),
            recommendation="保留 decomposed evidence rows 解释复杂问题证据来源。",
        ),
    ]


def overall_conclusion_row(rows: list[QualitySummaryRow]) -> QualitySummaryRow:
    risk_order = {"low": 0, "medium": 1, "high": 2, "skipped": 1}
    highest = max((row.risk_level for row in rows), key=lambda risk: risk_order.get(risk, 1), default="medium")
    status = "review_required" if highest in {"medium", "high"} else "completed"
    recommendation = (
        "阶段 15 已形成真实配置和回答复核报告；发布前优先处理 high 风险和真实 decompose error。"
        if highest == "high"
        else "阶段 15 质量状态可读，后续继续人工复核 medium 样例。"
    )
    return QualitySummaryRow(
        section="overall",
        metric="stage15_quality_gate",
        status=status,
        value=highest,
        baseline_value="stage14 quality tables",
        risk_level=highest,
        evidence_file=f"{DEFAULT_SUMMARY_OUT}",
        recommendation=recommendation,
    )


def pass_value(row: dict[str, str]) -> str:
    if not row:
        return ""
    passed = row.get("passed", "")
    total = row.get("total", "")
    pass_rate = row.get("pass_rate", "")
    if passed and total:
        return f"{passed}/{total}" + (f" ({pass_rate})" if pass_rate else "")
    return ""


def risk_for_real_status(status: str, value: str, baseline_value: str) -> str:
    if status == "error":
        return "high"
    if status in {"skipped", "missing", "missing_results"}:
        return "medium"
    if value and baseline_value and value.split(" ")[0] != baseline_value.split(" ")[0]:
        return "medium"
    return "low"


def recommendation_for_real_suite(suite: str, status: str, value: str, baseline_value: str) -> str:
    if status == "error":
        return f"优先排查 {suite} 真实配置错误；不要用 deterministic 结果伪造成真实通过。"
    if status in {"skipped", "missing", "missing_results"}:
        return f"补齐 {suite} 真实结果或保留 skipped 作为发布前风险。"
    if value and baseline_value and value.split(" ")[0] != baseline_value.split(" ")[0]:
        return f"{suite} 真实结果与 deterministic baseline 不同，保留差异用于人工审阅。"
    return f"{suite} 真实配置结果可作为发布前校准证据。"


def recommendation_for_coverage_risk(risk_level: str) -> str:
    if risk_level == "high":
        return "发布前优先处理 high 风险回答，通常是超时、无答案或来源不匹配。"
    if risk_level == "medium":
        return "保留 medium 样例进入人工审阅，检查回答是否真正覆盖期望要点。"
    return "低风险样例可作为真实回答质量通过证据。"


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get(field, "").strip() or "blank"
        counts[key] = counts.get(key, 0) + 1
    return counts


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def parse_bool(value: str) -> bool:
    return value.strip().casefold() in {"yes", "true", "1", "y", "pass", "passed"}


def write_summary(path: Path, rows: list[QualitySummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_row())


def write_markdown_report(path: Path, rows: list[QualitySummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 阶段 15 质量审阅报告",
        "",
        "本报告由 `scripts/build_stage15_quality_report.py` 生成，只读汇总阶段 14/15 质量表，不触发真实 API 调用。",
        "",
        "| Section | Metric | Status | Value | Baseline | Risk | Recommendation |",
        "|---|---|---|---|---|---|---|",
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
                    row.risk_level,
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
            "- 真实回答只以脱敏摘要和指标进入审阅表。",
            "- `obsidian-vault/` 仍作为本地知识库，不纳入 Git 提交。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html_report(path: Path, rows: list[QualitySummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.section)}</td>"
        f"<td>{html.escape(row.metric)}</td>"
        f"<td>{html.escape(row.status)}</td>"
        f"<td>{html.escape(row.value)}</td>"
        f"<td>{html.escape(row.baseline_value)}</td>"
        f"<td>{html.escape(row.risk_level)}</td>"
        f"<td>{html.escape(row.recommendation)}</td>"
        "</tr>"
        for row in rows
    )
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>阶段 15 质量审阅报告</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <main class="app-shell quality-report">
    <section class="hero">
      <div>
        <p class="eyebrow">只读质量报告</p>
        <h1>阶段 15 质量审阅报告</h1>
        <p class="hero-copy">汇总真实配置复跑、回答覆盖复核和 Decompose provenance 风险，不触发真实 API 调用。</p>
      </div>
      <a class="secondary-link" href="/">返回工作台</a>
    </section>
    <section class="panel">
      <h2>质量汇总</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Section</th>
              <th>Metric</th>
              <th>Status</th>
              <th>Value</th>
              <th>Baseline</th>
              <th>Risk</th>
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
      <h2>数据安全边界</h2>
      <ul class="compact-list">
        <li>报告只读取本地 CSV 质量产物，不调用真实模型或检索 API。</li>
        <li>报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。</li>
        <li>真实回答只以脱敏摘要和指标进入审阅表。</li>
      </ul>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def print_summary(rows: list[QualitySummaryRow], summary_out: str, markdown_out: str, html_out: str) -> None:
    risks = count_by([row.to_row() for row in rows], "risk_level")
    print(f"stage 15 quality summary: {len(rows)} rows")
    print("risk counts: " + ", ".join(f"{key}={value}" for key, value in sorted(risks.items())))
    print(f"wrote summary to {summary_out}")
    print(f"wrote markdown report to {markdown_out}")
    print(f"wrote html report to {html_out}")


if __name__ == "__main__":
    main()

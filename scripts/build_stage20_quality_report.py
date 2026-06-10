"""阶段 20：quality gate 汇总与只读报告生成。

只读取阶段 20 本地脱敏 CSV，不触发真实 API、不写数据库：

    data/evaluation/stage20_eval_upgrade_summary.csv
    data/evaluation/stage20_eval_upgrade_real_jina_summary.csv
    data/evaluation/stage20_eval_upgrade_results.csv
    data/evaluation/stage20_default_chain_decision.csv

产出：
    data/evaluation/stage20_quality_summary.csv
    docs/stage20_quality_report.md
    app/frontend/quality_report.html
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_DETERMINISTIC_SUMMARY = Path("data/evaluation/stage20_eval_upgrade_summary.csv")
DEFAULT_REAL_SUMMARY = Path("data/evaluation/stage20_eval_upgrade_real_jina_summary.csv")
DEFAULT_RESULTS = Path("data/evaluation/stage20_eval_upgrade_results.csv")
DEFAULT_DECISION = Path("data/evaluation/stage20_default_chain_decision.csv")
DEFAULT_SUMMARY_OUT = Path("data/evaluation/stage20_quality_summary.csv")
DEFAULT_MARKDOWN_OUT = Path("docs/stage20_quality_report.md")
DEFAULT_HTML_OUT = Path("app/frontend/quality_report.html")

SUMMARY_FIELDS = ["section", "metric", "status", "value", "risk", "evidence_file", "recommendation"]


@dataclass(frozen=True)
class GateRow:
    section: str
    metric: str
    status: str
    value: str
    risk: str
    evidence_file: str
    recommendation: str

    def to_row(self) -> dict[str, str]:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deterministic-summary", default=str(DEFAULT_DETERMINISTIC_SUMMARY))
    parser.add_argument("--real-summary", default=str(DEFAULT_REAL_SUMMARY))
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--summary-out", default=str(DEFAULT_SUMMARY_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--html-out", default=str(DEFAULT_HTML_OUT))
    parser.add_argument(
        "--full-tests-status",
        default="pending",
        choices=("pending", "passed", "failed"),
        help="Updated in Phase 7 after full regression.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def by_config(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("config", ""): row for row in rows if row.get("config")}


def build_quality_rows(
    *,
    deterministic_summary_path: Path = DEFAULT_DETERMINISTIC_SUMMARY,
    real_summary_path: Path = DEFAULT_REAL_SUMMARY,
    results_path: Path = DEFAULT_RESULTS,
    decision_path: Path = DEFAULT_DECISION,
    full_tests_status: str = "pending",
) -> list[GateRow]:
    deterministic = by_config(read_csv(deterministic_summary_path))
    real = by_config(read_csv(real_summary_path))
    decision_rows = read_csv(decision_path)
    results = read_csv(results_path)

    rows = [
        eval_judge_row(deterministic, deterministic_summary_path),
        real_jina_row(real, real_summary_path),
        default_chain_row(decision_rows, decision_path),
        responsibility_gate_row(results, results_path),
        api_regression_row(full_tests_status),
    ]
    rows.append(overall_row(rows, full_tests_status))
    return rows


def eval_judge_row(summary: dict[str, dict[str, str]], path: Path) -> GateRow:
    baseline = summary.get("hybrid_baseline", {})
    best_candidate = best_deep_candidate(summary)
    return GateRow(
        section="eval_judge_upgrade",
        metric="coverage_ratio",
        status="completed" if baseline else "missing",
        value=(
            f"baseline p@1={baseline.get('precision_at_1', '?')}, "
            f"best_deep={best_candidate.get('config', '?')} deep_top1={best_candidate.get('deep_fulltext_top1_rate', '?')}"
        ),
        risk="low" if baseline else "high",
        evidence_file=str(path),
        recommendation=(
            "已用 expected_answer_points 的 coverage_ratio 替代题录关键词命中主判定；"
            "结果显示 deep top-1 上浮但答案覆盖 p@1 未提升。"
        ),
    )


def best_deep_candidate(summary: dict[str, dict[str, str]]) -> dict[str, str]:
    candidates = [row for config, row in summary.items() if config != "hybrid_baseline"]
    if not candidates:
        return {}
    return max(candidates, key=lambda row: parse_float(row.get("deep_fulltext_top1_rate", "")))


def real_jina_row(summary: dict[str, dict[str, str]], path: Path) -> GateRow:
    statuses = {row.get("real_config_status", "") for row in summary.values() if row.get("real_config_status", "")}
    if not summary:
        status = "missing"
        risk = "medium"
        value = "real Jina query validation missing"
        recommendation = "真实 Jina query 端校验缺失；不能用 deterministic 掩盖真实失败。"
    elif statuses == {"completed"}:
        status = "completed"
        risk = "low"
        baseline = summary.get("hybrid_baseline", {})
        value = f"completed, baseline p@1={baseline.get('precision_at_1', '?')}"
        recommendation = "真实 Jina 只在 query 端校验，复用已有 chunk embeddings；本轮无真实错误。"
    elif "error" in statuses:
        status = "error"
        risk = "high"
        value = "real Jina query validation error"
        recommendation = "真实 Jina 调用失败已显式记录；不得伪造成通过。"
    else:
        status = "skipped"
        risk = "medium"
        value = "real Jina query validation skipped"
        recommendation = "真实配置缺失时显式 skipped；补齐本地 .env 后可重跑。"
    return GateRow(
        section="real_jina_query_validation",
        metric="query_only",
        status=status,
        value=value,
        risk=risk,
        evidence_file=str(path),
        recommendation=recommendation,
    )


def default_chain_row(decisions: list[dict[str, str]], path: Path) -> GateRow:
    promoted = [row for row in decisions if row.get("final_decision") == "switch_default_candidate"]
    blockers = [
        row.get("blocker", "")
        for row in decisions
        if row.get("config") != "hybrid_baseline" and row.get("blocker")
    ]
    if promoted:
        status = "switch_default_candidate"
        risk = "medium"
        value = ",".join(row["config"] for row in promoted)
        recommendation = "候选已过门槛；需确认配置开关和回滚后再接入默认链路。"
    else:
        status = "keep_existing_hybrid"
        risk = "low"
        value = "no candidate passed delta_precision_at_1 threshold"
        recommendation = "不接入默认链路；保留 source_type_reweight 为候选/评测开关。"
    return GateRow(
        section="default_chain_decision",
        metric="source_type_reweight",
        status=status,
        value=value,
        risk=risk,
        evidence_file=str(path),
        recommendation=recommendation + (" Blockers: " + " | ".join(blockers[:3]) if blockers else ""),
    )


def responsibility_gate_row(results: list[dict[str, str]], path: Path) -> GateRow:
    target_rows = [
        row
        for row in results
        if row.get("query_id") == "cn_hq_refusal_engineering_responsibility"
    ]
    matched = [row for row in target_rows if row.get("refusal_matched") == "true" and row.get("refused") == "true"]
    if target_rows and len(matched) == len(target_rows):
        status = "closed"
        risk = "low"
        value = f"{len(matched)}/{len(target_rows)} matched"
        recommendation = "responsibility_gate 已闭环工程责任拒答遗留，且正反例测试覆盖学习题不误拒。"
    else:
        status = "review_required"
        risk = "high"
        value = f"{len(matched)}/{len(target_rows)} matched"
        recommendation = "工程责任拒答未闭环；需要检查 responsibility_gate。"
    return GateRow(
        section="responsibility_gate",
        metric="engineering_responsibility_refusal",
        status=status,
        value=value,
        risk=risk,
        evidence_file=str(path),
        recommendation=recommendation,
    )


def api_regression_row(full_tests_status: str) -> GateRow:
    if full_tests_status == "passed":
        status = "passed"
        risk = "low"
        value = "full regression passed"
        recommendation = "核心 API 与全量测试通过。"
    elif full_tests_status == "failed":
        status = "failed"
        risk = "high"
        value = "full regression failed"
        recommendation = "修复失败测试后重新生成 quality gate。"
    else:
        status = "pending"
        risk = "medium"
        value = "full regression not run yet"
        recommendation = "Phase 7 运行全量测试后用 --full-tests-status passed 重建报告。"
    return GateRow(
        section="api_regression",
        metric="core_routes_and_tests",
        status=status,
        value=value,
        risk=risk,
        evidence_file="progress.md",
        recommendation=recommendation,
    )


def overall_row(rows: list[GateRow], full_tests_status: str) -> GateRow:
    risks = [row.risk for row in rows]
    if "high" in risks:
        status = "blocked"
        risk = "high"
        value = "high"
    elif "medium" in risks:
        status = "review_required"
        risk = "medium"
        value = "medium"
    else:
        status = "pass"
        risk = "low"
        value = "low"
    recommendation = (
        "阶段 20 核心质量闭环完成；等待用户人工核验。"
        if full_tests_status == "passed" and risk == "low"
        else "阶段 20 核心评测已完成；等待 Phase 7 全量回归或人工核验。"
    )
    return GateRow(
        section="overall",
        metric="stage20_quality_gate",
        status=status,
        value=value,
        risk=risk,
        evidence_file=str(DEFAULT_SUMMARY_OUT),
        recommendation=recommendation,
    )


def parse_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def write_summary(path: Path, rows: list[GateRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_row())


def write_markdown(path: Path, rows: list[GateRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 阶段 20 质量门槛报告",
        "",
        "本报告由 `scripts/build_stage20_quality_report.py` 生成，只读汇总阶段 20 评测判定升级、真实 Jina query 校验、默认链路决策和责任边界拒答，不触发真实 API 调用。",
        "",
        "| Section | Metric | Status | Value | Risk | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join([row.section, row.metric, row.status, row.value, row.risk, row.recommendation])
            + " |"
        )
    lines.extend(
        [
            "",
            "## 数据安全边界",
            "",
            "- 报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。",
            "- 报告只读取本地脱敏 CSV，不触发真实 API、不写数据库。",
            "- 阶段 20 收尾等待用户人工核验，当前不提交、不打 tag、不推送。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(path: Path, rows: list[GateRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps([row.to_row() for row in rows], ensure_ascii=False)
    overall = next((row for row in rows if row.section == "overall"), None)
    gate_text = f"{overall.status}/{overall.value}" if overall else "unknown"
    content = HTML_TEMPLATE.replace("__DATA_JSON__", html.escape(data_json, quote=True)).replace(
        "__GATE__",
        html.escape(gate_text),
    )
    path.write_text(content, encoding="utf-8")


def print_summary(rows: list[GateRow], summary_out: str, markdown_out: str, html_out: str) -> None:
    risks: dict[str, int] = {}
    for row in rows:
        risks[row.risk] = risks.get(row.risk, 0) + 1
    overall = next((row for row in rows if row.section == "overall"), None)
    print(f"stage 20 quality gate: {len(rows)} rows")
    print("risk counts: " + ", ".join(f"{key}={value}" for key, value in sorted(risks.items())))
    if overall:
        print(f"quality gate: {overall.status}/{overall.value}")
    print(f"wrote summary to {summary_out}")
    print(f"wrote markdown to {markdown_out}")
    print(f"wrote html to {html_out}")


def main() -> None:
    args = parse_args()
    rows = build_quality_rows(
        deterministic_summary_path=Path(args.deterministic_summary),
        real_summary_path=Path(args.real_summary),
        results_path=Path(args.results),
        decision_path=Path(args.decision),
        full_tests_status=args.full_tests_status,
    )
    write_summary(Path(args.summary_out), rows)
    write_markdown(Path(args.markdown_out), rows)
    write_html(Path(args.html_out), rows)
    print_summary(rows, args.summary_out, args.markdown_out, args.html_out)


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>阶段 20 质量门槛报告</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <main class="app-shell quality-report">
    <section class="hero">
      <div>
        <p class="eyebrow">只读质量报告</p>
        <h1>阶段 20 质量门槛报告</h1>
        <p class="hero-copy">汇总评测判定升级、真实 Jina query 校验、默认链路决策与责任边界拒答。只读，不触发真实 API。</p>
        <p class="hero-copy">当前质量门槛：<strong id="gate-badge">__GATE__</strong></p>
      </div>
      <a class="secondary-link" href="/">返回工作台</a>
    </section>
    <section class="panel">
      <h2>筛选与导出</h2>
      <div class="filter-bar">
        <label>Section
          <select id="filter-section"><option value="">全部</option></select>
        </label>
        <label>Risk
          <select id="filter-risk">
            <option value="">全部</option>
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
          </select>
        </label>
        <button id="export-csv" type="button">导出 CSV</button>
        <button id="export-json" type="button">导出 JSON</button>
      </div>
    </section>
    <section class="panel">
      <h2>风险队列（high / medium）</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Section</th><th>Metric</th><th>Risk</th><th>Status</th><th>Recommendation</th></tr></thead>
          <tbody id="risk-queue"></tbody>
        </table>
      </div>
    </section>
    <section class="panel">
      <h2>质量门槛汇总</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Section</th><th>Metric</th><th>Status</th><th>Value</th><th>Risk</th><th>Recommendation</th></tr></thead>
          <tbody id="summary-body"></tbody>
        </table>
      </div>
    </section>
    <section class="panel">
      <h2>人工核验边界</h2>
      <ul class="compact-list">
        <li>阶段 20 当前不执行 git add、commit、tag、push 或 PR。</li>
        <li>报告只读取本地 CSV 质量产物，不调用真实模型或检索 API。</li>
        <li>真实 API key、Bearer token、供应商原始敏感响应和受限全文不得写入报告。</li>
      </ul>
    </section>
  </main>
  <script id="quality-data" type="application/json">__DATA_JSON__</script>
  <script>
    (function () {
      var raw = document.getElementById("quality-data").textContent || "[]";
      var rows = [];
      try { rows = JSON.parse(raw); } catch (e) { rows = []; }
      var sectionSel = document.getElementById("filter-section");
      var riskSel = document.getElementById("filter-risk");
      var sections = Array.from(new Set(rows.map(function (r) { return r.section; })));
      sections.forEach(function (s) {
        var o = document.createElement("option"); o.value = s; o.textContent = s; sectionSel.appendChild(o);
      });
      function esc(v) { var d = document.createElement("div"); d.textContent = v == null ? "" : String(v); return d.innerHTML; }
      function riskClass(r) { return "risk-" + (r || "low"); }
      function render() {
        var sf = sectionSel.value, rf = riskSel.value;
        var filtered = rows.filter(function (r) {
          return (!sf || r.section === sf) && (!rf || r.risk === rf);
        });
        document.getElementById("summary-body").innerHTML = filtered.map(function (r) {
          return "<tr class='" + riskClass(r.risk) + "'><td>" + esc(r.section) + "</td><td>" + esc(r.metric) +
            "</td><td>" + esc(r.status) + "</td><td>" + esc(r.value) + "</td><td>" + esc(r.risk) +
            "</td><td>" + esc(r.recommendation) + "</td></tr>";
        }).join("");
        var queue = rows.filter(function (r) { return r.risk === "high" || r.risk === "medium"; });
        document.getElementById("risk-queue").innerHTML = queue.length ? queue.map(function (r) {
          return "<tr class='" + riskClass(r.risk) + "'><td>" + esc(r.section) + "</td><td>" + esc(r.metric) +
            "</td><td>" + esc(r.risk) + "</td><td>" + esc(r.status) + "</td><td>" + esc(r.recommendation) + "</td></tr>";
        }).join("") : "<tr><td colspan='5'>无 high/medium 风险</td></tr>";
      }
      function download(name, text, type) {
        var blob = new Blob([text], { type: type });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a"); a.href = url; a.download = name; a.click();
        URL.revokeObjectURL(url);
      }
      document.getElementById("export-json").addEventListener("click", function () {
        download("stage20_quality_summary.json", JSON.stringify(rows, null, 2), "application/json");
      });
      document.getElementById("export-csv").addEventListener("click", function () {
        var fields = ["section", "metric", "status", "value", "risk", "recommendation"];
        var lines = [fields.join(",")];
        rows.forEach(function (r) {
          lines.push(fields.map(function (f) { return '"' + String(r[f] == null ? "" : r[f]).replace(/"/g, '""') + '"'; }).join(","));
        });
        download("stage20_quality_summary.csv", lines.join("\\n"), "text/csv");
      });
      sectionSel.addEventListener("change", render);
      riskSel.addEventListener("change", render);
      render();
    })();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

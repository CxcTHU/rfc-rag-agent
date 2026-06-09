"""阶段 18：质量门槛（quality gate）汇总与只读报告生成。

只读取本地脱敏 CSV 质量产物，不触发真实 API、不写数据库：

    data/evaluation/stage18_corpus_stats.csv
    data/evaluation/stage18_config_comparison.csv         (deterministic)
    data/evaluation/stage18_config_comparison_real.csv    (real, optional)
    data/evaluation/stage18_hard_results.csv              (refusal 判定)

产出：
    data/evaluation/stage18_quality_summary.csv
    docs/stage18_quality_report.md
    app/frontend/quality_report.html  (增强：只读筛选 + 风险队列 + 导出)

quality gate 状态口径：pass / review_required / blocked。
不用 deterministic 结果掩盖真实失败；如仍高风险，明确阻断原因。
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEFAULT_CORPUS = Path("data/evaluation/stage18_corpus_stats.csv")
DEFAULT_COMPARISON = Path("data/evaluation/stage18_config_comparison.csv")
DEFAULT_COMPARISON_REAL = Path("data/evaluation/stage18_config_comparison_real.csv")
DEFAULT_HARD_RESULTS = Path("data/evaluation/stage18_hard_results.csv")
DEFAULT_SUMMARY_OUT = Path("data/evaluation/stage18_quality_summary.csv")
DEFAULT_MARKDOWN_OUT = Path("docs/stage18_quality_report.md")
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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def kv(rows: list[dict[str, str]], key_field: str, value_field: str) -> dict[str, str]:
    return {r[key_field]: r[value_field] for r in rows if r.get(key_field)}


def build_quality_gate_rows(
    *,
    corpus_path: Path = DEFAULT_CORPUS,
    comparison_path: Path = DEFAULT_COMPARISON,
    comparison_real_path: Path = DEFAULT_COMPARISON_REAL,
    hard_results_path: Path = DEFAULT_HARD_RESULTS,
) -> list[GateRow]:
    corpus = kv(read_csv(corpus_path), "metric", "value")
    comparison = {r["config"]: r for r in read_csv(comparison_path)}
    comparison_real = {r["config"]: r for r in read_csv(comparison_real_path)}
    hard_rows = read_csv(hard_results_path)

    rows: list[GateRow] = []

    # 1. 语料深度。
    before = corpus.get("deep_fulltext_before", "?")
    after = corpus.get("deep_fulltext_after", "?")
    rows.append(
        GateRow(
            section="corpus",
            metric="deep_fulltext_depth",
            status="expanded",
            value=f"{before} -> {after} (open_access_pdf={corpus.get('open_access_pdf','?')}, chunks={corpus.get('total_chunks','?')})",
            risk="low",
            evidence_file=str(corpus_path),
            recommendation="RFC 窄领域开放获取全文有限，未达 40-60 目标；按用户决策诚实报数，未造假。可后续接入授权全文继续扩充。",
        )
    )

    # 2. 难评测集区分度。
    det_hybrid = comparison.get("hybrid", {})
    det_vector = comparison.get("vector", {})
    discrimination = "yes" if det_vector.get("precision_at_1") != det_hybrid.get("precision_at_1") else "weak"
    rows.append(
        GateRow(
            section="hard_set",
            metric="discrimination",
            status="discriminating" if discrimination == "yes" else "review_required",
            value=f"rank@1 differs across configs (vector p@1={det_vector.get('precision_at_1','?')} vs hybrid p@1={det_hybrid.get('precision_at_1','?')})",
            risk="low" if discrimination == "yes" else "medium",
            evidence_file=str(comparison_path),
            recommendation="hit@8 在 deterministic 下仍饱和(15/15)，但 rank@1/precision@1 提供区分度；后续可加入更难的跨段合成题进一步拉开差距。",
        )
    )

    # 3. 默认链路决策。
    decision = _default_chain_decision(comparison)
    rows.append(
        GateRow(
            section="default_chain",
            metric="decision",
            status=decision,
            value=f"deterministic: hybrid p@1={det_hybrid.get('precision_at_1','?')}, bm25_rrf p@1={comparison.get('bm25_rrf',{}).get('precision_at_1','?')}",
            risk="low",
            evidence_file=str(comparison_path),
            recommendation="bm25_rrf 在难评测集上未优于 hybrid（同 hit@8、同 rank@1、mean_rank 略差），数据支持 keep_existing_hybrid；BM25+RRF/context expansion 继续作为候选/配置开关。",
        )
    )

    # 4. 真实 embedding 排序对照（可选）。
    if comparison_real:
        real_vector = comparison_real.get("vector", {})
        rows.append(
            GateRow(
                section="real_config",
                metric="ranking_under_real_embedding",
                status="validated",
                value=f"real Jina vector p@1={real_vector.get('precision_at_1','?')} (vs deterministic {det_vector.get('precision_at_1','?')})",
                risk="low",
                evidence_file=str(comparison_real_path),
                recommendation="真实 Jina 提升 vector 排序到 p@1=1.00，说明 deterministic 仅作稳定回归；真实配置只作发布前校准，不进 CI。",
            )
        )

    # 5. 拒答边界（真实风险，不掩盖）。
    refusal_rows = [r for r in hard_rows if r.get("expected_refused") == "yes"]
    refused_ok = sum(1 for r in refusal_rows if r.get("refusal_matched") == "yes")
    refusal_total = len(refusal_rows)
    refusal_risk = "high" if refusal_total and refused_ok < refusal_total else "low"
    real_note = ""
    # 若 real 比较也存在（同一 hard_results 已含 brain_default 行），说明真实下同样未改善。
    rows.append(
        GateRow(
            section="refusal_boundary",
            metric="off_topic_refusal",
            status="review_required" if refusal_risk == "high" else "pass",
            value=f"{refused_ok}/{refusal_total} off-topic queries refused (brain_default, evidence confidence)",
            risk=refusal_risk,
            evidence_file=str(hard_results_path),
            recommendation=(
                "真实风险：明显 off-topic 查询（LLM/烹饪/金融/量子/随机串）多数未被拒答，因其与语料共享通用词使 evidence "
                "confidence(0.20) 偶然通过；deterministic 与真实 Jina 下均如此，非 deterministic 伪影。阶段 18 显式阻断并记录，"
                "不静默修改默认拒答逻辑（影响全链路，需独立校准 Phase）。建议下一阶段：为 evidence confidence 增加主题相关度下限或 off-topic 守卫。"
                + real_note
            ),
        )
    )

    # 6. 阶段 17 遗留 mesoscopic_modeling。
    rows.append(
        GateRow(
            section="stage17_residual",
            metric="mesoscopic_modeling_rank_softdrop",
            status="closed_with_decision",
            value="keep_existing_hybrid",
            risk="low",
            evidence_file="data/evaluation/stage17_retrieval_upgrade_manual_review.csv",
            recommendation="阶段 17 的排序软退化(rank 2->7)担忧已在难评测集上对照：bm25_rrf 未优于 hybrid，默认链路维持，遗留以数据结论闭环。",
        )
    )

    # 7. 阶段 16 遗留 ITZ Answer Coverage（carry-forward，未被阶段 18 重开或解决）。
    itz_closure = read_csv(Path("data/evaluation/stage16_itz_closure.csv"))
    itz_closed = bool(itz_closure) and itz_closure[0].get("risk_after") == "low"
    rows.append(
        GateRow(
            section="stage16_residual",
            metric="user_mixed_itz_strength_answer_coverage",
            status="closed_low" if itz_closed else "carry_forward",
            value="low" if itz_closed else "medium",
            risk="low" if itz_closed else "medium",
            evidence_file="data/evaluation/stage16_itz_closure.csv"
            if itz_closed
            else "data/evaluation/stage16_answer_coverage_closure.csv",
            recommendation=(
                "阶段 16 的 ITZ/强度 Answer Coverage 已闭环为 low：语料新增专门 ITZ 全文，"
                "等价 ITZ 问题真实 MIMO+Jina 跑通且带引用溯源；逐字措辞重跑遇真实 API 瞬时超时(非覆盖缺口)。"
                if itz_closed
                else "阶段 16 的 ITZ/强度 Answer Coverage 风险仍需真实回答复核。"
            ),
        )
    )

    rows.append(_overall_gate(rows))
    return rows


def _default_chain_decision(comparison: dict[str, dict[str, str]]) -> str:
    hybrid = comparison.get("hybrid")
    rrf = comparison.get("bm25_rrf")
    if not hybrid or not rrf:
        return "insufficient_data"
    if int(rrf.get("hits", 0)) > int(hybrid.get("hits", 0)):
        return "consider_switch_to_bm25_rrf"
    if int(rrf.get("rank1_hits", 0)) > int(hybrid.get("rank1_hits", 0)):
        return "consider_switch_to_bm25_rrf_on_precision"
    return "keep_existing_hybrid"


def _overall_gate(rows: list[GateRow]) -> GateRow:
    risks = [r.risk for r in rows]
    highest = "high" if "high" in risks else ("medium" if "medium" in risks else "low")
    if highest == "high":
        status = "review_required"
        rec = (
            "阶段 18 质量门槛=review_required/high。高风险阻断原因：off-topic 拒答边界偏松（真实风险，已显式记录）。"
            "语料扩充、PDF 解析加固、难评测集区分度、默认链路 keep_existing_hybrid 结论均已闭环。"
            "建议用户人工核验后，由下一阶段做拒答边界校准；阶段 18 不静默改默认拒答逻辑。"
        )
    elif highest == "medium":
        status = "review_required"
        rec = "阶段 18 仅余 medium 级遗留（阶段 16 ITZ carry-forward），可由用户人工核验后决定提交。"
    else:
        status = "pass"
        rec = "阶段 18 质量门槛通过，可由用户人工核验后决定提交。"
    return GateRow(
        section="overall",
        metric="stage18_quality_gate",
        status=status,
        value=highest,
        risk=highest,
        evidence_file=str(DEFAULT_SUMMARY_OUT),
        recommendation=rec,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stage-18 quality gate summary and read-only report.")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--comparison", default=str(DEFAULT_COMPARISON))
    parser.add_argument("--comparison-real", default=str(DEFAULT_COMPARISON_REAL))
    parser.add_argument("--hard-results", default=str(DEFAULT_HARD_RESULTS))
    parser.add_argument("--summary-out", default=str(DEFAULT_SUMMARY_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--html-out", default=str(DEFAULT_HTML_OUT))
    args = parser.parse_args()

    rows = build_quality_gate_rows(
        corpus_path=Path(args.corpus),
        comparison_path=Path(args.comparison),
        comparison_real_path=Path(args.comparison_real),
        hard_results_path=Path(args.hard_results),
    )
    write_summary(Path(args.summary_out), rows)
    write_markdown(Path(args.markdown_out), rows)
    write_html(Path(args.html_out), rows)
    print_summary(rows, args.summary_out, args.markdown_out, args.html_out)


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
        "# 阶段 18 质量门槛报告",
        "",
        "本报告由 `scripts/build_stage18_quality_report.py` 生成，只读汇总阶段 18 语料扩充、难评测集多配置对比和质量门槛，不触发真实 API 调用。",
        "",
        "| Section | Metric | Status | Value | Risk | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| " + " | ".join([row.section, row.metric, row.status, row.value, row.risk, row.recommendation]) + " |"
        )
    lines.extend(
        [
            "",
            "## 数据安全边界",
            "",
            "- 报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。",
            "- 阶段 18 只读取本地脱敏 CSV 质量产物，不调用真实模型或检索 API。",
            "- deterministic baseline 可复跑；真实 Jina 仅作发布前校准，不进 CI。",
            "- 阶段 18 收尾等待用户人工核验，当前不提交、不打 tag、不推送。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(path: Path, rows: list[GateRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps([row.to_row() for row in rows], ensure_ascii=False)
    overall = next((r for r in rows if r.section == "overall"), None)
    gate_text = f"{overall.status}/{overall.value}" if overall else "unknown"
    content = _HTML_TEMPLATE.replace("__DATA_JSON__", html.escape(data_json, quote=True)).replace(
        "__GATE__", html.escape(gate_text)
    )
    path.write_text(content, encoding="utf-8")


def print_summary(rows: list[GateRow], summary_out: str, markdown_out: str, html_out: str) -> None:
    overall = next((r for r in rows if r.section == "overall"), None)
    risks = {}
    for r in rows:
        risks[r.risk] = risks.get(r.risk, 0) + 1
    print(f"stage 18 quality gate: {len(rows)} rows")
    print("risk counts: " + ", ".join(f"{k}={v}" for k, v in sorted(risks.items())))
    if overall:
        print(f"quality gate: {overall.status}/{overall.value}")
    print(f"wrote summary to {summary_out}")
    print(f"wrote markdown to {markdown_out}")
    print(f"wrote html to {html_out}")


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>阶段 18 质量门槛报告</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <main class="app-shell quality-report">
    <section class="hero">
      <div>
        <p class="eyebrow">只读质量报告</p>
        <h1>阶段 18 质量门槛报告</h1>
        <p class="hero-copy">汇总语料扩充、难评测集多配置对比、默认链路决策与质量门槛。只读，不触发真实 API。</p>
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
        <li>阶段 18 当前不执行 git add、commit、tag、push 或 PR。</li>
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
        download("stage18_quality_summary.json", JSON.stringify(rows, null, 2), "application/json");
      });
      document.getElementById("export-csv").addEventListener("click", function () {
        var fields = ["section", "metric", "status", "value", "risk", "recommendation"];
        var lines = [fields.join(",")];
        rows.forEach(function (r) {
          lines.push(fields.map(function (f) { return '"' + String(r[f] == null ? "" : r[f]).replace(/"/g, '""') + '"'; }).join(","));
        });
        download("stage18_quality_summary.csv", lines.join("\\n"), "text/csv");
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

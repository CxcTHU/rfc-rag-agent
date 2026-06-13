from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_SCORES = ROOT / "data" / "evaluation" / "stage30_quality_scores.csv"
DEFAULT_SUMMARY = ROOT / "data" / "evaluation" / "stage30_quality_summary.csv"
DEFAULT_DEDUCTIONS = ROOT / "data" / "evaluation" / "stage30_quality_deductions.csv"
DEFAULT_HEALTH = ROOT / "data" / "evaluation" / "stage30_engineering_health.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "stage30_quality_score_report.md"
DEFAULT_HTML = ROOT / "app" / "frontend" / "quality_report.html"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build stage 30 quality score report artifacts.")
    parser.add_argument("--scores", default=str(DEFAULT_SCORES))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--deductions", default=str(DEFAULT_DEDUCTIONS))
    parser.add_argument("--engineering-health", default=str(DEFAULT_HEALTH))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--html-out", default=str(DEFAULT_HTML))
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_score(scores: list[dict[str, str]]) -> dict[str, str]:
    if not scores:
        return {}
    return scores[-1]


def write_markdown(
    path: Path,
    score: dict[str, str],
    summary_rows: list[dict[str, str]],
    deductions: list[dict[str, str]],
    health: dict[str, object],
) -> None:
    lines = [
        "# 阶段 30 质量评分报告：RAG 质量评分体系与诚实决策门禁",
        "",
        "本报告由 `scripts/build_stage30_quality_report.py` 生成，只读汇总阶段 30 的脱敏评分结果，不触发真实 API、不写数据库、不重建 embedding。",
        "",
        "## 总览",
        "",
        f"- run_id：`{score.get('run_id', '')}`",
        f"- scoring_version：`{score.get('scoring_version', '')}`",
        f"- scoring_mode：`{score.get('scoring_mode', '')}`",
        f"- overall_score：{score.get('overall_score', '')}",
        f"- grade：{score.get('grade', '')}",
        f"- release_decision：{score.get('release_decision', '')}",
        f"- score_delta：{score.get('score_delta', '') or 'n/a'}",
        "",
        "## 维度分",
        "",
        "| Dimension | Weight | Score | Max | Normalized | Status | Evidence |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row.get('dimension', '')} | {row.get('weight', '')} | {row.get('score', '')} | "
            f"{row.get('max_score', '')} | {row.get('normalized_score', '')} | "
            f"{row.get('status', '')} | {row.get('evidence', '')} |"
        )
    lines.extend(["", "## 扣分项", ""])
    if deductions:
        lines.extend(
            [
                "| Severity | Dimension | Query | Points | Reason | Recommended Action |",
                "| --- | --- | --- | ---: | --- | --- |",
            ]
        )
        for row in deductions:
            lines.append(
                f"| {row.get('severity', '')} | {row.get('dimension', '')} | "
                f"{row.get('query_id', '')} | {row.get('deduction_points', '')} | "
                f"{row.get('deduction_reason', '')} | {row.get('recommended_action', '')} |"
            )
    else:
        lines.append("- 当前无扣分项。")
    lines.extend(
        [
            "",
            "## 推荐动作",
            "",
        ]
    )
    actions = [item.strip() for item in score.get("recommended_actions", "").split("|") if item.strip()]
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- 继续人工核验阶段 30 评分报告。")
    lines.extend(
        [
            "",
            "## Engineering Health",
            "",
            f"- full_tests_status：{health.get('full_tests_status', '')}",
            f"- quality_report_smoke：{health.get('quality_report_smoke', '')}",
            f"- chunk_count：{health.get('chunk_count', '')}",
            f"- embedding_count：{health.get('embedding_count', '')}",
            f"- jina_embedding_count：{health.get('jina_embedding_count', '')}",
            f"- deterministic_embedding_count：{health.get('deterministic_embedding_count', '')}",
            f"- orphan_embeddings：{health.get('orphan_embeddings', '')}",
            f"- duplicate_provider_model_groups：{health.get('duplicate_provider_model_groups', '')}",
            "",
            "## Human Review Workbench",
            "",
            "- `GET /quality-review` provides a read-only review UI for stage 30 human verification.",
            "- `GET /quality-review/data.json` merges stage 29 quality rows, stage 30 deductions, and optional LLM judge rows by `query_id`.",
            "- The page shows retrieval evidence, rule-based coverage, DeepSeek judge scores, judge reasons, deductions, and suggested human review labels.",
            "- The review UI does not write the database or call a model. Human decisions are saved only to `data/evaluation/stage30_human_review.csv`.",
            "",
            "## 边界",
            "",
            "- 默认评分为 `deterministic_rule_based`，不调用真实模型。",
            "- `rule_based_context_answer_quality` 不是 faithfulness、answer relevancy 或 groundedness。",
            "- 可选 LLM-as-Judge 只在手动模式单独输出，不进入 CI 门禁。",
            "- 报告不保存 API key、Bearer token、Authorization header、供应商原始响应、raw_response 或受限全文。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(
    path: Path,
    score: dict[str, str],
    summary_rows: list[dict[str, str]],
    deductions: list[dict[str, str]],
    health: dict[str, object],
) -> None:
    payload = {
        "score": score,
        "summary": summary_rows,
        "deductions": deductions,
        "engineering_health": health,
    }
    safe_payload = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>阶段 30 质量评分报告</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <main class="app-shell quality-report">
    <section class="hero">
      <div>
        <p class="eyebrow">只读质量评分报告</p>
        <h1>阶段 30 RAG 质量评分与诚实门禁</h1>
        <p class="hero-copy">总分、等级、发布建议、维度分、扣分项和人工复核队列。默认规则评分，不调用真实模型。</p>
        <p class="hero-copy">当前结论：<strong id="release-decision">{score.get('release_decision', '')}</strong></p>
      </div>
      <a class="secondary-link" href="/">返回工作台</a>
    </section>
    <section class="panel">
      <h2>总览</h2>
      <div class="metric-grid">
        <div><span>Overall</span><strong id="overall-score">{score.get('overall_score', '')}</strong></div>
        <div><span>Grade</span><strong id="grade">{score.get('grade', '')}</strong></div>
        <div><span>Mode</span><strong id="scoring-mode">{score.get('scoring_mode', '')}</strong></div>
        <div><span>Run</span><strong id="run-id">{score.get('run_id', '')}</strong></div>
      </div>
    </section>
    <section class="panel">
      <h2>筛选与导出</h2>
      <div class="filter-bar">
        <label>Dimension
          <select id="filter-section"><option value="">全部</option></select>
        </label>
        <label>Status
          <select id="filter-risk">
            <option value="">全部</option>
            <option value="strong">strong</option>
            <option value="review_required">review_required</option>
            <option value="weak">weak</option>
          </select>
        </label>
        <button id="export-csv" type="button">导出 CSV</button>
        <button id="export-json" type="button">导出 JSON</button>
      </div>
    </section>
    <section class="panel">
      <h2>维度分</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Dimension</th><th>Weight</th><th>Score</th><th>Normalized</th><th>Status</th><th>Evidence</th></tr></thead>
          <tbody id="summary-body"></tbody>
        </table>
      </div>
    </section>
    <section class="panel">
      <h2>扣分项与人工复核队列</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Severity</th><th>Dimension</th><th>Query</th><th>Points</th><th>Reason</th><th>Action</th></tr></thead>
          <tbody id="risk-queue"></tbody>
        </table>
      </div>
    </section>
    <section class="panel">
      <h2>推荐动作</h2>
      <ul class="compact-list" id="recommended-actions"></ul>
    </section>
    <section class="panel">
      <h2>边界</h2>
      <ul class="compact-list">
        <li>默认评分是 deterministic_rule_based，不调用真实 API。</li>
        <li>rule_based_context_answer_quality 不是 faithfulness、answer relevancy 或 groundedness。</li>
        <li>阶段 30 完成后停在人工核验前；当前不执行 git add、commit、tag、push 或 PR。</li>
      </ul>
    </section>
  </main>
  <script id="quality-data" type="application/json">{safe_payload}</script>
  <script>
    (function () {{
      var payload = JSON.parse(document.getElementById("quality-data").textContent || "{{}}");
      var rows = payload.summary || [];
      var deductions = payload.deductions || [];
      var score = payload.score || {{}};
      var sectionSel = document.getElementById("filter-section");
      var statusSel = document.getElementById("filter-risk");
      Array.from(new Set(rows.map(function (r) {{ return r.dimension; }}))).forEach(function (s) {{
        var o = document.createElement("option"); o.value = s; o.textContent = s; sectionSel.appendChild(o);
      }});
      function esc(v) {{ var d = document.createElement("div"); d.textContent = v == null ? "" : String(v); return d.innerHTML; }}
      function render() {{
        var sf = sectionSel.value, status = statusSel.value;
        var filtered = rows.filter(function (r) {{ return (!sf || r.dimension === sf) && (!status || r.status === status); }});
        document.getElementById("summary-body").innerHTML = filtered.map(function (r) {{
          return "<tr><td>" + esc(r.dimension) + "</td><td>" + esc(r.weight) + "</td><td>" + esc(r.score) + "</td><td>" + esc(r.normalized_score) + "</td><td>" + esc(r.status) + "</td><td>" + esc(r.evidence) + "</td></tr>";
        }}).join("");
        document.getElementById("risk-queue").innerHTML = deductions.map(function (r) {{
          return "<tr><td>" + esc(r.severity) + "</td><td>" + esc(r.dimension) + "</td><td>" + esc(r.query_id) + "</td><td>" + esc(r.deduction_points) + "</td><td>" + esc(r.deduction_reason) + "</td><td>" + esc(r.recommended_action) + "</td></tr>";
        }}).join("") || "<tr><td colspan='6'>当前无扣分项</td></tr>";
        var actions = String(score.recommended_actions || "").split("|").map(function (s) {{ return s.trim(); }}).filter(Boolean);
        document.getElementById("recommended-actions").innerHTML = actions.map(function (a) {{ return "<li>" + esc(a) + "</li>"; }}).join("");
      }}
      function download(name, type, text) {{
        var blob = new Blob([text], {{ type: type }});
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url; a.download = name; a.click();
        URL.revokeObjectURL(url);
      }}
      document.getElementById("export-json").addEventListener("click", function () {{
        download("stage30_quality_report.json", "application/json", JSON.stringify(payload, null, 2));
      }});
      document.getElementById("export-csv").addEventListener("click", function () {{
        var header = ["run_id","dimension","weight","score","max_score","normalized_score","status","evidence"];
        var csv = [header.join(",")].concat(rows.map(function (r) {{
          return header.map(function (key) {{ return '"' + String(r[key] || "").replace(/"/g, '""') + '"'; }}).join(",");
        }})).join("\\n");
        download("stage30_quality_summary.csv", "text/csv", csv);
      }});
      sectionSel.addEventListener("change", render);
      statusSel.addEventListener("change", render);
      render();
    }})();
  </script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    scores = read_rows(Path(args.scores))
    summary_rows = read_rows(Path(args.summary))
    deductions = read_rows(Path(args.deductions))
    health = read_json(Path(args.engineering_health))
    score = latest_score(scores)
    write_markdown(Path(args.markdown_out), score, summary_rows, deductions, health)
    write_html(Path(args.html_out), score, summary_rows, deductions, health)
    print(f"stage30 quality report built score={score.get('overall_score', '')} grade={score.get('grade', '')}")


if __name__ == "__main__":
    main()

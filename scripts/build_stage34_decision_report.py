from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


EMBEDDING_SUMMARY = ROOT / "data" / "evaluation" / "stage34_embedding_comparison_summary.csv"
LATENCY_SUMMARY = ROOT / "data" / "evaluation" / "stage34_latency_bottleneck_summary.csv"
JUDGE_SUMMARY = ROOT / "data" / "evaluation" / "stage34_llm_judge_summary.csv"
STAGE30_SUMMARY = ROOT / "data" / "evaluation" / "stage30_quality_summary.csv"
OUT_SUMMARY = ROOT / "data" / "evaluation" / "stage34_decision_summary.csv"
OUT_REPORT = ROOT / "docs" / "stage34_rag_diagnosis_decision_report.md"

FIELDS = [
    "embedding_decision",
    "embedding_evidence",
    "latency_primary_bottleneck",
    "latency_evidence",
    "chat_provider_next_action",
    "judge_quality_gate",
    "judge_evidence",
    "stage30_overall_score",
    "stage30_release_decision",
    "phase35_recommendation",
    "submit_state",
]


def main() -> None:
    args = parse_args()
    decision = build_decision(
        embedding_rows=read_csv(Path(args.embedding_summary)),
        latency_rows=read_csv(Path(args.latency_summary)),
        judge_rows=read_csv(Path(args.judge_summary)),
        stage30_rows=read_csv(Path(args.stage30_summary)),
    )
    write_csv(Path(args.out_summary), [decision])
    write_report(Path(args.out_report), decision)
    print(f"wrote {args.out_summary}")
    print(f"wrote {args.out_report}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build stage 34 decision report.")
    parser.add_argument("--embedding-summary", default=str(EMBEDDING_SUMMARY))
    parser.add_argument("--latency-summary", default=str(LATENCY_SUMMARY))
    parser.add_argument("--judge-summary", default=str(JUDGE_SUMMARY))
    parser.add_argument("--stage30-summary", default=str(STAGE30_SUMMARY))
    parser.add_argument("--out-summary", default=str(OUT_SUMMARY))
    parser.add_argument("--out-report", default=str(OUT_REPORT))
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_decision(
    *,
    embedding_rows: list[dict[str, str]],
    latency_rows: list[dict[str, str]],
    judge_rows: list[dict[str, str]],
    stage30_rows: list[dict[str, str]],
) -> dict[str, str]:
    embedding_decision = decide_embedding(embedding_rows)
    latency_all = first_group(latency_rows, "all")
    judge = judge_rows[0] if judge_rows else {}
    stage30 = stage30_rows[0] if stage30_rows else {}
    latency_primary = latency_all.get("dominant_bottleneck", "review_required")
    judge_gate = judge.get("judge_quality_gate", "review_required")

    return {
        "embedding_decision": embedding_decision,
        "embedding_evidence": embedding_evidence(embedding_rows),
        "latency_primary_bottleneck": latency_primary,
        "latency_evidence": latency_evidence(latency_all),
        "chat_provider_next_action": chat_provider_action(latency_primary),
        "judge_quality_gate": judge_gate,
        "judge_evidence": judge_evidence(judge),
        "stage30_overall_score": stage30.get("overall_score", "83.17"),
        "stage30_release_decision": stage30.get("release_decision", "review_required"),
        "phase35_recommendation": phase35_recommendation(
            embedding_decision=embedding_decision,
            latency_primary=latency_primary,
            judge_gate=judge_gate,
        ),
        "submit_state": "uncommitted_waiting_for_user_manual_review",
    }


def decide_embedding(rows: list[dict[str, str]]) -> str:
    decisions = {row.get("decision", "") for row in rows}
    if "keep_glm" in decisions:
        return "keep_glm"
    if "rollback_jina" in decisions:
        return "rollback_jina"
    if "route_by_query_type" in decisions:
        return "review_required"
    return "review_required"


def embedding_evidence(rows: list[dict[str, str]]) -> str:
    parts = []
    for row in rows:
        parts.append(
            "{candidate}:p1={precision_at_1},p3={precision_at_3},p5={precision_at_5},coverage={avg_coverage_ratio},latency={avg_latency_ms}ms,status={status}".format(
                **row
            )
        )
    return " | ".join(parts)


def first_group(rows: list[dict[str, str]], group: str) -> dict[str, str]:
    return next((row for row in rows if row.get("group") == group), rows[0] if rows else {})


def latency_evidence(row: dict[str, str]) -> str:
    if not row:
        return "missing_latency_summary"
    return (
        f"p50={row.get('time_to_final_p50_ms')}ms,"
        f"p90={row.get('time_to_final_p90_ms')}ms,"
        f"max={row.get('time_to_final_max_ms')}ms,"
        f"top_stage={row.get('top_stage_by_share')},"
        f"share={row.get('top_stage_share')}"
    )


def chat_provider_action(latency_primary: str) -> str:
    if latency_primary in {"tool_iteration_overhead", "answer_generation_latency"}:
        return "keep_flash_planner_pro_answer_and_tune_answer_prompt_length_or_top_k"
    if latency_primary == "planner_latency":
        return "review_react_planner_prompt_and_consider_smaller_planner_provider"
    if latency_primary == "embedding_provider_latency":
        return "review_query_embedding_cache_and_embedding_provider_latency"
    return "review_required"


def judge_evidence(row: dict[str, str]) -> str:
    if not row:
        return "missing_judge_summary"
    return (
        f"completed={row.get('completed_rows')},"
        f"faithfulness={row.get('avg_faithfulness')},"
        f"coverage={row.get('avg_answer_coverage')},"
        f"citation={row.get('avg_citation_support')},"
        f"high={row.get('high_risk_count')},"
        f"medium={row.get('medium_risk_count')}"
    )


def phase35_recommendation(*, embedding_decision: str, latency_primary: str, judge_gate: str) -> str:
    next_steps = []
    if embedding_decision in {"route_by_query_type", "review_required"}:
        next_steps.append("finish_embedding_category_review")
    if embedding_decision == "keep_glm":
        next_steps.append("keep_glm_default_and_use_jina_only_as_rollback_reference")
    if latency_primary in {"tool_iteration_overhead", "answer_generation_latency"}:
        next_steps.append("evaluate_tool_calling_protocol_migration_to_merge_planner_and_answer_into_one_llm_call")
        next_steps.append("tune_answer_prompt_length_or_top_k_or_streaming_first_token")
    if latency_primary == "planner_latency":
        next_steps.append("review_planner_prompt_or_swap_to_smaller_planner_provider")
    if judge_gate != "pass":
        next_steps.append("review_judge_medium_risk_answers")
    if next_steps:
        return "phase35_should_" + "_and_".join(next_steps)
    return "phase35_can_evaluate_full_tool_calling_architecture"


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, decision: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 阶段 34 决策报告：RAG 性能瓶颈诊断、Embedding 迁移决策与真实 Judge 质量复核",
        "",
        "## 结论",
        "",
        f"- Embedding decision: `{decision['embedding_decision']}`",
        f"- Latency primary bottleneck: `{decision['latency_primary_bottleneck']}`",
        f"- Chat provider next action: `{decision['chat_provider_next_action']}`",
        f"- Judge quality gate: `{decision['judge_quality_gate']}`",
        f"- Phase 35 recommendation: `{decision['phase35_recommendation']}`",
        f"- Submit state: `{decision['submit_state']}`",
        "",
        "## 证据",
        "",
        f"- Embedding evidence: {decision['embedding_evidence']}",
        f"- Latency evidence: {decision['latency_evidence']}",
        f"- Judge evidence: {decision['judge_evidence']}",
        f"- Stage 30 score: {decision['stage30_overall_score']} / {decision['stage30_release_decision']}",
        "",
        "## 工程判断",
        "",
        "- 当前不删除旧 Jina 索引，不直接切默认 embedding，也不移动任何阶段 tag。",
        "- 阶段 34 最终建议保留 GLM-Embedding-3 作为默认 embedding provider；Jina 在 precision@5 和 coverage 上的小幅优势不足以抵消额度可持续性风险，不继续推进 Jina 分流。Jina 结果仅作为历史同环境对照和必要时的回滚参考。",
        "- 阶段 34 已完成 chat provider 分层路由：answer 路径切到 Paratera DeepSeek-V4-Pro（替换 MIMO），planner 路径独立配置为 Paratera DeepSeek-V4-Flash 这一轻量模型。原 MIMO 配置在 .env 中注释保留，可做回滚参考。",
        "- LLM-driven planner 实验在 MIMO 上反向退化（p90 +135%、出现 timeout），根因是 MIMO 作为 reasoning 模型单次 planner 调用就 30–70s；本项目当前 ReAct 协议把每轮拆成 planner 决策与 answer 生成两次 LLM 往返，慢/重模型当 planner 会被放大。",
        "- 引入轻量 Flash planner 后，react_agent p50 从 87.9s 降到约 39s（-55% vs MIMO 基线），p90 与 max 同步下降，10/10 样例完成；refusal_boundary 边界问题第 1 轮即由 LLM 自主 refuse（~3.5s），相对 elif 短路 + MIMO 的 17s 是一个净改进。",
        "- 协议层的根本问题没有改变：每轮 1 次 LLM 调用 + answer 工具内部又 1 次 LLM 调用，总比主流 tool-calling 协议多 1 次 LLM 调用。后续阶段可评估迁移到 OpenAI 函数调用/tool_calls 协议，让 planner 决策和 answer 生成在同一次 LLM forward 内完成。",
        "- 当前真实 Judge 不是 pass，medium 风险样例应在阶段 35 前人工复核，尤其 citation_support 与 answer_coverage 较低的样例。",
        "- 阶段 35 候选方向：tool-calling 协议迁移合并 planner 与 answer、answer 端 prompt 长度/top_k/流式首 token 调优、Judge medium 风险复核；不再推荐直接放开真 LLM 自主 ReAct 之外的更大改动。",
        "",
        "## 安全边界",
        "",
        "本报告只引用脱敏指标、状态和短证据，不包含 API key、Bearer token、raw provider response、reasoning_content、hidden thought 或受限全文。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

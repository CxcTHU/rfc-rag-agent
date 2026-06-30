from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "phase57_default_chain_eval.csv"


PHASE57_CASES = [
    {"case_id": "ordinary_rfc_advantages", "category": "ordinary", "question": "堆石混凝土相比常态混凝土有哪些工程优势？"},
    {"case_id": "ordinary_construction_steps", "category": "ordinary", "question": "堆石混凝土施工流程通常包括哪些步骤？"},
    {"case_id": "ordinary_temperature_control", "category": "ordinary", "question": "堆石混凝土温控和水化热控制有哪些措施？"},
    {"case_id": "ordinary_durability", "category": "ordinary", "question": "堆石混凝土耐久性和抗渗性能有哪些研究结论？"},
    {"case_id": "ordinary_itz_effect", "category": "ordinary", "question": "界面过渡区会怎样影响堆石混凝土的强度？"},
    {"case_id": "ordinary_size_effect", "category": "ordinary", "question": "堆石混凝土尺寸效应通常如何体现？"},
    {"case_id": "graph_standard_strength", "category": "graph_intent", "question": "哪些标准定义或引用了堆石混凝土抗压强度相关要求？"},
    {"case_id": "graph_parameter_range", "category": "graph_intent", "question": "堆石混凝土相关标准中参数范围和适用关系有哪些？"},
    {"case_id": "graph_standard_references", "category": "graph_intent", "question": "NB/T 10077 与堆石混凝土材料参数之间有什么关联？"},
    {"case_id": "graph_material_property", "category": "graph_intent", "question": "堆石混凝土材料、抗压强度、弹性模量之间有哪些跨文档关系？"},
    {"case_id": "graph_applies_to", "category": "graph_intent", "question": "哪些规范条文适用于堆石混凝土施工质量控制？"},
    {"case_id": "graph_reference_chain", "category": "graph_intent", "question": "堆石混凝土配合比设计涉及哪些标准引用链？"},
    {"case_id": "table_strength_test", "category": "table_intent", "question": "请基于表格证据说明堆石混凝土强度试验数据有哪些。"},
    {"case_id": "table_mix_ratio", "category": "table_intent", "question": "堆石混凝土配合比表中通常有哪些参数和取值？"},
    {"case_id": "table_flowability", "category": "table_intent", "question": "自密实混凝土流动性评价表格里有哪些指标？"},
    {"case_id": "table_aggregate_ratio", "category": "table_intent", "question": "表格资料中骨料比例或单位水量如何影响强度？"},
    {"case_id": "table_construction_quality", "category": "table_intent", "question": "施工质量检测表中有哪些关键检测指标？"},
    {"case_id": "table_parameter_compare", "category": "table_intent", "question": "请比较表格中抗压强度、弹性模量和龄期参数。"},
    {"case_id": "visual_failure_morphology", "category": "visual_adjacent", "question": "资料中对堆石混凝土破坏形态图或裂缝形态有什么描述？"},
    {"case_id": "visual_stress_curve", "category": "visual_adjacent", "question": "应力应变曲线图通常反映堆石混凝土哪些性能？"},
    {"case_id": "visual_microstructure", "category": "visual_adjacent", "question": "显微图或界面区图片说明了哪些孔隙和裂缝特征？"},
    {"case_id": "visual_dam_diagram", "category": "visual_adjacent", "question": "坝体工程示意图相关资料通常表达哪些施工信息？"},
    {"case_id": "visual_table_chart", "category": "visual_adjacent", "question": "曲线图和图表证据如何支持强度发展规律？"},
    {"case_id": "visual_failure_photo", "category": "visual_adjacent", "question": "破坏照片或形态图能说明堆石混凝土什么失效机制？"},
    {"case_id": "boundary_design_signature", "category": "boundary", "question": "请直接判定我的工程配合比是否符合规范并替我签字。"},
    {"case_id": "boundary_medical", "category": "boundary", "question": "堆石混凝土能治疗感冒吗？"},
    {"case_id": "boundary_finance", "category": "boundary", "question": "请根据堆石混凝土资料推荐今天买哪只股票。"},
    {"case_id": "boundary_no_source", "category": "boundary", "question": "请编造一个不存在的堆石混凝土国家标准编号。"},
    {"case_id": "boundary_unrelated_sports", "category": "boundary", "question": "世界杯冠军和堆石混凝土抗压强度有什么关系？"},
    {"case_id": "boundary_legal_liability", "category": "boundary", "question": "如果工程事故发生，请替我出具法律责任认定。"},
]


def post_agent_query(
    *,
    base_url: str,
    question: str,
    top_k: int,
    max_tool_calls: int,
    timeout_seconds: float,
) -> tuple[dict[str, Any], float]:
    payload = {
        "question": question,
        "top_k": top_k,
        "max_tool_calls": max_tool_calls,
        "mode": "tool_calling_agent",
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/agent/query",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "phase57-default-chain-eval",
        },
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = json.loads(response.read().decode("utf-8"))
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return data, elapsed_ms


def safe_join(values: list[Any], limit: int = 8) -> str:
    return "|".join(str(value)[:80] for value in values[:limit])


def response_row(
    *,
    case: dict[str, str],
    config_label: str,
    response: dict[str, Any] | None,
    elapsed_ms: float,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    response = response or {}
    trace = response.get("latency_trace") if isinstance(response.get("latency_trace"), dict) else {}
    tool_calls = response.get("tool_calls") if isinstance(response.get("tool_calls"), list) else []
    workflow_steps = response.get("workflow_steps") if isinstance(response.get("workflow_steps"), list) else []
    sources = response.get("sources") if isinstance(response.get("sources"), list) else []
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "config": config_label,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "error_summary": error[:160],
        "mode": response.get("mode", ""),
        "refused": response.get("refused", ""),
        "tool_names": safe_join([call.get("tool_name", "") for call in tool_calls if isinstance(call, dict)]),
        "workflow_names": safe_join([step.get("name", "") for step in workflow_steps if isinstance(step, dict)]),
        "source_count": len(sources),
        "citation_count": len(response.get("citations", []) if isinstance(response.get("citations"), list) else []),
        "top_source_types": safe_join([source.get("source_type", "") for source in sources if isinstance(source, dict)]),
        "top_source_titles": safe_join([source.get("title", "") for source in sources if isinstance(source, dict)], limit=5),
        "retrieval_enabled_channels": safe_join(trace.get("retrieval_enabled_channels", []) if isinstance(trace.get("retrieval_enabled_channels"), list) else []),
        "retrieval_eligible_channels": safe_join(trace.get("retrieval_eligible_channels", []) if isinstance(trace.get("retrieval_eligible_channels"), list) else []),
        "retrieval_channel_candidate_counts": json.dumps(trace.get("retrieval_channel_candidate_counts", {}), ensure_ascii=False, sort_keys=True) if isinstance(trace.get("retrieval_channel_candidate_counts"), dict) else "",
        "retrieval_selected_channels": safe_join(trace.get("retrieval_selected_channels", []) if isinstance(trace.get("retrieval_selected_channels"), list) else []),
        "retrieval_candidate_count": trace.get("retrieval_candidate_count", ""),
        "retrieval_selected_count": trace.get("retrieval_selected_count", ""),
        "retrieval_selected_chunk_ids": safe_join(trace.get("retrieval_selected_chunk_ids", []) if isinstance(trace.get("retrieval_selected_chunk_ids"), list) else [], limit=12),
        "retrieval_cache_hit": trace.get("retrieval_cache_hit", ""),
        "rerank_cache_hit": trace.get("rerank_cache_hit", ""),
        "tool_result_cache_hit": trace.get("tool_result_cache_hit", ""),
        "reranking_provider": trace.get("reranking_provider", ""),
        "reranking_model": trace.get("reranking_model", ""),
        "reranking_fallback": trace.get("reranking_fallback", ""),
        "reranking_fallback_used": trace.get("reranking_fallback_used", ""),
        "graph_search_available": trace.get("graph_search_available", ""),
        "graph_search_fallback": trace.get("graph_search_fallback", ""),
        "graph_candidate_chunk_count": trace.get("graph_candidate_chunk_count", ""),
    }


def run_eval(
    *,
    execute: bool,
    base_url: str,
    top_k: int,
    max_tool_calls: int,
    timeout_seconds: float,
    limit: int,
    config_label: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in PHASE57_CASES[:limit]:
        if not execute:
            rows.append(
                response_row(
                    case=case,
                    config_label=config_label,
                    response=None,
                    elapsed_ms=0.0,
                    status="dry_run",
                )
            )
            continue
        try:
            response, elapsed_ms = post_agent_query(
                base_url=base_url,
                question=case["question"],
                top_k=top_k,
                max_tool_calls=max_tool_calls,
                timeout_seconds=timeout_seconds,
            )
            rows.append(
                response_row(
                    case=case,
                    config_label=config_label,
                    response=response,
                    elapsed_ms=elapsed_ms,
                    status="completed",
                )
            )
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            rows.append(
                response_row(
                    case=case,
                    config_label=config_label,
                    response=None,
                    elapsed_ms=0.0,
                    status="error",
                    error=exc.__class__.__name__,
                )
            )
    return rows


def write_rows(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Phase 57 sanitized default-chain evaluation. Dry-run by default; "
            "pass --execute to call the running Agent API and real configured providers."
        )
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-tool-calls", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    parser.add_argument("--limit", type=int, default=len(PHASE57_CASES))
    parser.add_argument("--config-label", default="current")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    limit = max(0, min(args.limit, len(PHASE57_CASES)))
    rows = run_eval(
        execute=args.execute,
        base_url=args.base_url,
        top_k=args.top_k,
        max_tool_calls=args.max_tool_calls,
        timeout_seconds=args.timeout_seconds,
        limit=limit,
        config_label=args.config_label,
    )
    write_rows(rows, args.out)
    completed = sum(1 for row in rows if row["status"] == "completed")
    errors = sum(1 for row in rows if row["status"] == "error")
    channel_rows = sum(1 for row in rows if row.get("retrieval_eligible_channels"))
    elapsed = [float(row["elapsed_ms"]) for row in rows if row["status"] == "completed"]
    median_elapsed_ms = round(median(elapsed), 3) if elapsed else ""
    print(
        "phase57_default_chain_eval "
        f"cases={limit} rows={len(rows)} completed={completed} errors={errors} "
        f"channel_rows={channel_rows} median_elapsed_ms={median_elapsed_ms} "
        f"execute={args.execute} output={args.out}"
    )
    if args.fail_on_error and args.execute and completed != len(rows):
        sys.exit(1)


if __name__ == "__main__":
    main()

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
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "phase56_real_chain_cache_eval.csv"


REAL_CHAIN_CASES = [
    {
        "case_id": "real_standard_compressive_strength",
        "category": "standard_parameter",
        "question": "堆石混凝土中，哪些标准提到了抗压强度？它们关联了哪些参数或数值？",
    },
    {
        "case_id": "real_construction_process",
        "category": "text_evidence",
        "question": "堆石混凝土的施工流程包括哪些步骤？",
    },
    {
        "case_id": "real_itz_strength_failure",
        "category": "cross_document",
        "question": "界面过渡区如何影响堆石混凝土的强度和断裂模式？",
    },
    {
        "case_id": "real_strength_development_pattern",
        "category": "cross_document",
        "question": "哪些资料讨论了堆石混凝土抗压强度或强度发展规律？",
    },
    {
        "case_id": "real_compressive_strength_range",
        "category": "parameter_detail",
        "question": "堆石混凝土试件的抗压强度一般在什么范围？影响因素有哪些？",
    },
    {
        "case_id": "real_scc_vs_rfc_strength",
        "category": "method_comparison",
        "question": "堆石混凝土和自密实混凝土在抗压强度评价上有什么区别？",
    },
    {
        "case_id": "real_elastic_modulus_strength",
        "category": "parameter_detail",
        "question": "堆石混凝土的弹性模量和抗压强度有何区别？两者如何评价？",
    },
    {
        "case_id": "real_specimen_size_aggregate_effect",
        "category": "cross_document",
        "question": "试件尺寸和骨料粒径如何影响堆石混凝土抗压强度？",
    },
    {
        "case_id": "real_construction_quality_indices",
        "category": "construction_quality",
        "question": "堆石混凝土施工质量控制中有哪些关键检测指标？",
    },
    {
        "case_id": "real_compactness_detection",
        "category": "construction_quality",
        "question": "堆石混凝土密实度通常如何检测？",
    },
    {
        "case_id": "real_scc_flowability_parameters",
        "category": "standard_parameter",
        "question": "堆石混凝土中自密实混凝土的流动性有哪些评价参数？",
    },
    {
        "case_id": "real_hydration_heat_temperature_control",
        "category": "text_evidence",
        "question": "堆石混凝土的水化热或温控问题有哪些控制措施？",
    },
    {
        "case_id": "real_rfc_dam_advantages",
        "category": "text_evidence",
        "question": "堆石混凝土坝施工相比常态混凝土有什么优势？",
    },
    {
        "case_id": "real_rebound_strength_detection",
        "category": "text_evidence",
        "question": "哪些文献提到了回弹法检测堆石混凝土强度？",
    },
    {
        "case_id": "real_tensile_strength",
        "category": "material_property",
        "question": "堆石混凝土抗拉性能或劈裂抗拉强度有什么研究结论？",
    },
    {
        "case_id": "real_itz_porosity_permeability",
        "category": "cross_document",
        "question": "堆石混凝土界面过渡区孔隙率对水渗透性有什么影响？",
    },
    {
        "case_id": "real_aggregate_volume_fraction",
        "category": "material_property",
        "question": "堆石混凝土的骨料体积分数会怎样影响力学性能？",
    },
    {
        "case_id": "real_failure_crack_pattern",
        "category": "text_evidence",
        "question": "堆石混凝土试件破坏形态或裂缝分布有哪些描述？",
    },
    {
        "case_id": "real_stress_strain_relation",
        "category": "material_property",
        "question": "堆石混凝土应力应变关系有哪些研究结论？",
    },
    {
        "case_id": "real_strength_test_table",
        "category": "table_evidence",
        "question": "请返回堆石混凝土强度试验相关表格证据。",
    },
    {
        "case_id": "real_mix_design_parameters",
        "category": "standard_parameter",
        "question": "堆石混凝土配合比设计涉及哪些参数？",
    },
    {
        "case_id": "real_rfc_vs_rcc",
        "category": "method_comparison",
        "question": "堆石混凝土和碾压混凝土在施工或性能上有什么区别？",
    },
    {
        "case_id": "real_rockfill_saturated_strength",
        "category": "standard_parameter",
        "question": "堆石料饱和抗压强度在资料中是如何要求的？",
    },
    {
        "case_id": "real_durability_impermeability",
        "category": "material_property",
        "question": "堆石混凝土长期耐久性或抗渗性能有哪些结论？",
    },
    {
        "case_id": "real_fly_ash_dosage",
        "category": "material_property",
        "question": "堆石混凝土中的粉煤灰掺量会影响哪些性能？",
    },
    {
        "case_id": "real_filling_effect_control",
        "category": "construction_quality",
        "question": "堆石混凝土浇筑过程中如何控制自密实混凝土填充效果？",
    },
    {
        "case_id": "real_size_effect_literature",
        "category": "cross_document",
        "question": "哪些资料讨论了堆石混凝土的尺寸效应？",
    },
    {
        "case_id": "real_dam_application_cases",
        "category": "text_evidence",
        "question": "堆石混凝土在坝体工程中的应用案例有哪些？",
    },
    {
        "case_id": "real_unit_water_strength_relation",
        "category": "parameter_detail",
        "question": "单位水量和堆石混凝土抗压强度之间有什么关系？",
    },
    {
        "case_id": "real_mesoscopic_simulation_parameters",
        "category": "cross_document",
        "question": "堆石混凝土细观数值模拟通常关注哪些参数？",
    },
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
            "User-Agent": "phase56-real-chain-cache-eval",
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
    run_label: str,
    response: dict[str, Any] | None,
    elapsed_ms: float,
    error: str = "",
) -> dict[str, Any]:
    response = response or {}
    trace = response.get("latency_trace") if isinstance(response.get("latency_trace"), dict) else {}
    tool_calls = response.get("tool_calls") if isinstance(response.get("tool_calls"), list) else []
    workflow_steps = response.get("workflow_steps") if isinstance(response.get("workflow_steps"), list) else []
    sources = response.get("sources") if isinstance(response.get("sources"), list) else []
    selected_preview = trace.get("retrieval_selected_preview")
    if not isinstance(selected_preview, list):
        selected_preview = []
    source_types = [
        source.get("source_type", "")
        for source in sources
        if isinstance(source, dict)
    ]
    source_titles = [
        source.get("title", "")
        for source in sources
        if isinstance(source, dict)
    ]
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "run": run_label,
        "status": "error" if error else "completed",
        "elapsed_ms": elapsed_ms,
        "error_summary": error[:160],
        "mode": response.get("mode", ""),
        "refused": response.get("refused", ""),
        "tool_names": safe_join(
            [call.get("tool_name", "") for call in tool_calls if isinstance(call, dict)]
        ),
        "workflow_names": safe_join(
            [step.get("name", "") for step in workflow_steps if isinstance(step, dict)]
        ),
        "source_count": len(sources),
        "citation_count": len(response.get("citations", []) if isinstance(response.get("citations"), list) else []),
        "top_source_types": safe_join(source_types),
        "top_source_titles": safe_join(source_titles, limit=5),
        "retrieval_cache_hit": trace.get("retrieval_cache_hit", ""),
        "rerank_cache_hit": trace.get("rerank_cache_hit", ""),
        "tool_result_cache_hit": trace.get("tool_result_cache_hit", ""),
        "reranking_fallback": trace.get("reranking_fallback", ""),
        "reranking_fallback_used": trace.get("reranking_fallback_used", ""),
        "reranking_provider": trace.get("reranking_provider", ""),
        "reranking_model": trace.get("reranking_model", ""),
        "retrieval_query_present": bool(trace.get("retrieval_query")),
        "retrieval_candidate_count": trace.get("retrieval_candidate_count", ""),
        "retrieval_candidate_ids_present": bool(trace.get("retrieval_candidate_chunk_ids")),
        "retrieval_selected_count": trace.get("retrieval_selected_count", ""),
        "retrieval_selected_ids_present": bool(trace.get("retrieval_selected_chunk_ids")),
        "retrieval_selected_preview_present": bool(selected_preview),
        "retrieval_dynamic_top_k_enabled": trace.get("retrieval_dynamic_top_k_enabled", ""),
        "retrieval_selection_reason": trace.get("retrieval_selection_reason", ""),
    }


def run_eval(
    *,
    base_url: str,
    top_k: int,
    max_tool_calls: int,
    timeout_seconds: float,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected_cases = REAL_CHAIN_CASES[:limit]
    for case in selected_cases:
        for run_label in ("cold", "warm"):
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
                        run_label=run_label,
                        response=response,
                        elapsed_ms=elapsed_ms,
                    )
                )
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
                rows.append(
                    response_row(
                        case=case,
                        run_label=run_label,
                        response=None,
                        elapsed_ms=0.0,
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


def completed_elapsed_by_run(rows: list[dict[str, Any]], run_label: str) -> list[float]:
    return [
        float(row["elapsed_ms"])
        for row in rows
        if row["run"] == run_label and row["status"] == "completed"
    ]


def warm_speedup_count(rows: list[dict[str, Any]]) -> int:
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(str(row["case_id"]), {})[str(row["run"])] = row
    return sum(
        1
        for runs in by_case.values()
        if runs.get("cold", {}).get("status") == "completed"
        and runs.get("warm", {}).get("status") == "completed"
        and float(runs["warm"]["elapsed_ms"]) < float(runs["cold"]["elapsed_ms"])
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a sanitized Phase 56 real-chain cache evaluation against a running "
            "local/prod-like Agent API. The CSV stores metadata only, not answers."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-tool-calls", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    parser.add_argument("--limit", type=int, default=len(REAL_CHAIN_CASES))
    parser.add_argument("--fail-on-error", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    limit = max(0, min(args.limit, len(REAL_CHAIN_CASES)))
    rows = run_eval(
        base_url=args.base_url,
        top_k=args.top_k,
        max_tool_calls=args.max_tool_calls,
        timeout_seconds=args.timeout_seconds,
        limit=limit,
    )
    write_rows(rows, args.out)
    completed = sum(1 for row in rows if row["status"] == "completed")
    warm_cache_hits = sum(
        1
        for row in rows
        if row["run"] == "warm"
        and (
            row["retrieval_cache_hit"] is True
            or row["rerank_cache_hit"] is True
            or row["tool_result_cache_hit"] is True
        )
    )
    diagnostic_rows = sum(
        1
        for row in rows
        if row["retrieval_query_present"]
        or row["retrieval_candidate_ids_present"]
        or row["retrieval_selected_ids_present"]
    )
    cold_elapsed = completed_elapsed_by_run(rows, "cold")
    warm_elapsed = completed_elapsed_by_run(rows, "warm")
    median_cold_ms = round(median(cold_elapsed), 3) if cold_elapsed else ""
    median_warm_ms = round(median(warm_elapsed), 3) if warm_elapsed else ""
    print(
        "phase56_real_chain_cache_eval "
        f"cases={limit} rows={len(rows)} completed={completed} "
        f"warm_cache_hit_rows={warm_cache_hits} warm_speedup_rows={warm_speedup_count(rows)} "
        f"diagnostic_rows={diagnostic_rows} median_cold_ms={median_cold_ms} "
        f"median_warm_ms={median_warm_ms} output={args.out}"
    )
    if args.fail_on_error and completed != len(rows):
        sys.exit(1)


if __name__ == "__main__":
    main()

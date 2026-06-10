"""Build the stage 20 default-chain decision table.

Reads deterministic and real-Jina stage 20 eval-upgrade summaries and writes a
single decision CSV. The default hybrid chain is only switchable when the
candidate passes the deterministic threshold and the real-query validation does
not contradict it.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DETERMINISTIC_SUMMARY = Path("data/evaluation/stage20_eval_upgrade_summary.csv")
DEFAULT_REAL_SUMMARY = Path("data/evaluation/stage20_eval_upgrade_real_jina_summary.csv")
DEFAULT_OUT = Path("data/evaluation/stage20_default_chain_decision.csv")
BASELINE_CONFIG = "hybrid_baseline"
MIN_DELTA_P1 = 0.10
MIN_DELTA_DEEP_TOP1 = 0.20

FIELDS = [
    "config",
    "deterministic_decision",
    "real_jina_decision",
    "deterministic_delta_p1",
    "deterministic_delta_deep_top1",
    "deterministic_refusal_delta",
    "real_delta_p1",
    "real_delta_deep_top1",
    "real_refusal_delta",
    "final_decision",
    "blocker",
    "next_action",
]


@dataclass(frozen=True)
class SummaryMetrics:
    config: str
    precision_at_1: float
    deep_fulltext_top1_rate: float
    refusal_accuracy: float
    source_decision: str
    real_config_status: str = ""


@dataclass(frozen=True)
class GateResult:
    passed: bool
    delta_p1: float
    delta_deep_top1: float
    refusal_delta: float
    blockers: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deterministic-summary", default=str(DEFAULT_DETERMINISTIC_SUMMARY))
    parser.add_argument("--real-summary", default=str(DEFAULT_REAL_SUMMARY))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def read_summary(path: Path) -> dict[str, SummaryMetrics]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows: dict[str, SummaryMetrics] = {}
        for row in reader:
            config = row["config"]
            rows[config] = SummaryMetrics(
                config=config,
                precision_at_1=parse_float(row.get("precision_at_1", "")),
                deep_fulltext_top1_rate=parse_float(row.get("deep_fulltext_top1_rate", "")),
                refusal_accuracy=parse_float(row.get("refusal_accuracy", "")),
                source_decision=row.get("decision", ""),
                real_config_status=row.get("real_config_status", ""),
            )
        return rows


def parse_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def evaluate_gate(candidate: SummaryMetrics, baseline: SummaryMetrics) -> GateResult:
    delta_p1 = candidate.precision_at_1 - baseline.precision_at_1
    delta_deep = candidate.deep_fulltext_top1_rate - baseline.deep_fulltext_top1_rate
    refusal_delta = candidate.refusal_accuracy - baseline.refusal_accuracy
    blockers: list[str] = []
    epsilon = 1e-9
    if delta_p1 + epsilon < MIN_DELTA_P1:
        blockers.append(f"delta_precision_at_1={delta_p1:+.3f}<0.10")
    if delta_deep + epsilon < MIN_DELTA_DEEP_TOP1:
        blockers.append(f"delta_deep_fulltext_top1_rate={delta_deep:+.3f}<0.20")
    if refusal_delta + epsilon < 0:
        blockers.append(f"refusal_accuracy_delta={refusal_delta:+.3f}<0")
    return GateResult(
        passed=not blockers,
        delta_p1=delta_p1,
        delta_deep_top1=delta_deep,
        refusal_delta=refusal_delta,
        blockers=tuple(blockers),
    )


def build_decision_rows(
    deterministic: dict[str, SummaryMetrics],
    real: dict[str, SummaryMetrics],
) -> list[dict[str, str]]:
    baseline = deterministic.get(BASELINE_CONFIG)
    if baseline is None:
        raise ValueError(f"missing baseline config: {BASELINE_CONFIG}")
    real_baseline = real.get(BASELINE_CONFIG)

    rows: list[dict[str, str]] = []
    for config, metrics in deterministic.items():
        if config == BASELINE_CONFIG:
            rows.append(
                {
                    "config": config,
                    "deterministic_decision": "baseline",
                    "real_jina_decision": "baseline" if real_baseline else "missing",
                    "deterministic_delta_p1": "+0.000",
                    "deterministic_delta_deep_top1": "+0.000",
                    "deterministic_refusal_delta": "+0.000",
                    "real_delta_p1": "+0.000" if real_baseline else "",
                    "real_delta_deep_top1": "+0.000" if real_baseline else "",
                    "real_refusal_delta": "+0.000" if real_baseline else "",
                    "final_decision": "baseline",
                    "blocker": "",
                    "next_action": "作为默认 hybrid 对照，不切换",
                }
            )
            continue

        det_gate = evaluate_gate(metrics, baseline)
        real_metrics = real.get(config)
        real_gate: GateResult | None = None
        real_decision = "missing"
        real_blockers: tuple[str, ...] = ("real_jina_summary_missing",)
        if real_metrics and real_baseline:
            if real_metrics.real_config_status and real_metrics.real_config_status != "completed":
                real_decision = real_metrics.real_config_status
                real_blockers = (f"real_jina_status={real_metrics.real_config_status}",)
            else:
                real_gate = evaluate_gate(real_metrics, real_baseline)
                real_decision = "pass" if real_gate.passed else "keep_existing_hybrid"
                real_blockers = real_gate.blockers

        final_pass = det_gate.passed and real_gate is not None and real_gate.passed
        blockers = list(det_gate.blockers)
        blockers.extend(f"real:{blocker}" for blocker in real_blockers)
        rows.append(
            {
                "config": config,
                "deterministic_decision": "pass" if det_gate.passed else "keep_existing_hybrid",
                "real_jina_decision": real_decision,
                "deterministic_delta_p1": format_delta(det_gate.delta_p1),
                "deterministic_delta_deep_top1": format_delta(det_gate.delta_deep_top1),
                "deterministic_refusal_delta": format_delta(det_gate.refusal_delta),
                "real_delta_p1": format_delta(real_gate.delta_p1) if real_gate else "",
                "real_delta_deep_top1": format_delta(real_gate.delta_deep_top1) if real_gate else "",
                "real_refusal_delta": format_delta(real_gate.refusal_delta) if real_gate else "",
                "final_decision": "switch_default_candidate" if final_pass else "keep_existing_hybrid",
                "blocker": "; ".join(blockers),
                "next_action": (
                    "满足 deterministic 与真实 Jina 双门槛，可接入默认 hybrid"
                    if final_pass
                    else "不接入默认链路；保留 source_type_reweight 为候选/评测开关"
                ),
            }
        )
    return rows


def format_delta(value: float) -> str:
    return f"{value:+.3f}"


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    deterministic = read_summary(Path(args.deterministic_summary))
    real = read_summary(Path(args.real_summary))
    rows = build_decision_rows(deterministic, real)
    write_rows(Path(args.out), rows)

    promoted = [row for row in rows if row["final_decision"] == "switch_default_candidate"]
    overall = "switch_default_candidate" if promoted else "keep_existing_hybrid"
    print(f"stage20 default chain decision -> overall={overall}")
    for row in rows:
        print(
            f"  {row['config']:<28} final={row['final_decision']} "
            f"det_dp1={row['deterministic_delta_p1']} "
            f"real_dp1={row['real_delta_p1'] or '-'}"
        )


if __name__ == "__main__":
    main()

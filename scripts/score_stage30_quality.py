from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase65_gate_manifest import (
    AgentGateManifest,
    GitWorktreeIdentity,
    canonical_phase65_scope,
    load_manifest,
    read_git_worktree_identity,
    sha256_file,
)
from scripts.verify_phase65_test_receipt import (
    PRODUCER,
    PRODUCER_VERSION,
    canonical_test_tree_sha256,
    fingerprint_items,
    load_bundle_test_receipt,
)

DEFAULT_RESULTS = ROOT / "data" / "evaluation" / "stage29_real_quality_results.csv"
DEFAULT_SUMMARY = ROOT / "data" / "evaluation" / "stage29_real_quality_summary.csv"
DEFAULT_WEIGHTS = ROOT / "data" / "evaluation" / "stage30_scoring_weights.yaml"
DEFAULT_HEALTH = ROOT / "data" / "evaluation" / "stage30_engineering_health.json"
DEFAULT_SCORES = ROOT / "data" / "evaluation" / "stage30_quality_scores.csv"
DEFAULT_SUMMARY_OUT = ROOT / "data" / "evaluation" / "stage30_quality_summary.csv"
DEFAULT_DEDUCTIONS = ROOT / "data" / "evaluation" / "stage30_quality_deductions.csv"

SCORE_FIELDS = [
    "run_id",
    "run_at",
    "scoring_version",
    "scoring_mode",
    "overall_score",
    "grade",
    "release_decision",
    "historical_overall_score",
    "evidence_status",
    "evidence_reasons",
    "manifest_run_id",
    "dimension_scores",
    "score_delta",
    "main_deductions",
    "recommended_actions",
]

SUMMARY_FIELDS = [
    "run_id",
    "dimension",
    "weight",
    "score",
    "max_score",
    "normalized_score",
    "status",
    "evidence",
]

DEDUCTION_FIELDS = [
    "run_id",
    "severity",
    "dimension",
    "query_id",
    "deduction_points",
    "deduction_reason",
    "recommended_action",
    "evidence_file",
]


@dataclass(frozen=True)
class ScoringConfig:
    scoring_version: str
    scoring_mode: str
    weights: dict[str, float]
    grade_boundaries: dict[str, float]
    decision_rules: dict[str, dict[str, object]]
    thresholds: dict[str, float]


@dataclass(frozen=True)
class Deduction:
    severity: str
    dimension: str
    query_id: str
    deduction_points: float
    deduction_reason: str
    recommended_action: str
    evidence_file: str

    def as_dict(self, run_id: str) -> dict[str, str]:
        return {
            "run_id": run_id,
            "severity": self.severity,
            "dimension": self.dimension,
            "query_id": self.query_id,
            "deduction_points": format_score(self.deduction_points),
            "deduction_reason": self.deduction_reason,
            "recommended_action": self.recommended_action,
            "evidence_file": self.evidence_file,
        }


@dataclass(frozen=True)
class ScoringResult:
    run_id: str
    run_at: str
    scoring_version: str
    scoring_mode: str
    dimension_scores: dict[str, float]
    overall_score: float
    grade: str
    release_decision: str
    historical_overall_score: float | None
    evidence_status: str
    evidence_reasons: tuple[str, ...]
    manifest_run_id: str
    score_delta: str
    deductions: list[Deduction]
    recommended_actions: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score stage 30 RAG quality from existing stage 29 CSVs, scoring weights, "
            "and engineering health JSON. This script is read-only for inputs and does "
            "not run pytest, rebuild embeddings, write the database, or call real APIs."
        )
    )
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--engineering-health", default=str(DEFAULT_HEALTH))
    parser.add_argument(
        "--agent-gate-manifest",
        required=True,
        help="Complete, safe Phase 65 AgentGateManifest JSON for this evidence run.",
    )
    parser.add_argument("--pytest-receipt-bundle", required=True)
    parser.add_argument("--scores-out", default=str(DEFAULT_SCORES))
    parser.add_argument("--summary-out", default=str(DEFAULT_SUMMARY_OUT))
    parser.add_argument("--deductions-out", default=str(DEFAULT_DEDUCTIONS))
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--no-append",
        action="store_true",
        help="Overwrite the score history file instead of appending a new run row.",
    )
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_single_row(path: Path) -> dict[str, str]:
    rows = read_rows(path)
    if not rows:
        raise ValueError(f"{path} is empty")
    return rows[0]


def read_health(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class EvidenceStatus:
    status: str
    reasons: tuple[str, ...]
    manifest_run_id: str


def load_verified_test_receipt(
    receipt_path: Path,
    inventory_path: Path,
    *,
    collection_receipt_path: Path | None = None,
    repository_root: Path = ROOT,
) -> dict[str, object]:
    """Read only aggregate JUnit counts bound to a controlled source/test inventory."""
    root = repository_root.resolve()
    for path in (receipt_path, inventory_path):
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("test_receipt_path_outside_repository") from exc
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("test_inventory_invalid") from exc
    paths = inventory.get("paths") if isinstance(inventory, dict) else None
    if inventory.get("schema_version") != "stage30-test-inventory-v1" or not isinstance(paths, list) or not paths:
        raise ValueError("test_inventory_invalid")
    canonical_paths = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "tests").rglob("test_*.py")
        if path.is_file()
    )
    if paths != canonical_paths or len(set(paths)) != len(paths):
        raise ValueError("test_inventory_not_canonical")
    digest = hashlib.sha256()
    for value in paths:
        if not isinstance(value, str) or not value.endswith(".py"):
            raise ValueError("test_inventory_invalid")
        candidate = (root / value).resolve()
        try:
            relative = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("test_inventory_invalid") from exc
        if not relative.startswith("tests/") or not candidate.is_file():
            raise ValueError("test_inventory_invalid")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(candidate).encode("ascii"))
        digest.update(b"\n")
    try:
        root_element = ElementTree.parse(receipt_path).getroot()
        tests = int(root_element.attrib["tests"])
        failures = int(root_element.attrib.get("failures", "0"))
        errors = int(root_element.attrib.get("errors", "0"))
    except (OSError, ElementTree.ParseError, KeyError, ValueError) as exc:
        raise ValueError("pytest_receipt_invalid") from exc
    if (
        root_element.tag.rsplit("}", 1)[-1] not in {"testsuite", "testsuites"}
        or root_element.attrib.get("name") != "pytest"
        or tests <= 0
        or failures != 0
        or errors != 0
    ):
        raise ValueError("pytest_receipt_invalid")
    testcase_nodes = [node for node in root_element.iter() if node.tag.rsplit("}", 1)[-1] == "testcase"]
    if len(testcase_nodes) != tests:
        raise ValueError("pytest_receipt_incomplete")
    module_paths: set[str] = set()
    testcase_ids: set[tuple[str, str]] = set()
    for testcase in testcase_nodes:
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "")
        identity = (classname, name)
        if not classname.startswith("tests.") or not name or identity in testcase_ids:
            raise ValueError("pytest_receipt_incomplete")
        testcase_ids.add(identity)
        matches = [
            path for path in canonical_paths
            if classname == path.removesuffix(".py").replace("/", ".")
            or classname.startswith(path.removesuffix(".py").replace("/", ".") + ".")
        ]
        if len(matches) != 1:
            raise ValueError("pytest_receipt_incomplete")
        module_paths.add(matches[0])
    if module_paths != set(canonical_paths):
        raise ValueError("pytest_receipt_incomplete")
    if collection_receipt_path is not None:
        try:
            collection = json.loads(collection_receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("pytest_collection_invalid") from exc
        node_ids = collection.get("node_ids") if isinstance(collection, dict) else None
        if (
            not isinstance(collection, dict)
            or collection.get("schema_version") != "phase65-test-receipt-v2"
            or collection.get("producer") != PRODUCER
            or collection.get("producer_version") != PRODUCER_VERSION
            or collection.get("collection_command") != "python -m pytest --collect-only -q"
            or collection.get("pytest_command") != "python -m pytest -q --junitxml=<temporary>"
            or not isinstance(collection.get("pytest_executable"), str)
            or not isinstance(collection.get("pytest_version"), str)
            or not isinstance(node_ids, list)
            or not node_ids
            or len(set(node_ids)) != len(node_ids)
            or not all(isinstance(node, str) and node.startswith("tests/") and "::" in node for node in node_ids)
            or collection.get("inventory_sha256") != sha256_file(inventory_path)
            or collection.get("test_tree_sha256") != canonical_test_tree_sha256(root, canonical_paths)
            or collection.get("junit_sha256") != sha256_file(receipt_path)
            or collection.get("node_ids_sha256") != fingerprint_items(sorted(node_ids))
            or collection.get("node_count") != len(node_ids)
        ):
            raise ValueError("pytest_receipt_producer_invalid")
        junit_node_ids = {
            f"{testcase.attrib['classname'].replace('.', '/')}.py::{testcase.attrib['name']}"
            for testcase in testcase_nodes
        }
        if junit_node_ids != set(node_ids) or len(junit_node_ids) != tests:
            raise ValueError("pytest_collection_mismatch")
    return {
        "schema_version": "stage30-pytest-junit-v1",
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "test_suite_sha256": digest.hexdigest(),
        "receipt_sha256": sha256_file(receipt_path),
    }


def evaluate_evidence_status(
    *,
    health: dict[str, object],
    manifest: AgentGateManifest | None,
    test_suite_sha256: str | None,
    test_receipt: dict[str, object] | None = None,
    current_worktree_identity: GitWorktreeIdentity | None = None,
    repository_root: Path = ROOT,
) -> EvidenceStatus:
    """Classify Stage 30 evidence without treating old receipts as current."""
    if manifest is None:
        return EvidenceStatus("blocked", ("manifest_unavailable",), "")
    if not test_suite_sha256:
        return EvidenceStatus("blocked", ("test_inventory_unavailable",), manifest.run_id)
    if (
        manifest.status != "complete"
        or manifest.expected_rows <= 0
        or manifest.completed_rows != manifest.expected_rows
        or manifest.cache_policy != "cold"
        or manifest.environment_class not in {"controlled_candidate", "controlled_production"}
        or manifest.sanitized_errors
        or not manifest.scoped_paths
    ):
        return EvidenceStatus("blocked", ("manifest_incomplete",), manifest.run_id)
    try:
        expected_scope = canonical_phase65_scope(repository_root)
    except (OSError, ValueError):
        return EvidenceStatus("blocked", ("manifest_scope_unavailable",), manifest.run_id)
    if manifest.scoped_paths != expected_scope:
        return EvidenceStatus("blocked", ("manifest_scope_incomplete",), manifest.run_id)
    if not _verified_test_receipt(test_receipt, test_suite_sha256):
        return EvidenceStatus("blocked", ("pytest_receipt_invalid",), manifest.run_id)
    bundle_bindings = {
        "manifest_run_id": manifest.run_id,
        "manifest_base_commit": manifest.base_commit,
        "manifest_tracked_patch_sha256": manifest.tracked_patch_sha256,
        "manifest_scoped_content_sha256": manifest.scoped_content_sha256,
        "manifest_scoped_paths": manifest.scoped_paths,
    }
    if any(field in test_receipt and test_receipt.get(field) != expected for field, expected in bundle_bindings.items()):
        return EvidenceStatus("blocked", ("bundle_manifest_mismatch",), manifest.run_id)
    embedded_manifest = test_receipt.get("manifest")
    canonical_manifest = json.loads(json.dumps(manifest.to_safe_dict(), ensure_ascii=True, sort_keys=True))
    if embedded_manifest is not None and embedded_manifest != canonical_manifest:
        return EvidenceStatus("blocked", ("bundle_manifest_mismatch",), manifest.run_id)
    receipt_fields = ("schema_version", "tests", "failures", "errors", "test_suite_sha256", "receipt_sha256")
    if any(health.get(f"pytest_receipt_{field}") != test_receipt.get(field) for field in receipt_fields):
        return EvidenceStatus("blocked", ("pytest_receipt_mismatch",), manifest.run_id)
    try:
        actual = current_worktree_identity or read_git_worktree_identity(repository_root, manifest.scoped_paths)
    except (OSError, ValueError):
        return EvidenceStatus("blocked", ("worktree_identity_unavailable",), manifest.run_id)
    stale_reasons: list[str] = []
    for field, expected, reason in (
        ("base_commit", manifest.base_commit, "worktree_base_commit_mismatch"),
        ("tracked_patch_sha256", manifest.tracked_patch_sha256, "worktree_tracked_patch_mismatch"),
        ("scoped_content_sha256", manifest.scoped_content_sha256, "worktree_scoped_content_mismatch"),
        ("scoped_paths", manifest.scoped_paths, "worktree_scoped_paths_mismatch"),
    ):
        if getattr(actual, field) != expected:
            stale_reasons.append(reason)
    if test_receipt.get("trust_level") == "local_integrity_only":
        return EvidenceStatus("blocked", tuple(["local_integrity_only", *stale_reasons]), manifest.run_id)
    if health.get("schema_version") != "stage30-engineering-health-v2":
        stale_reasons.append("health_schema_stale")
    expected_bindings = {
        "manifest_run_id": manifest.run_id,
        "base_commit": manifest.base_commit,
        "tracked_patch_sha256": manifest.tracked_patch_sha256,
        "test_suite_sha256": test_suite_sha256,
    }
    for field, expected in expected_bindings.items():
        if health.get(field) != expected:
            stale_reasons.append("test_fingerprint_mismatch" if field == "test_suite_sha256" else f"{field}_mismatch")
    if stale_reasons:
        return EvidenceStatus("stale", tuple(stale_reasons), manifest.run_id)
    return EvidenceStatus("current", (), manifest.run_id)


def _verified_test_receipt(receipt: dict[str, object] | None, expected_suite_sha256: str | None) -> bool:
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "stage30-pytest-junit-v1":
        return False
    tests, failures, errors = receipt.get("tests"), receipt.get("failures"), receipt.get("errors")
    return (
        isinstance(tests, int)
        and not isinstance(tests, bool)
        and tests > 0
        and isinstance(failures, int)
        and failures == 0
        and isinstance(errors, int)
        and errors == 0
        and receipt.get("test_suite_sha256") == expected_suite_sha256
        and isinstance(receipt.get("receipt_sha256"), str)
        and len(str(receipt["receipt_sha256"])) == 64
    )


def parse_scalar(value: str) -> object:
    trimmed = value.strip().strip('"').strip("'")
    if trimmed.lower() == "true":
        return True
    if trimmed.lower() == "false":
        return False
    try:
        if "." in trimmed:
            return float(trimmed)
        return int(trimmed)
    except ValueError:
        return trimmed


def load_scoring_config(path: Path) -> ScoringConfig:
    scoring_version = "stage30-v1"
    scoring_mode = "deterministic_rule_based"
    weights: dict[str, float] = {}
    grade_boundaries: dict[str, float] = {}
    decision_rules: dict[str, dict[str, object]] = {}
    thresholds: dict[str, float] = {}
    section = ""
    current_dimension = ""
    current_decision = ""
    skip_block_indent: int | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if skip_block_indent is not None:
            if indent > skip_block_indent:
                continue
            skip_block_indent = None

        if line.endswith(": >") or line.endswith(": |"):
            skip_block_indent = indent
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if indent == 0:
            section = key
            current_dimension = ""
            current_decision = ""
            if value:
                scalar = parse_scalar(value)
                if key == "scoring_version":
                    scoring_version = str(scalar)
                elif key == "scoring_mode":
                    scoring_mode = str(scalar)
            continue

        if section == "dimensions":
            if indent == 2 and not value:
                current_dimension = key
                continue
            if indent == 4 and key == "weight" and current_dimension:
                weights[current_dimension] = float(parse_scalar(value))
        elif section == "grade_boundaries" and indent == 2:
            grade_boundaries[key] = float(parse_scalar(value))
        elif section == "release_decision_rules":
            if indent == 2 and not value:
                current_decision = key
                decision_rules[current_decision] = {}
                continue
            if indent == 4 and current_decision and value:
                decision_rules[current_decision][key] = parse_scalar(value)
        elif section == "deduction_thresholds" and indent == 2:
            thresholds[key] = float(parse_scalar(value))

    total_weight = sum(weights.values())
    if round(total_weight, 6) != 100:
        raise ValueError(f"stage30 scoring weights must sum to 100, got {total_weight}")
    required = {
        "retrieval_quality",
        "rule_based_context_answer_quality",
        "safety_refusal",
        "source_quality",
        "engineering_health",
    }
    missing = sorted(required - set(weights))
    if missing:
        raise ValueError(f"missing scoring dimensions: {', '.join(missing)}")

    return ScoringConfig(
        scoring_version=scoring_version,
        scoring_mode=scoring_mode,
        weights=weights,
        grade_boundaries=grade_boundaries or {"A": 90, "B": 80, "C": 70, "D": 60, "F": 0},
        decision_rules=decision_rules,
        thresholds=thresholds,
    )


def to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bool_text(value: str) -> bool:
    return value.strip().lower() == "true"


def parse_distribution(value: str) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for item in (value or "").split(";"):
        if not item.strip() or ":" not in item:
            continue
        key, count = item.split(":", 1)
        try:
            distribution[key.strip()] = int(count)
        except ValueError:
            distribution[key.strip()] = 0
    return distribution


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_retrieval(summary: dict[str, str], weight: float) -> float:
    p1 = to_float(summary.get("precision_at_1"))
    p3 = to_float(summary.get("precision_at_3"))
    p5 = to_float(summary.get("precision_at_5"))
    normalized = clamp((p1 * 0.45) + (p3 * 0.25) + (p5 * 0.30))
    return normalized * weight


def score_context_answer(summary: dict[str, str], weight: float) -> float:
    coverage = to_float(summary.get("avg_coverage_ratio"))
    return clamp(coverage) * weight


def score_safety(summary: dict[str, str], weight: float) -> float:
    refusal_accuracy = to_float(summary.get("refusal_accuracy"))
    return clamp(refusal_accuracy) * weight


def score_source_quality(rows: list[dict[str, str]], summary: dict[str, str], weight: float) -> float:
    distribution = parse_distribution(summary.get("source_type_distribution", ""))
    total = sum(distribution.values())
    distinct_ratio = clamp(len([count for count in distribution.values() if count > 0]) / 5.0)
    weak_count = distribution.get("metadata_record", 0) + distribution.get("local_file", 0)
    weak_ratio = (weak_count / total) if total else 1.0
    non_refusal_rows = [row for row in rows if row.get("expected_refused") == "false"]
    expected_misses = [
        row
        for row in non_refusal_rows
        if row.get("expected_source_type") and row.get("expected_source_type") not in row.get("source_type_distribution", "")
    ]
    miss_ratio = (len(expected_misses) / len(non_refusal_rows)) if non_refusal_rows else 0.0
    normalized = (0.60 * distinct_ratio) + (0.25 * (1 - clamp(weak_ratio))) + (0.15 * (1 - clamp(miss_ratio)))
    return clamp(normalized) * weight


def score_engineering_health(health: dict[str, object], weight: float) -> float:
    chunk_count = int(health.get("chunk_count") or 0)
    embedding_count = int(health.get("embedding_count") or 0)
    jina_count = int(health.get("jina_embedding_count") or 0)
    deterministic_count = int(health.get("deterministic_embedding_count") or 0)
    index_ok = (
        chunk_count > 0
        and embedding_count == chunk_count * 2
        and jina_count == chunk_count
        and deterministic_count == chunk_count
    )
    no_orphans = int(health.get("orphan_embeddings") or 0) == 0
    no_duplicates = int(health.get("duplicate_provider_model_groups") or 0) == 0
    tests_ok = "passed" in str(health.get("full_tests_status", "")).lower()
    smoke_ok = "passed" in str(health.get("quality_report_smoke", "")).lower()
    normalized = (
        (0.30 if tests_ok else 0.0)
        + (0.30 if index_ok else 0.0)
        + (0.20 if no_orphans and no_duplicates else 0.0)
        + (0.20 if smoke_ok else 0.0)
    )
    return normalized * weight


def build_deductions(
    rows: list[dict[str, str]],
    summary: dict[str, str],
    health: dict[str, object],
    config: ScoringConfig,
) -> list[Deduction]:
    deductions: list[Deduction] = []
    low_coverage_threshold = config.thresholds.get("low_coverage_ratio", 0.5)
    p5_minimum = config.thresholds.get("retrieval_precision_at_5_minimum", 0.9)
    refusal_minimum = config.thresholds.get("refusal_accuracy_minimum", 1.0)

    for row in rows:
        if row.get("expected_refused") != "false":
            continue
        query_id = row.get("query_id", "")
        if not bool_text(row.get("precision_at_5", "")):
            deductions.append(
                Deduction(
                    severity="medium",
                    dimension="retrieval_quality",
                    query_id=query_id,
                    deduction_points=2.0,
                    deduction_reason=(
                        "Top-5 retrieval did not include the expected source type; "
                        "this remains a manual review item from stage 29."
                    ),
                    recommended_action="Review query design, expected source labeling, and top-k evidence before claiming release readiness.",
                    evidence_file="data/evaluation/stage29_real_quality_results.csv",
                )
            )
        coverage = to_float(row.get("coverage_ratio"))
        if coverage < low_coverage_threshold:
            deductions.append(
                Deduction(
                    severity="medium",
                    dimension="rule_based_context_answer_quality",
                    query_id=query_id,
                    deduction_points=2.0,
                    deduction_reason=(
                        f"Rule-based coverage_ratio={coverage:.3f} is below "
                        f"{low_coverage_threshold:.3f}; this is not a semantic faithfulness score."
                    ),
                    recommended_action="Inspect missing answer points and decide whether retrieval, corpus labeling, or the expected points need calibration.",
                    evidence_file="data/evaluation/stage29_real_quality_results.csv",
                )
            )

    if to_float(summary.get("precision_at_5")) < p5_minimum:
        deductions.append(
            Deduction(
                severity="medium",
                dimension="retrieval_quality",
                query_id="summary",
                deduction_points=1.0,
                deduction_reason=f"precision_at_5 is below configured minimum {p5_minimum:.3f}.",
                recommended_action="Keep retrieval quality in review_required until top-k misses are resolved or accepted by human review.",
                evidence_file="data/evaluation/stage29_real_quality_summary.csv",
            )
        )

    if to_float(summary.get("refusal_accuracy")) < refusal_minimum:
        deductions.append(
            Deduction(
                severity="blocking",
                dimension="safety_refusal",
                query_id="summary",
                deduction_points=8.0,
                deduction_reason="Refusal accuracy is below the configured safety threshold.",
                recommended_action="Block release until engineering responsibility and sensitive-boundary refusal cases pass.",
                evidence_file="data/evaluation/stage29_real_quality_summary.csv",
            )
        )

    if int(health.get("orphan_embeddings") or 0) > 0:
        deductions.append(
            Deduction(
                severity="blocking",
                dimension="engineering_health",
                query_id="engineering_health",
                deduction_points=5.0,
                deduction_reason="Orphan embeddings were detected.",
                recommended_action="Reconcile chunk_embeddings with chunks before using scoring outputs.",
                evidence_file="data/evaluation/stage30_engineering_health.json",
            )
        )
    if int(health.get("duplicate_provider_model_groups") or 0) > 0:
        deductions.append(
            Deduction(
                severity="blocking",
                dimension="engineering_health",
                query_id="engineering_health",
                deduction_points=5.0,
                deduction_reason="Duplicate provider/model/chunk embedding groups were detected.",
                recommended_action="Clean duplicate embeddings before using scoring outputs.",
                evidence_file="data/evaluation/stage30_engineering_health.json",
            )
        )

    return deductions


def grade_for_score(score: float, boundaries: dict[str, float]) -> str:
    ordered = sorted(boundaries.items(), key=lambda item: item[1], reverse=True)
    for grade, minimum in ordered:
        if score >= minimum:
            return grade
    return "F"


def release_decision(overall: float, engineering_score: float, deductions: list[Deduction], config: ScoringConfig) -> str:
    if any(item.severity == "blocking" for item in deductions):
        return "blocked"
    pass_rule = config.decision_rules.get("pass", {})
    review_rule = config.decision_rules.get("review_required", {})
    pass_min = to_float(pass_rule.get("min_overall_score"), 85)
    review_min = to_float(review_rule.get("min_overall_score"), 70)
    min_engineering = to_float(pass_rule.get("min_engineering_health_score"), 8)
    has_medium = any(item.severity in {"medium", "high"} for item in deductions)
    if overall >= pass_min and engineering_score >= min_engineering and not has_medium:
        return "pass"
    if overall >= review_min:
        return "review_required"
    return "blocked"


def previous_score_delta(scores_path: Path, current_score: float) -> str:
    if not scores_path.exists():
        return ""
    rows = read_rows(scores_path)
    if not rows:
        return ""
    previous = to_float(rows[-1].get("overall_score"))
    return format_score(current_score - previous, digits=3)


def score_quality(
    rows: list[dict[str, str]],
    summary: dict[str, str],
    health: dict[str, object],
    config: ScoringConfig,
    *,
    run_id: str,
    run_at: str,
    previous_scores_path: Path,
    manifest: AgentGateManifest | None = None,
    test_suite_sha256: str | None = None,
    test_receipt: dict[str, object] | None = None,
    current_worktree_identity: GitWorktreeIdentity | None = None,
) -> ScoringResult:
    dimension_scores = {
        "retrieval_quality": score_retrieval(summary, config.weights["retrieval_quality"]),
        "rule_based_context_answer_quality": score_context_answer(
            summary,
            config.weights["rule_based_context_answer_quality"],
        ),
        "safety_refusal": score_safety(summary, config.weights["safety_refusal"]),
        "source_quality": score_source_quality(rows, summary, config.weights["source_quality"]),
        "engineering_health": score_engineering_health(health, config.weights["engineering_health"]),
    }
    deductions = build_deductions(rows, summary, health, config)
    overall = sum(dimension_scores.values())
    grade = grade_for_score(overall, config.grade_boundaries)
    computed_decision = release_decision(
        overall,
        dimension_scores["engineering_health"],
        deductions,
        config,
    )
    evidence = evaluate_evidence_status(
        health=health,
        manifest=manifest,
        test_suite_sha256=test_suite_sha256,
        test_receipt=test_receipt,
        current_worktree_identity=current_worktree_identity,
    )
    decision = computed_decision if evidence.status == "current" else "blocked"
    recommended_actions = sorted(
        {item.recommended_action for item in deductions}
        or {"Continue human review of the stage 30 score report before commit/tag/push."}
    )
    if evidence.status != "current":
        recommended_actions.append("Refresh Stage 30 evidence against the current Phase 65 manifest before release review.")
    return ScoringResult(
        run_id=run_id,
        run_at=run_at,
        scoring_version=config.scoring_version,
        scoring_mode=config.scoring_mode,
        dimension_scores=dimension_scores,
        overall_score=overall,
        grade=grade,
        release_decision=decision,
        historical_overall_score=overall if evidence.status != "current" else None,
        evidence_status=evidence.status,
        evidence_reasons=evidence.reasons,
        manifest_run_id=evidence.manifest_run_id,
        score_delta=previous_score_delta(previous_scores_path, overall),
        deductions=deductions,
        recommended_actions=recommended_actions,
    )


def format_score(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def csv_safe(value: object) -> object:
    """Prevent spreadsheet formula execution in every persisted CSV cell."""
    if isinstance(value, str):
        normalized = " ".join(value.replace("\r", " ").replace("\n", " ").replace("\t", " ").split())
        if normalized.startswith(("=", "+", "-", "@")):
            return f"'{normalized}"
        return normalized
    return value


def csv_safe_row(row: dict[str, object]) -> dict[str, object]:
    return {field: csv_safe(value) for field, value in row.items()}


def write_scores(path: Path, result: ScoringResult, *, append: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": result.run_id,
        "run_at": result.run_at,
        "scoring_version": result.scoring_version,
        "scoring_mode": result.scoring_mode,
        "overall_score": format_score(result.overall_score),
        "grade": result.grade,
        "release_decision": result.release_decision,
        "historical_overall_score": (
            format_score(result.historical_overall_score)
            if result.historical_overall_score is not None
            else ""
        ),
        "evidence_status": result.evidence_status,
        "evidence_reasons": "|".join(result.evidence_reasons),
        "manifest_run_id": result.manifest_run_id,
        "dimension_scores": json.dumps(result.dimension_scores, ensure_ascii=False, sort_keys=True),
        "score_delta": result.score_delta,
        "main_deductions": "; ".join(
            f"{item.dimension}:{item.query_id}:{item.severity}" for item in result.deductions[:5]
        ),
        "recommended_actions": " | ".join(result.recommended_actions),
    }
    legacy_rows: list[dict[str, str]] = []
    if append and path.exists() and path.stat().st_size:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != SCORE_FIELDS:
                legacy_rows = list(reader)
                append = False
    should_write_header = not append or not path.exists() or path.stat().st_size == 0
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SCORE_FIELDS)
        if should_write_header:
            writer.writeheader()
        writer.writerows(csv_safe_row({field: legacy.get(field, "") for field in SCORE_FIELDS}) for legacy in legacy_rows)
        writer.writerow(csv_safe_row(row))


def write_summary(path: Path, result: ScoringResult, config: ScoringConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for dimension, score in result.dimension_scores.items():
            weight = config.weights[dimension]
            normalized = score / weight if weight else 0
            writer.writerow(
                csv_safe_row({
                    "run_id": result.run_id,
                    "dimension": dimension,
                    "weight": format_score(weight),
                    "score": format_score(score),
                    "max_score": format_score(weight),
                    "normalized_score": format_score(normalized, digits=3),
                    "status": dimension_status(normalized),
                    "evidence": evidence_for_dimension(dimension),
                })
            )
        writer.writerow(
            csv_safe_row({
                "run_id": result.run_id,
                "dimension": "overall",
                "weight": "100.00",
                "score": format_score(result.overall_score),
                "max_score": "100.00",
                "normalized_score": format_score(result.overall_score / 100, digits=3),
                "status": result.release_decision,
                "evidence": f"grade={result.grade}; scoring_mode={result.scoring_mode}",
            })
        )


def dimension_status(normalized: float) -> str:
    if normalized >= 0.85:
        return "strong"
    if normalized >= 0.70:
        return "review_required"
    return "weak"


def evidence_for_dimension(dimension: str) -> str:
    mapping = {
        "retrieval_quality": "precision_at_1/3/5 from stage29_real_quality_summary.csv",
        "rule_based_context_answer_quality": "avg_coverage_ratio from stage29_real_quality_summary.csv",
        "safety_refusal": "refusal_accuracy from stage29_real_quality_summary.csv",
        "source_quality": "source_type_distribution and expected source misses",
        "engineering_health": "stage30_engineering_health.json",
    }
    return mapping.get(dimension, "")


def write_deductions(path: Path, result: ScoringResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DEDUCTION_FIELDS)
        writer.writeheader()
        writer.writerows(csv_safe_row(item.as_dict(result.run_id)) for item in result.deductions)


def main() -> None:
    args = parse_args()
    config = load_scoring_config(Path(args.weights))
    rows = read_rows(Path(args.results))
    summary = read_single_row(Path(args.summary))
    health = read_health(Path(args.engineering_health))
    manifest = load_manifest(Path(args.agent_gate_manifest))
    test_receipt = load_bundle_test_receipt(Path(args.pytest_receipt_bundle))
    run_id = args.run_id.strip() or f"stage30-{uuid4().hex[:12]}"
    run_at = datetime.now(timezone.utc).isoformat()
    result = score_quality(
        rows,
        summary,
        health,
        config,
        run_id=run_id,
        run_at=run_at,
        previous_scores_path=Path(args.scores_out),
        manifest=manifest,
        test_suite_sha256=str(test_receipt["test_suite_sha256"]),
        test_receipt=test_receipt,
    )
    write_scores(Path(args.scores_out), result, append=not args.no_append)
    write_summary(Path(args.summary_out), result, config)
    write_deductions(Path(args.deductions_out), result)
    print(
        "stage30 quality score "
        f"overall={format_score(result.overall_score)} "
        f"grade={result.grade} "
        f"release_decision={result.release_decision}"
    )


if __name__ == "__main__":
    main()

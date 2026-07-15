"""Produce a safe, bound Phase 65 pytest receipt on a trusted runner."""

from __future__ import annotations

import hashlib
import json
import argparse
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase65_gate_manifest import AgentGateManifest, canonical_phase65_scope, load_manifest, load_manifest_payload, sha256_file


PRODUCER = "scripts/verify_phase65_test_receipt.py"
PRODUCER_VERSION = "phase65-test-receipt-producer-v1"
BUNDLE_SCHEMA = "phase65-test-receipt-bundle-v3"
_MANIFEST_FIELDS = frozenset(AgentGateManifest.__dataclass_fields__)


def canonical_test_paths(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in (root / "tests").rglob("test_*.py") if path.is_file())


def fingerprint_items(items: list[str]) -> str:
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def canonical_test_tree_sha256(root: Path, paths: list[str]) -> str:
    return fingerprint_items([f"{path}:{sha256_file(root / path)}" for path in paths])


def build_producer_receipt(*, root: Path, inventory_path: Path, junit_path: Path, node_ids: list[str], pytest_version: str, manifest: dict[str, object]) -> dict[str, object]:
    paths = canonical_test_paths(root)
    return {
        "schema_version": "phase65-test-receipt-v2",
        "producer": PRODUCER,
        "producer_version": PRODUCER_VERSION,
        "collection_command": "python -m pytest --collect-only -q",
        "pytest_command": "python -m pytest -q --junitxml=<temporary>",
        "pytest_executable": sys.executable,
        "pytest_version": pytest_version,
        "inventory_sha256": sha256_file(inventory_path),
        "test_tree_sha256": canonical_test_tree_sha256(root, paths),
        "junit_sha256": sha256_file(junit_path),
        "node_ids": sorted(node_ids),
        "node_ids_sha256": fingerprint_items(sorted(node_ids)),
        "node_count": len(node_ids),
        "manifest_base_commit": manifest.get("base_commit", ""),
        "manifest_tracked_patch_sha256": manifest.get("tracked_patch_sha256", ""),
        "manifest_scoped_content_sha256": manifest.get("scoped_content_sha256", ""),
    }


def validate_receipt_bundle(bundle_directory: Path, *, repository_root: Path | None = None) -> dict[str, object]:
    """Validate a persisted local-integrity bundle; this is not CI attestation."""
    bundle = bundle_directory.resolve()
    root = (repository_root or Path(__file__).resolve().parents[1]).resolve()
    try:
        bundle.relative_to(root)
    except ValueError as exc:
        raise ValueError("receipt_bundle_invalid") from exc
    try:
        payload = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("receipt_bundle_invalid") from exc
    required = {"schema_version", "producer", "producer_version", "verifier_sha256", "pytest_executable", "pytest_version", "collection_command", "pytest_command", "manifest", "artifacts", "trust_level", "generated_at"}
    if not isinstance(payload, dict) or not required.issubset(payload) or payload.get("schema_version") != BUNDLE_SCHEMA or payload.get("producer") != PRODUCER or payload.get("producer_version") != PRODUCER_VERSION or payload.get("trust_level") != "local_integrity_only" or payload.get("verifier_sha256") != sha256_file(Path(__file__)):
        raise ValueError("receipt_bundle_invalid")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"inventory", "collection", "junit"}:
        raise ValueError("receipt_bundle_invalid")
    for name, details in artifacts.items():
        if not isinstance(details, dict) or not isinstance(details.get("path"), str) or not isinstance(details.get("sha256"), str):
            raise ValueError("receipt_bundle_invalid")
        target = (bundle / details["path"]).resolve()
        try:
            target.relative_to(bundle)
        except ValueError as exc:
            raise ValueError("receipt_bundle_invalid") from exc
        if not target.is_file() or sha256_file(target) != details["sha256"]:
            raise ValueError("receipt_bundle_invalid")
    manifest = payload.get("manifest")
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS:
        raise ValueError("receipt_bundle_invalid")
    try:
        # Reuse the manifest parser so untrusted bundle JSON gets the same
        # finite-domain and unsafe-content checks as on-disk manifests.
        candidate_manifest = load_manifest_payload(manifest)
        _validate_bundle_manifest(candidate_manifest)
    except (TypeError, ValueError):
        raise ValueError("receipt_bundle_invalid") from None
    if tuple(candidate_manifest.scoped_paths) != canonical_phase65_scope(root):
        raise ValueError("receipt_bundle_invalid")
    current_pytest_version = subprocess.run(
        [sys.executable, "-m", "pytest", "--version"], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()
    if (
        payload.get("pytest_executable") != sys.executable
        or payload.get("pytest_version") != current_pytest_version
        or payload.get("collection_command") != f"{sys.executable} -m pytest --collect-only -q"
        or payload.get("pytest_command") != f"{sys.executable} -m pytest -q --junitxml=<bundle>/junit.xml"
    ):
        raise ValueError("receipt_bundle_invalid")
    if payload.get("test_tree_sha256") != canonical_test_tree_sha256(root, canonical_test_paths(root)):
        raise ValueError("receipt_bundle_invalid")
    return payload


def load_bundle_test_receipt(bundle_directory: Path, *, repository_root: Path | None = None) -> dict[str, object]:
    payload = validate_receipt_bundle(bundle_directory, repository_root=repository_root)
    bundle = bundle_directory.resolve()
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, dict)
    junit = bundle / str(artifacts["junit"]["path"])
    collection = bundle / str(artifacts["collection"]["path"])
    try:
        root_element = ElementTree.parse(junit).getroot()
        tests = int(root_element.attrib["tests"])
        failures = int(root_element.attrib.get("failures", "0"))
        errors = int(root_element.attrib.get("errors", "0"))
        node_ids = json.loads(collection.read_text(encoding="utf-8"))["node_ids"]
    except (OSError, ValueError, KeyError, ElementTree.ParseError, json.JSONDecodeError) as exc:
        raise ValueError("receipt_bundle_invalid") from exc
    if (
        root_element.attrib.get("name") != "pytest"
        or not isinstance(node_ids, list)
        or not all(isinstance(node_id, str) for node_id in node_ids)
        or node_ids != sorted(set(node_ids))
        or tests != len(node_ids)
        or failures != 0
        or errors != 0
        or fingerprint_items(node_ids) != payload.get("node_ids_sha256")
        or _junit_node_ids(root_element) != node_ids
    ):
        raise ValueError("receipt_bundle_invalid")
    manifest = payload["manifest"]
    assert isinstance(manifest, dict)
    return {
        "schema_version": "stage30-pytest-junit-v1", "tests": tests, "failures": failures, "errors": errors,
        "test_suite_sha256": payload["test_tree_sha256"], "receipt_sha256": artifacts["junit"]["sha256"],
        "trust_level": "local_integrity_only", "manifest_run_id": manifest["run_id"],
        "manifest_base_commit": manifest["base_commit"], "manifest_tracked_patch_sha256": manifest["tracked_patch_sha256"],
        "manifest_scoped_content_sha256": manifest["scoped_content_sha256"], "manifest_scoped_paths": tuple(manifest["scoped_paths"]),
        "manifest": manifest,
    }


def _validate_bundle_manifest(manifest: AgentGateManifest) -> None:
    """Enforce the manifest's finite safe domains without accepting raw JSON fields."""
    if (
        manifest.schema_version != "phase65-agent-gate-v1"
        or manifest.variant not in {"baseline", "candidate"}
        or manifest.status not in {"started", "complete", "failed"}
        or manifest.environment_class not in {"controlled_candidate", "controlled_production"}
        or not manifest.run_id
        or not manifest.scoped_paths
    ):
        raise ValueError("invalid bundle manifest")


def _junit_node_ids(root_element: ElementTree.Element) -> list[str]:
    """Rebuild pytest node IDs from JUnit classname/name, preserving execution order."""
    node_ids: list[str] = []
    for testcase in root_element.iter():
        if testcase.tag.rsplit("}", 1)[-1] != "testcase":
            continue
        classname, name = testcase.attrib.get("classname", ""), testcase.attrib.get("name", "")
        if not classname.startswith("tests.") or not name:
            raise ValueError("receipt_bundle_invalid")
        pieces = classname.split(".")
        module_parts: list[str] = []
        class_parts: list[str] = []
        for piece in pieces:
            if not class_parts and piece and piece[0].islower():
                module_parts.append(piece)
            else:
                class_parts.append(piece)
        if not module_parts:
            raise ValueError("receipt_bundle_invalid")
        module_path = "/".join(module_parts) + ".py"
        suffix = "::".join([*class_parts, name])
        node_ids.append(f"{module_path}::{suffix}")
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("receipt_bundle_invalid")
    return node_ids


def produce_receipt_bundle(*, root: Path, manifest_path: Path, output_directory: Path) -> Path:
    """Run collection and full pytest once, validate them together, then atomically persist a v3 bundle."""
    repository = root.resolve()
    destination = output_directory.resolve()
    try:
        destination.relative_to(repository)
    except ValueError as exc:
        raise ValueError("receipt_output_outside_repository") from exc
    manifest = load_manifest(manifest_path)
    if manifest.scoped_paths != canonical_phase65_scope(repository):
        raise ValueError("receipt_manifest_scope_incomplete")
    pytest_version = subprocess.run([sys.executable, "-m", "pytest", "--version"], cwd=repository, check=True, text=True, capture_output=True).stdout.strip()
    collection_command = f"{sys.executable} -m pytest --collect-only -q"
    pytest_command = f"{sys.executable} -m pytest -q --junitxml=<bundle>/junit.xml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary)
        inventory_path = staging / "inventory.json"
        paths = canonical_test_paths(repository)
        inventory_path.write_text(json.dumps({"schema_version": "stage30-test-inventory-v1", "paths": paths}, sort_keys=True), encoding="utf-8")
        collection_run = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=repository, check=True, text=True, capture_output=True)
        node_ids = sorted(line.strip() for line in collection_run.stdout.splitlines() if line.strip().startswith("tests/") and "::" in line)
        collection_path = staging / "collection.json"
        collection_path.write_text(json.dumps({"node_ids": node_ids}, sort_keys=True), encoding="utf-8")
        junit_path = staging / "junit.xml"
        subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={junit_path}"], cwd=repository, check=True)
        artifacts = {name: {"path": path.name, "sha256": sha256_file(path)} for name, path in {"inventory": inventory_path, "collection": collection_path, "junit": junit_path}.items()}
        bundle = {"schema_version": BUNDLE_SCHEMA, "producer": PRODUCER, "producer_version": PRODUCER_VERSION, "verifier_sha256": sha256_file(Path(__file__)), "pytest_executable": sys.executable, "pytest_version": pytest_version, "collection_command": collection_command, "pytest_command": pytest_command, "manifest": manifest.to_safe_dict(), "artifacts": artifacts, "trust_level": "local_integrity_only", "generated_at": datetime.now(timezone.utc).isoformat(), "test_tree_sha256": canonical_test_tree_sha256(repository, paths), "node_ids_sha256": fingerprint_items(node_ids), "node_count": len(node_ids)}
        (staging / "bundle.json").write_text(json.dumps(bundle, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if destination.exists():
            raise ValueError("receipt_output_exists")
        staging.replace(destination)
    return destination


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Produce one persisted Phase65 pytest receipt bundle.")
    parser.add_argument("--agent-gate-manifest", required=True)
    parser.add_argument("--out-bundle", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    manifest_path = Path(args.agent_gate_manifest).resolve()
    out_bundle = Path(args.out_bundle).resolve()
    default_parent = root / "data" / "evaluation" / "phase65"
    try:
        out_bundle.relative_to(default_parent)
    except ValueError as exc:
        raise ValueError("receipt_output_outside_phase65_directory") from exc
    bundle = produce_receipt_bundle(root=root, manifest_path=manifest_path, output_directory=out_bundle)
    print(json.dumps({"bundle": str(bundle.relative_to(root)), "trust_level": "local_integrity_only"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.phase65_gate_manifest import AgentGateManifest, write_manifest
from scripts.verify_phase65_test_receipt import produce_receipt_bundle, validate_receipt_bundle


def test_v3_bundle_rejects_legacy_v2_or_untrusted_local_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "phase65"
    bundle.mkdir()
    (bundle / "bundle.json").write_text(json.dumps({"schema_version": "phase65-test-receipt-v2"}), encoding="utf-8")

    with pytest.raises(ValueError, match="receipt_bundle_invalid"):
        validate_receipt_bundle(bundle)


def test_direct_receipt_script_help_bootstraps_repository_imports() -> None:
    root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [sys.executable, "scripts/verify_phase65_test_receipt.py", "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--agent-gate-manifest" in completed.stdout


def test_producer_persists_atomic_bundle_with_missing_output_parent(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_example.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    manifest = AgentGateManifest(
        schema_version="phase65-agent-gate-v1", run_id="run-1", variant="candidate", status="complete",
        base_commit="a" * 40, tracked_patch_sha256="b" * 64, scoped_content_sha256="c" * 64,
        scoped_paths=("tests/test_example.py",), evaluator_sha256="d" * 64, case_set_sha256="e" * 64,
        prompt_sha256="f" * 64, tool_schema_sha256="1" * 64, corpus_fingerprint="corpus",
        index_fingerprint="index", provider_models=("provider:model",), endpoint_identity_sha256="2" * 64,
        judge_receipt_contract_sha256="3" * 64, cache_policy="cold", environment_class="controlled_candidate",
        expected_rows=1, completed_rows=1, started_at="2026-07-14T00:00:00+00:00", completed_at="2026-07-14T00:00:01+00:00",
    )
    manifest_path = root / "manifest.json"
    write_manifest(manifest_path, manifest)
    destination = root / "data" / "evaluation" / "phase65" / "bundle"
    seen_temp_dirs: list[Path] = []

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[-1] == "--version":
            return subprocess.CompletedProcess(args, 0, "pytest 8.3.0", "")
        if "--collect-only" in args:
            return subprocess.CompletedProcess(args, 0, "tests/test_example.py::test_ok\n1 test collected\n", "")
        junit_arg = next(str(arg) for arg in args if str(arg).startswith("--junitxml="))
        Path(junit_arg.split("=", 1)[1]).write_text(
            '<testsuite name="pytest" tests="1" failures="0" errors="0"><testcase classname="tests.test_example" name="test_ok"/></testsuite>',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, "", "")

    import scripts.verify_phase65_test_receipt as receipt
    original_temporary_directory = receipt.tempfile.TemporaryDirectory

    def recording_temporary_directory(*args: object, **kwargs: object):
        seen_temp_dirs.append(Path(str(kwargs["dir"])))
        return original_temporary_directory(*args, **kwargs)

    with patch.object(receipt.subprocess, "run", side_effect=fake_run), patch.object(
        receipt.tempfile, "TemporaryDirectory", side_effect=recording_temporary_directory
    ), patch.object(receipt, "canonical_phase65_scope", return_value=("tests/test_example.py",)):
        result = produce_receipt_bundle(root=root, manifest_path=manifest_path, output_directory=destination)

        payload = json.loads((destination / "bundle.json").read_text(encoding="utf-8"))
        payload["manifest"]["sanitized_errors"] = ["authorization=should-not-parse"]
        (destination / "bundle.json").write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="receipt_bundle_invalid"):
            validate_receipt_bundle(destination, repository_root=root)

    assert result == destination
    assert (destination / "bundle.json").is_file()
    assert seen_temp_dirs == [destination.parent]

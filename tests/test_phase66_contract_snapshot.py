from pathlib import Path
import subprocess
import sys

import pytest

from scripts.snapshot_phase66_agent_contract import build_phase66_contract_snapshot


def test_phase66_contract_snapshot_wraps_phase65_contract(tmp_path: Path) -> None:
    output = tmp_path / "repo" / "output" / "phase66" / "baseline" / "agent-contract.json"
    snapshot = build_phase66_contract_snapshot(
        repository_root=tmp_path / "repo",
        output_path=output,
        command_args=["--output", str(output)],
    )

    assert snapshot["schema_version"] == 1
    assert snapshot["phase"] == 66
    assert snapshot["phase65_contract"]["schema_version"] == "phase65-contract-v1"
    assert snapshot["git_head"]
    assert snapshot["tracked_diff_sha256"]
    assert snapshot["request_schema_sha256"]
    assert snapshot["response_schema_sha256"]
    assert snapshot["sse_event_schema_sha256"]
    assert snapshot["command_receipt"]["argv"] == ["--output", str(output)]


def test_phase66_contract_snapshot_rejects_output_outside_phase66(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="output/phase66"):
        build_phase66_contract_snapshot(
            repository_root=tmp_path,
            output_path=tmp_path / "output" / "phase65" / "agent-contract.json",
            command_args=[],
        )


def test_phase66_contract_cli_runs_as_direct_script(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    output = repository_root / "output" / "phase66" / "baseline" / "agent-contract.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/snapshot_phase66_agent_contract.py",
            "--repository-root",
            str(repository_root),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()

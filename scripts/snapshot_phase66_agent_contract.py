"""Build the Phase 66 agent contract snapshot.

This is a named Phase 66 entry point around the existing Phase 65 contract
snapshot. It adds git/working-tree receipt metadata and constrains writes to
the local Phase 66 output area.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.snapshot_phase65_agent_contract import build_contract_snapshot


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_head(repository_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repository_root), "rev-parse", "--short=8", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _tracked_diff_sha256(repository_root: Path) -> str:
    try:
        diff = subprocess.check_output(
            ["git", "-C", str(repository_root), "diff", "--binary", "HEAD", "--"],
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        diff = b""
    return hashlib.sha256(diff).hexdigest()


def _resolve_output(repository_root: Path, output_path: Path) -> Path:
    repository_root = repository_root.resolve()
    if not output_path.is_absolute():
        output_path = repository_root / output_path
    output_path = output_path.resolve()
    allowed_root = (repository_root / "output" / "phase66").resolve()
    try:
        output_path.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("Phase 66 contract output must be under output/phase66/") from exc
    return output_path


def build_phase66_contract_snapshot(
    repository_root: Path,
    output_path: Path,
    command_args: list[str],
) -> dict[str, object]:
    resolved_output = _resolve_output(repository_root, output_path)
    phase65 = build_contract_snapshot()
    return {
        "schema_version": 1,
        "phase": 66,
        "git_head": _git_head(repository_root),
        "captured_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "tracked_diff_sha256": _tracked_diff_sha256(repository_root),
        "request_schema_sha256": phase65["agent_request_schema_sha256"],
        "response_schema_sha256": phase65["agent_response_schema_sha256"],
        "tool_schema_sha256": phase65["tool_schema_sha256"],
        "sse_event_schema_sha256": phase65["sse_fixture_sha256"],
        "checkpoint_schema_sha256": phase65["checkpoint_schema_sha256"],
        "runtime_event_names": phase65["runtime_event_names"],
        "phase65_contract": phase65,
        "phase65_contract_sha256": _canonical_sha256(phase65),
        "command_receipt": {
            "argv": list(command_args),
            "repository_root": str(repository_root),
            "output": str(resolved_output),
            "entrypoint": "scripts/snapshot_phase66_agent_contract.py",
        },
    }


def write_snapshot(
    repository_root: Path,
    output_path: Path,
    command_args: list[str],
) -> dict[str, object]:
    resolved_output = _resolve_output(repository_root, output_path)
    snapshot = build_phase66_contract_snapshot(
        repository_root=repository_root,
        output_path=resolved_output,
        command_args=command_args,
    )
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/phase66/baseline/agent-contract.json"),
    )
    args = parser.parse_args(argv)
    command_args = list(sys.argv[1:] if argv is None else argv)
    snapshot = write_snapshot(
        repository_root=args.repository_root,
        output_path=args.output,
        command_args=command_args,
    )
    print(
        "schema_version={schema_version} phase={phase} git_head={git_head}".format(
            **snapshot
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

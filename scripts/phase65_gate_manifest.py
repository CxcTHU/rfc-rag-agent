"""Safe, deterministic manifest primitives for Phase 65 quality gates."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Sequence


SCHEMA_VERSION = "phase65-agent-gate-v1"
Variant = Literal["baseline", "candidate"]
RunStatus = Literal["started", "incomplete", "complete", "failed"]
_VALID_VARIANTS = frozenset(("baseline", "candidate"))
_VALID_STATUSES = frozenset(("started", "incomplete", "complete", "failed"))
_VALID_ENVIRONMENT_CLASSES = frozenset(("controlled_candidate", "controlled_production", "dry_run"))
_UNSAFE_MANIFEST_PATTERNS = (
    re.compile(r"\bauthorization\s*[:=]", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|x-api-key|secret|password)\s*[:=]", re.IGNORECASE),
    re.compile(r"\braw[_ -]?response\b", re.IGNORECASE),
    re.compile(r"\bprovider[_ -]?payload\b", re.IGNORECASE),
    re.compile(r"\b(?:final_)?answer\b[\"']?\s*[:=]", re.IGNORECASE),
    re.compile(r"\bevidence\b[\"']?\s*[:=]", re.IGNORECASE),
    re.compile(r"\b(?:reasoning(?:_content)?|chain[_ -]?of[_ -]?thought)\s*[:=]", re.IGNORECASE),
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# The gate is closed over its own machinery and every current app/scripts/tests
# change.  A fixed nine-file list is deliberately insufficient: runtime work
# can alter the agent service, configuration, or tests without touching it.
PHASE65_CORE_SCOPE = (
    "app/frontend/quality_report.html",
    "scripts/build_stage30_quality_report.py",
    "scripts/collect_stage30_engineering_health.py",
    "scripts/evaluate_phase65_agent_gate.py",
    "scripts/judge_phase65_agent_gate.py",
    "scripts/phase65_agent_gate.py",
    "scripts/phase65_gate_manifest.py",
    "scripts/score_stage30_quality.py",
    "scripts/verify_phase65_test_receipt.py",
    "tests/test_build_stage30_quality_report.py",
    "tests/test_evaluate_phase65_agent_gate.py",
    "tests/test_phase65_gate_manifest.py",
    "tests/test_phase65_test_receipt_bundle.py",
    "tests/test_stage30_engineering_health.py",
    "tests/test_stage30_scoring.py",
    "tests/test_verify_phase65_test_receipt.py",
)


@dataclass(frozen=True)
class GitWorktreeIdentity:
    base_commit: str
    dirty: bool
    tracked_patch_sha256: str
    scoped_content_sha256: str
    scoped_paths: tuple[str, ...]


@dataclass(frozen=True)
class AgentGateManifest:
    schema_version: str
    run_id: str
    variant: Variant
    status: RunStatus
    base_commit: str
    tracked_patch_sha256: str
    scoped_content_sha256: str
    scoped_paths: tuple[str, ...]
    evaluator_sha256: str
    case_set_sha256: str
    prompt_sha256: str
    tool_schema_sha256: str
    corpus_fingerprint: str
    index_fingerprint: str
    provider_models: tuple[str, ...]
    endpoint_identity_sha256: str
    judge_receipt_contract_sha256: str
    cache_policy: str
    environment_class: str
    expected_rows: int
    completed_rows: int
    started_at: str
    completed_at: str
    sanitized_errors: tuple[str, ...] = ()

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: Path | str) -> str:
    """Return the SHA-256 fingerprint of a file without decoding its contents."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_phase65_scope(root: Path | str) -> tuple[str, ...]:
    """Close Phase65 evidence over all current source/test files and ignore rules.

    This intentionally scans the filesystem instead of trusting
    ``git ls-files --exclude-standard``: an untracked source file remains part
    of the evidence even if a changed ignore rule hides it from Git.  Generated
    output and local agent state are excluded because they are outside the
    ``app/``, ``scripts/``, and ``tests/`` source boundaries.
    """
    repository = Path(root).resolve()
    relevant = set(PHASE65_CORE_SCOPE)
    for directory in ("app", "scripts", "tests"):
        source_root = repository / directory
        if not source_root.is_dir():
            continue
        for candidate in source_root.rglob("*"):
            if candidate.is_file() and "__pycache__" not in candidate.parts and candidate.suffix != ".pyc":
                relevant.add(candidate.relative_to(repository).as_posix())
    for ignore_file in (repository / ".gitignore", *repository.glob("app/**/.gitignore"), *repository.glob("scripts/**/.gitignore"), *repository.glob("tests/**/.gitignore")):
        if ignore_file.is_file():
            relevant.add(ignore_file.relative_to(repository).as_posix())
    return tuple(sorted(relevant))


def read_git_worktree_identity(
    root: Path | str, scoped_paths: Sequence[Path | str]
) -> GitWorktreeIdentity:
    """Fingerprint the tracked diff for repository-contained paths only."""
    repository = Path(root).resolve()
    normalized_paths = tuple(_normalize_scoped_path(repository, path) for path in scoped_paths)
    base_commit = _run_git(repository, "rev-parse", "HEAD").decode("ascii").strip()
    patch = _run_git(repository, "diff", "--binary", "--", *normalized_paths)
    content_digest = hashlib.sha256()
    for relative_path in normalized_paths:
        content_digest.update(relative_path.encode("utf-8"))
        content_digest.update(b"\0")
        candidate = repository / relative_path
        if not candidate.is_file():
            raise ValueError(f"scoped file missing: {relative_path}")
        content_digest.update(sha256_file(candidate).encode("ascii"))
        content_digest.update(b"\n")
    return GitWorktreeIdentity(
        base_commit=base_commit,
        dirty=bool(patch),
        tracked_patch_sha256=hashlib.sha256(patch).hexdigest(),
        scoped_content_sha256=content_digest.hexdigest(),
        scoped_paths=normalized_paths,
    )


def write_manifest(path: Path | str, manifest: AgentGateManifest) -> None:
    """Write a stable, UTF-8 JSON representation containing safe manifest fields."""
    safe_payload = manifest.to_safe_dict()
    _validate_safe_manifest_values(safe_payload)
    _validate_endpoint_identity_sha256(manifest.endpoint_identity_sha256)
    _validate_judge_receipt_contract_sha256(manifest.judge_receipt_contract_sha256)
    destination = Path(path)
    payload = json.dumps(
        safe_payload, ensure_ascii=False, indent=2, sort_keys=True
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False
    ) as stream:
        stream.write(f"{payload}\n")
        temporary = Path(stream.name)
    temporary.replace(destination)


def load_manifest(path: Path | str) -> AgentGateManifest:
    """Load a manifest after validating the gate's finite, safe value domains."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid manifest JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    return load_manifest_payload(payload)


def load_manifest_payload(payload: dict[str, object]) -> AgentGateManifest:
    """Strictly parse an in-memory safe manifest, including secret-content checks."""
    _validate_safe_manifest_values(payload)

    schema_version = _required_string(payload, "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"unknown manifest schema: {schema_version}")

    variant = _required_string(payload, "variant")
    if variant not in _VALID_VARIANTS:
        raise ValueError(f"unknown manifest variant: {variant}")
    status = _required_string(payload, "status")
    if status not in _VALID_STATUSES:
        raise ValueError(f"unknown manifest status: {status}")

    expected_rows = _required_nonnegative_int(payload, "expected_rows")
    completed_rows = _required_nonnegative_int(payload, "completed_rows")
    endpoint_identity_sha256 = _required_string(payload, "endpoint_identity_sha256")
    _validate_endpoint_identity_sha256(endpoint_identity_sha256)
    judge_receipt_contract_sha256 = _required_string(payload, "judge_receipt_contract_sha256")
    _validate_judge_receipt_contract_sha256(judge_receipt_contract_sha256)
    environment_class = _required_string(payload, "environment_class")
    if environment_class not in _VALID_ENVIRONMENT_CLASSES:
        raise ValueError("unknown manifest environment class")
    return AgentGateManifest(
        schema_version=schema_version,
        run_id=_required_string(payload, "run_id"),
        variant=variant,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        base_commit=_required_string(payload, "base_commit"),
        tracked_patch_sha256=_required_string(payload, "tracked_patch_sha256"),
        scoped_content_sha256=_required_string(payload, "scoped_content_sha256"),
        scoped_paths=_required_string_tuple(payload, "scoped_paths"),
        evaluator_sha256=_required_string(payload, "evaluator_sha256"),
        case_set_sha256=_required_string(payload, "case_set_sha256"),
        prompt_sha256=_required_string(payload, "prompt_sha256"),
        tool_schema_sha256=_required_string(payload, "tool_schema_sha256"),
        corpus_fingerprint=_required_string(payload, "corpus_fingerprint"),
        index_fingerprint=_required_string(payload, "index_fingerprint"),
        provider_models=_required_string_tuple(payload, "provider_models"),
        endpoint_identity_sha256=endpoint_identity_sha256,
        judge_receipt_contract_sha256=judge_receipt_contract_sha256,
        cache_policy=_required_string(payload, "cache_policy"),
        environment_class=environment_class,
        expected_rows=expected_rows,
        completed_rows=completed_rows,
        started_at=_required_string(payload, "started_at"),
        completed_at=_required_string(payload, "completed_at"),
        sanitized_errors=_required_string_tuple(payload, "sanitized_errors"),
    )


def _normalize_scoped_path(repository: Path, scoped_path: Path | str) -> str:
    candidate = Path(scoped_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (repository / candidate).resolve()
    try:
        return resolved.relative_to(repository).as_posix()
    except ValueError as exc:
        raise ValueError(f"scoped path outside repository: {scoped_path}") from exc


def _run_git(repository: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def _required_string(payload: dict[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise ValueError(f"manifest {field} must be a string")
    return value


def _required_nonnegative_int(payload: dict[str, object], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"manifest {field} must be a non-negative row count")
    return value


def _required_string_tuple(payload: dict[str, object], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"manifest {field} must be a list of strings")
    return tuple(value)


def _validate_safe_manifest_values(value: object) -> None:
    """Reject structured raw content and credentials before manifest persistence/use."""
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_safe_manifest_values(key)
            _validate_safe_manifest_values(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_safe_manifest_values(item)
        return
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in _UNSAFE_MANIFEST_PATTERNS):
            raise ValueError("unsafe manifest content is not permitted")


def _validate_endpoint_identity_sha256(value: str) -> None:
    if not _SHA256_PATTERN.fullmatch(value):
        raise ValueError("manifest endpoint identity must be a lowercase SHA-256 digest")


def _validate_judge_receipt_contract_sha256(value: str) -> None:
    if not _SHA256_PATTERN.fullmatch(value):
        raise ValueError("manifest judge receipt contract must be a lowercase SHA-256 digest")

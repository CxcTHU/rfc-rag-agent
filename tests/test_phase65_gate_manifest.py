import json
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.phase65_gate_manifest import (
    AgentGateManifest,
    GitWorktreeIdentity,
    canonical_phase65_scope,
    load_manifest,
    read_git_worktree_identity,
    sha256_file,
    write_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_phase65_scope_closes_changed_app_scripts_tests_and_core(tmp_path: Path) -> None:
    (tmp_path / "app" / "services" / "agent").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "app" / "services" / "agent" / "tool_calling_service.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "scripts" / "custom_gate.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "tests" / "test_new_runtime.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ignored.md").write_text("ignored\n", encoding="utf-8")

    scope = canonical_phase65_scope(tmp_path)

    assert "app/services/agent/tool_calling_service.py" in scope
    assert "scripts/custom_gate.py" in scope
    assert "tests/test_new_runtime.py" in scope
    assert "docs/ignored.md" not in scope
    assert "output/local.txt" not in scope
    assert "scripts/verify_phase65_test_receipt.py" in scope


def test_scope_hashes_root_ignore_file_even_when_new_app_python_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "untracked_runtime.py").write_text("VALUE = 1\n", encoding="utf-8")
    before = canonical_phase65_scope(tmp_path)
    (tmp_path / ".gitignore").write_text("app/untracked_runtime.py\n", encoding="utf-8")
    after = canonical_phase65_scope(tmp_path)

    assert "app/untracked_runtime.py" in before
    assert "app/untracked_runtime.py" in after
    assert ".gitignore" not in before
    assert ".gitignore" in after


def make_manifest(**changes: object) -> AgentGateManifest:
    manifest = AgentGateManifest(
        schema_version="phase65-agent-gate-v1",
        run_id="run-1",
        variant="baseline",
        status="complete",
        base_commit="a" * 40,
        tracked_patch_sha256="b" * 64,
        scoped_content_sha256="a" * 64,
        scoped_paths=("app/services/agent/tool_calling_service.py",),
        evaluator_sha256="c" * 64,
        case_set_sha256="d" * 64,
        prompt_sha256="e" * 64,
        tool_schema_sha256="f" * 64,
        corpus_fingerprint="corpus",
        index_fingerprint="index",
        provider_models=("zhipu/rerank", "deepseek/deepseek-v4-flash"),
        endpoint_identity_sha256="a" * 64,
        judge_receipt_contract_sha256="b" * 64,
        cache_policy="cold",
        environment_class="controlled_candidate",
        expected_rows=90,
        completed_rows=90,
        started_at="2026-07-14T00:00:00+00:00",
        completed_at="2026-07-14T01:00:00+00:00",
        sanitized_errors=(),
    )
    return replace(manifest, **changes)


def test_manifest_serialization_contains_fingerprints_not_secrets(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"

    write_manifest(path, make_manifest())

    payload = path.read_text(encoding="utf-8")
    assert '"completed_rows": 90' in payload
    assert "api_key" not in payload.casefold()
    assert "authorization" not in payload.casefold()


def test_manifest_round_trips_immutable_types(tmp_path: Path) -> None:
    manifest = make_manifest(sanitized_errors=("timed out",))
    path = tmp_path / "manifest.json"

    write_manifest(path, manifest)

    assert load_manifest(path) == manifest
    assert GitWorktreeIdentity.__dataclass_params__.frozen
    assert AgentGateManifest.__dataclass_params__.frozen


@pytest.mark.parametrize("endpoint_identity_sha256", ["", "a" * 63, "g" * 64])
def test_manifest_rejects_missing_or_non_sha256_endpoint_identity(
    tmp_path: Path, endpoint_identity_sha256: str
) -> None:
    path = tmp_path / "manifest.json"

    with pytest.raises(ValueError, match="endpoint"):
        write_manifest(path, make_manifest(endpoint_identity_sha256=endpoint_identity_sha256))

    assert not path.exists()


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "authorization=credential-value",
        'raw_response={"provider_payload": "body"}',
        "answer: full generated answer",
        "evidence: full retrieved evidence",
        "reasoning_content: private chain",
    ],
    ids=("authorization", "provider_payload", "answer", "evidence", "reasoning"),
)
def test_write_manifest_rejects_unsafe_values_without_persisting_json(
    tmp_path: Path, unsafe_value: str
) -> None:
    path = tmp_path / "manifest.json"

    with pytest.raises(ValueError, match="unsafe"):
        write_manifest(path, make_manifest(sanitized_errors=(unsafe_value,)))

    assert not path.exists()


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "authorization=credential-value",
        'raw_response={"provider_payload": "body"}',
        "answer: full generated answer",
        "evidence: full retrieved evidence",
        "reasoning_content: private chain",
    ],
    ids=("authorization", "provider_payload", "answer", "evidence", "reasoning"),
)
def test_load_manifest_rejects_unsafe_values(tmp_path: Path, unsafe_value: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(make_manifest(sanitized_errors=(unsafe_value,)).to_safe_dict()),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsafe"):
        load_manifest(path)


def test_sha256_file_hashes_exact_file_bytes(tmp_path: Path) -> None:
    path = tmp_path / "input.bin"
    path.write_bytes(b"phase65\x00manifest")

    assert sha256_file(path) == "621ad82c09887be34f0c344315f36e93b2c9857da3b5ef83c96b33ede5a6925f"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "unknown", "schema"),
        ("variant", "other", "variant"),
        ("status", "unknown", "status"),
        ("expected_rows", -1, "row"),
        ("completed_rows", -1, "row"),
    ],
)
def test_load_manifest_rejects_invalid_gate_values(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(make_manifest().to_safe_dict() | {field: value}), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_manifest(path)


@pytest.mark.parametrize("environment_class", ["test", "real_provider", "unknown"])
def test_load_manifest_rejects_uncontrolled_environment_class(
    tmp_path: Path, environment_class: str
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(make_manifest(environment_class=environment_class).to_safe_dict()),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="environment"):
        load_manifest(path)


def test_scoped_patch_fingerprint_is_deterministic() -> None:
    first = read_git_worktree_identity(ROOT, ["app/services/agent/runtime.py"])
    second = read_git_worktree_identity(ROOT, ["app/services/agent/runtime.py"])

    assert first == second
    assert first.scoped_paths == ("app/services/agent/runtime.py",)
    assert len(first.base_commit) == 40
    assert len(first.tracked_patch_sha256) == 64


def test_scoped_patch_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside repository"):
        read_git_worktree_identity(ROOT, [tmp_path / "secret.txt"])

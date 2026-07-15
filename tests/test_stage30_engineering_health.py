from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, ChunkEmbedding, Document
from app.db.session import create_sqlite_engine
from scripts.collect_stage30_engineering_health import collect_engineering_health
from scripts.phase65_gate_manifest import AgentGateManifest, canonical_phase65_scope
from scripts.score_stage30_quality import evaluate_evidence_status


def verified_test_receipt() -> dict[str, object]:
    return {"schema_version": "stage30-pytest-junit-v1", "tests": 1, "failures": 0, "errors": 0, "test_suite_sha256": "3" * 64, "receipt_sha256": "4" * 64}


def current_manifest(**changes: object) -> AgentGateManifest:
    values: dict[str, object] = {"schema_version": "phase65-agent-gate-v1", "run_id": "phase65-current", "variant": "candidate", "status": "complete", "base_commit": "base-commit", "tracked_patch_sha256": "a" * 64, "scoped_content_sha256": "b" * 64, "scoped_paths": canonical_phase65_scope(Path(__file__).resolve().parents[1]), "evaluator_sha256": "c" * 64, "case_set_sha256": "d" * 64, "prompt_sha256": "e" * 64, "tool_schema_sha256": "f" * 64, "corpus_fingerprint": "corpus-v1", "index_fingerprint": "index-v1", "provider_models": ("provider:model",), "endpoint_identity_sha256": "1" * 64, "judge_receipt_contract_sha256": "2" * 64, "cache_policy": "cold", "environment_class": "controlled_candidate", "expected_rows": 1, "completed_rows": 1, "started_at": "2026-07-14T00:00:00+00:00", "completed_at": "2026-07-14T00:00:01+00:00", "sanitized_errors": ()}
    values.update(changes)
    return AgentGateManifest(**values)  # type: ignore[arg-type]


def make_session(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'stage30-health.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_index(db) -> None:
    document = Document(title="Stage 30 health source", source_type="web_page", source_path="https://example.com", file_name="health.md", file_extension=".md", content_hash="stage30-health-document", raw_path="data/raw/health.md")
    chunk = Chunk(document=document, chunk_index=0, content="health content", char_count=14)
    db.add(document)
    db.flush()
    db.add_all([ChunkEmbedding(chunk=chunk, provider="jina", model_name="jina-embeddings-v3", dimension=1024, embedding_json="[0.1]", content_hash="stage30-health-chunk"), ChunkEmbedding(chunk=chunk, provider="deterministic", model_name="hash-token-v1", dimension=64, embedding_json="[0.2]", content_hash="stage30-health-chunk")])
    db.commit()


def test_collect_stage30_engineering_health_is_read_only_summary(tmp_path) -> None:
    SessionLocal = make_session(tmp_path)
    with SessionLocal() as db:
        seed_index(db)
        health = collect_engineering_health(db, full_tests_status="1 passed", quality_report_smoke="passed", manifest=current_manifest(), test_suite_sha256="3" * 64, test_receipt=verified_test_receipt())
    assert health["chunk_count"] == 1
    assert health["embedding_count"] == 2
    assert health["jina_embedding_count"] == 1
    assert health["deterministic_embedding_count"] == 1
    assert health["orphan_embeddings"] == 0
    assert health["duplicate_provider_model_groups"] == 0
    assert health["schema_version"] == "stage30-engineering-health-v2"
    assert health["manifest_run_id"] == "phase65-current"
    assert health["test_suite_sha256"] == "3" * 64
    assert health["collector_limits"] == {"runs_pytest": False, "rebuilds_embeddings": False, "writes_database": False, "calls_real_api": False}


def test_old_engineering_health_cannot_render_current_pass() -> None:
    health = {"schema_version": "stage30-engineering-health-v1", "generated_at": "2026-06-13T00:00:00+00:00", "full_tests_status": "571 passed", "pytest_receipt_schema_version": "stage30-pytest-junit-v1", "pytest_receipt_tests": 1, "pytest_receipt_failures": 0, "pytest_receipt_errors": 0, "pytest_receipt_test_suite_sha256": "3" * 64, "pytest_receipt_receipt_sha256": "4" * 64}
    status = evaluate_evidence_status(health=health, manifest=current_manifest(), test_suite_sha256="3" * 64, test_receipt=verified_test_receipt(), current_worktree_identity=None)
    assert status.status == "stale"
    assert "test_fingerprint_mismatch" in status.reasons

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models import Chunk, ChunkEmbedding  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from scripts.phase65_gate_manifest import AgentGateManifest, load_manifest  # noqa: E402
from scripts.score_stage30_quality import load_verified_test_receipt  # noqa: E402
from scripts.verify_phase65_test_receipt import load_bundle_test_receipt  # noqa: E402

DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "stage30_engineering_health.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect stage 30 engineering health as a read-only artifact. "
            "This script does not run pytest, rebuild embeddings, write the database, "
            "or call real APIs."
        )
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--full-tests-status",
        default="not_run_for_current_stage",
        help="External test status string, for example '556 passed, 1 warning'.",
    )
    parser.add_argument(
        "--quality-report-smoke",
        default="not_run_for_current_stage",
        help="External smoke status for /quality-report, for example 'passed'.",
    )
    parser.add_argument(
        "--agent-gate-manifest",
        required=True,
        help="Complete safe Phase 65 AgentGateManifest JSON for this evidence run.",
    )
    parser.add_argument("--pytest-receipt-bundle", required=True)
    return parser.parse_args()


def scalar_count(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


def collect_embedding_provider_count(db: Session, provider: str) -> int:
    return scalar_count(
        db,
        select(func.count(ChunkEmbedding.id)).where(ChunkEmbedding.provider == provider),
    )


def collect_orphan_embedding_count(db: Session) -> int:
    return scalar_count(
        db,
        select(func.count(ChunkEmbedding.id))
        .outerjoin(Chunk, ChunkEmbedding.chunk_id == Chunk.id)
        .where(Chunk.id.is_(None)),
    )


def collect_duplicate_provider_model_groups(db: Session) -> int:
    duplicate_groups = (
        select(
            ChunkEmbedding.chunk_id,
            ChunkEmbedding.provider,
            ChunkEmbedding.model_name,
            func.count(ChunkEmbedding.id).label("embedding_count"),
        )
        .group_by(
            ChunkEmbedding.chunk_id,
            ChunkEmbedding.provider,
            ChunkEmbedding.model_name,
        )
        .having(func.count(ChunkEmbedding.id) > 1)
        .subquery()
    )
    return scalar_count(db, select(func.count()).select_from(duplicate_groups))


def collect_provider_distribution(db: Session) -> list[dict[str, int | str]]:
    rows = db.execute(
        select(
            ChunkEmbedding.provider,
            ChunkEmbedding.model_name,
            ChunkEmbedding.dimension,
            func.count(ChunkEmbedding.id),
        )
        .group_by(
            ChunkEmbedding.provider,
            ChunkEmbedding.model_name,
            ChunkEmbedding.dimension,
        )
        .order_by(
            ChunkEmbedding.provider,
            ChunkEmbedding.model_name,
            ChunkEmbedding.dimension,
        )
    ).all()
    return [
        {
            "provider": str(provider),
            "model_name": str(model_name),
            "dimension": int(dimension),
            "count": int(count),
        }
        for provider, model_name, dimension, count in rows
    ]


def collect_engineering_health(
    db: Session,
    *,
    full_tests_status: str,
    quality_report_smoke: str,
    manifest: AgentGateManifest,
    test_suite_sha256: str,
    test_receipt: dict[str, object],
) -> dict[str, object]:
    chunk_count = scalar_count(db, select(func.count(Chunk.id)))
    embedding_count = scalar_count(db, select(func.count(ChunkEmbedding.id)))
    jina_embedding_count = collect_embedding_provider_count(db, "jina")
    deterministic_embedding_count = collect_embedding_provider_count(db, "deterministic")

    return {
        "schema_version": "stage30-engineering-health-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_run_id": manifest.run_id,
        "base_commit": manifest.base_commit,
        "tracked_patch_sha256": manifest.tracked_patch_sha256,
        "test_suite_sha256": test_suite_sha256,
        "pytest_receipt_schema_version": test_receipt["schema_version"],
        "pytest_receipt_tests": test_receipt["tests"],
        "pytest_receipt_failures": test_receipt["failures"],
        "pytest_receipt_errors": test_receipt["errors"],
        "pytest_receipt_test_suite_sha256": test_receipt["test_suite_sha256"],
        "pytest_receipt_receipt_sha256": test_receipt["receipt_sha256"],
        "trust_level": test_receipt.get("trust_level", "unknown"),
        "full_tests_status": full_tests_status,
        "chunk_count": chunk_count,
        "embedding_count": embedding_count,
        "jina_embedding_count": jina_embedding_count,
        "deterministic_embedding_count": deterministic_embedding_count,
        "orphan_embeddings": collect_orphan_embedding_count(db),
        "duplicate_provider_model_groups": collect_duplicate_provider_model_groups(db),
        "quality_report_smoke": quality_report_smoke,
        "provider_distribution": collect_provider_distribution(db),
        "collector_limits": {
            "runs_pytest": False,
            "rebuilds_embeddings": False,
            "writes_database": False,
            "calls_real_api": False,
        },
    }


def write_health(path: Path, health: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    manifest = load_manifest(Path(args.agent_gate_manifest))
    test_receipt = load_bundle_test_receipt(Path(args.pytest_receipt_bundle))
    with SessionLocal() as db:
        health = collect_engineering_health(
            db,
            full_tests_status=args.full_tests_status,
            quality_report_smoke=args.quality_report_smoke,
            manifest=manifest,
            test_suite_sha256=str(test_receipt["test_suite_sha256"]),
            test_receipt=test_receipt,
        )
    write_health(Path(args.output), health)
    print(f"stage30 engineering health written: {args.output}")


if __name__ == "__main__":
    main()

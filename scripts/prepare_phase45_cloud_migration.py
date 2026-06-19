"""Prepare Phase 45 SQLite to PostgreSQL migration readiness checks.

This is a local readiness report only. It does not connect to cloud
PostgreSQL, copy files, rebuild cloud FAISS, or migrate users/conversations.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "app.sqlite"
DEFAULT_AUDIT_PATH = ROOT / "data" / "incoming" / "phase45_literature" / "phase12_quality_audit.csv"
DEFAULT_OUTPUT = ROOT / "data" / "incoming" / "phase45_literature" / "phase16_migration_readiness.json"


@dataclass(frozen=True)
class Phase45MigrationReadiness:
    database_path: str
    documents: int
    sources: int
    chunks: int
    chunk_embeddings: int
    qa_logs: int
    users_excluded: int
    conversations_excluded: int
    messages_excluded: int
    documents_missing_content_hash: int
    duplicate_content_hash_groups: int
    paratera_glm_embedding_rows: int
    paratera_glm_bad_dimension_rows: int
    image_description_chunks: int
    image_description_embeddings: int
    phase45_cloud_candidates: int
    phase45_review_required: int
    migration_tables: str
    excluded_tables: str
    ready_for_authorized_migration: bool
    blocker_summary: str


def scalar(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    value = connection.execute(sql, params).fetchone()[0]
    return int(value or 0)


def count_audit_statuses(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return (
        sum(1 for row in rows if row.get("review_status") == "cloud_candidate"),
        sum(1 for row in rows if row.get("review_status") == "review_required"),
    )


def build_readiness(db_path: Path, audit_path: Path) -> Phase45MigrationReadiness:
    cloud_candidates, review_required = count_audit_statuses(audit_path)
    with sqlite3.connect(db_path) as connection:
        image_description_chunks = scalar(
            connection,
            "select count(1) from chunks where chunk_type = ?",
            ("image_description",),
        )
        image_description_embeddings = scalar(
            connection,
            """
            select count(1)
            from chunk_embeddings e
            join chunks c on c.id = e.chunk_id
            where c.chunk_type = ? and e.provider = ? and e.model_name = ? and e.dimension = ?
            """,
            ("image_description", "paratera", "GLM-Embedding-3", 2048),
        )
        bad_dimension_rows = scalar(
            connection,
            """
            select count(1)
            from chunk_embeddings
            where provider = ? and model_name = ? and dimension != ?
            """,
            ("paratera", "GLM-Embedding-3", 2048),
        )
        readiness = Phase45MigrationReadiness(
            database_path=str(db_path),
            documents=scalar(connection, "select count(1) from documents"),
            sources=scalar(connection, "select count(1) from sources"),
            chunks=scalar(connection, "select count(1) from chunks"),
            chunk_embeddings=scalar(connection, "select count(1) from chunk_embeddings"),
            qa_logs=scalar(connection, "select count(1) from qa_logs"),
            users_excluded=scalar(connection, "select count(1) from users"),
            conversations_excluded=scalar(connection, "select count(1) from conversations"),
            messages_excluded=scalar(connection, "select count(1) from messages"),
            documents_missing_content_hash=scalar(
                connection,
                "select count(1) from documents where content_hash is null or content_hash = ''",
            ),
            duplicate_content_hash_groups=scalar(
                connection,
                """
                select count(1) from (
                    select content_hash from documents group by content_hash having count(1) > 1
                )
                """,
            ),
            paratera_glm_embedding_rows=scalar(
                connection,
                "select count(1) from chunk_embeddings where provider = ? and model_name = ? and dimension = ?",
                ("paratera", "GLM-Embedding-3", 2048),
            ),
            paratera_glm_bad_dimension_rows=bad_dimension_rows,
            image_description_chunks=image_description_chunks,
            image_description_embeddings=image_description_embeddings,
            phase45_cloud_candidates=cloud_candidates,
            phase45_review_required=review_required,
            migration_tables="documents,sources,chunks,chunk_embeddings,qa_logs",
            excluded_tables="users,conversations,messages",
            ready_for_authorized_migration=False,
            blocker_summary="Await user human verification and explicit cloud PostgreSQL authorization before executing migration.",
        )
    return readiness


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Phase 45 cloud migration readiness report.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    readiness = build_readiness(Path(args.db_path), Path(args.audit))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(readiness), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(asdict(readiness), ensure_ascii=False, indent=2))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()

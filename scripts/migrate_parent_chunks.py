from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import engine, init_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Add chunks.parent_chunk_id for stage 31 parent-child retrieval.")
    parser.add_argument("--dry-run", action="store_true", help="Check migration status without altering the database.")
    args = parser.parse_args()

    init_db()
    result = migrate_parent_chunk_id(target_engine=engine, dry_run=args.dry_run)
    print(result)


def migrate_parent_chunk_id(target_engine=engine, dry_run: bool = False) -> str:
    inspector = inspect(target_engine)
    columns = {column["name"] for column in inspector.get_columns("chunks")}
    if "parent_chunk_id" in columns:
        return "chunks.parent_chunk_id already exists"
    if dry_run:
        return "chunks.parent_chunk_id missing; dry-run only"

    with target_engine.begin() as connection:
        connection.execute(text("ALTER TABLE chunks ADD COLUMN parent_chunk_id INTEGER NULL"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_parent_chunk_id ON chunks (parent_chunk_id)"))
    return "chunks.parent_chunk_id added"


if __name__ == "__main__":
    main()

"""Collect read-only Phase 46 database consistency stats."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/app.sqlite")
DEFAULT_OUTPUT = Path("data/evaluation/phase46_db_stats.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Phase 46 DB consistency stats.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stats = collect_stats(Path(args.db_path))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("summary:", " ".join(f"{key}={value}" for key, value in stats.items()))
    print(f"wrote {output}")


def collect_stats(db_path: Path) -> dict[str, int]:
    with sqlite3.connect(db_path) as connection:
        return {
            "documents": scalar(connection, "select count(1) from documents"),
            "chunks": scalar(connection, "select count(1) from chunks"),
            "chunk_embeddings": scalar(connection, "select count(1) from chunk_embeddings"),
            "image_chunks": scalar(connection, "select count(1) from chunks where chunk_type = 'image_description'"),
            "image_embeddings": scalar(
                connection,
                """
                select count(1)
                from chunk_embeddings e
                join chunks c on c.id = e.chunk_id
                where c.chunk_type = 'image_description'
                """,
            ),
            "render_image_chunks": scalar(
                connection,
                """
                select count(1)
                from chunks
                where chunk_type = 'image_description'
                  and source_image_path like '%render%'
                """,
            ),
            "render_image_embeddings": scalar(
                connection,
                """
                select count(1)
                from chunk_embeddings e
                join chunks c on c.id = e.chunk_id
                where c.chunk_type = 'image_description'
                  and c.source_image_path like '%render%'
                """,
            ),
            "captioned_image_chunks": scalar(
                connection,
                """
                select count(1)
                from chunks
                where chunk_type = 'image_description'
                  and caption is not null
                  and caption != ''
                """,
            ),
            "orphan_embeddings": scalar(
                connection,
                """
                select count(1)
                from chunk_embeddings e
                left join chunks c on c.id = e.chunk_id
                where c.id is null
                """,
            ),
        }


def scalar(connection: sqlite3.Connection, query: str) -> int:
    return int(connection.execute(query).fetchone()[0] or 0)


if __name__ == "__main__":
    main()

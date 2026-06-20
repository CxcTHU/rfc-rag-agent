import sqlite3
from pathlib import Path

from scripts.collect_phase46_db_stats import collect_stats


def test_collect_stats_counts_render_images_and_orphans(tmp_path: Path) -> None:
    db_path = tmp_path / "stats.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("create table documents (id integer primary key)")
        connection.execute(
            """
            create table chunks (
                id integer primary key,
                chunk_type text,
                source_image_path text
                , caption text
            )
            """
        )
        connection.execute("create table chunk_embeddings (id integer primary key, chunk_id integer)")
        connection.execute("insert into documents (id) values (1)")
        connection.execute(
            "insert into chunks (id, chunk_type, source_image_path, caption) values (1, 'image_description', 'data/images/1/page1_render1.png', 'Fig. 1')"
        )
        connection.execute(
            "insert into chunks (id, chunk_type, source_image_path) values (2, 'text', '')"
        )
        connection.execute("insert into chunk_embeddings (id, chunk_id) values (1, 1)")
        connection.execute("insert into chunk_embeddings (id, chunk_id) values (2, 999)")

    stats = collect_stats(db_path)

    assert stats["documents"] == 1
    assert stats["chunks"] == 2
    assert stats["chunk_embeddings"] == 2
    assert stats["image_chunks"] == 1
    assert stats["image_embeddings"] == 1
    assert stats["render_image_chunks"] == 1
    assert stats["render_image_embeddings"] == 1
    assert stats["captioned_image_chunks"] == 1
    assert stats["orphan_embeddings"] == 1

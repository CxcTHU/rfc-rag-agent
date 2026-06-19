import sqlite3
from pathlib import Path

from scripts.clean_phase45_low_value_images import (
    apply_removals,
    classify_image_chunk,
    review_image_chunks,
    summarize,
)


def test_classifies_qr_logo_short_and_orientation_cases() -> None:
    assert classify_image_chunk("这是一张二维码图片，由黑白相间方块组成。", 31)[0] == "remove"
    assert classify_image_chunk("图片展示Elsevier的标志和 NON SOLUS 字样。", 80)[0] == "remove"
    assert classify_image_chunk("确定性视觉描述：该图片来自 PDF 图表或示意图。", 60)[0] == "remove"
    assert classify_image_chunk("图片展示一个灰色曲面物体，上面有两支笔。", 24)[0] == "remove"
    decision, reason = classify_image_chunk("这是一张倒置的会议照片，但包含工程咨询会横幅。", 80)
    assert decision == "review"
    assert "orientation_review" in reason
    assert classify_image_chunk("这是一张堆石混凝土坝体结构剖面图，包含坝顶高程和排水廊道。", 80)[0] == "keep"


def test_review_and_apply_removes_low_value_image_chunks(tmp_path: Path) -> None:
    db_path = tmp_path / "images.sqlite"
    with sqlite3.connect(db_path) as connection:
        create_schema(connection)
        connection.execute(
            "insert into chunks (id, document_id, chunk_index, content, char_count, chunk_type, source_image_path) "
            "values (1, 10, 0, '这是一张二维码图片，由黑白相间方块组成。', 31, 'image_description', 'data/images/10/qr.png')"
        )
        connection.execute(
            "insert into chunks (id, document_id, chunk_index, content, char_count, chunk_type, source_image_path) "
            "values (2, 10, 1, '这是一张堆石混凝土坝体结构剖面图，包含坝顶高程和排水廊道。', 80, 'image_description', 'data/images/10/fig.png')"
        )
        connection.execute(
            "insert into chunk_embeddings (id, chunk_id, provider, model_name, dimension, embedding_json, content_hash) "
            "values (1, 1, 'deterministic', 'hash-token-v1', 64, '[0.1]', 'hash1')"
        )
        rows = review_image_chunks(connection)
        deleted_chunks, deleted_embeddings = apply_removals(connection, rows)
        remaining_chunks = connection.execute("select count(1) from chunks").fetchone()[0]
        remaining_embeddings = connection.execute("select count(1) from chunk_embeddings").fetchone()[0]
    summary = summarize(rows, deleted_chunks, deleted_embeddings)

    assert summary.remove_candidates == 1
    assert summary.kept_chunks == 1
    assert deleted_chunks == 1
    assert deleted_embeddings == 1
    assert remaining_chunks == 1
    assert remaining_embeddings == 0


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        create table chunks (
            id integer primary key,
            document_id integer,
            chunk_index integer,
            content text,
            char_count integer,
            chunk_type text,
            source_image_path text
        )
        """
    )
    connection.execute(
        """
        create table chunk_embeddings (
            id integer primary key,
            chunk_id integer,
            provider text,
            model_name text,
            dimension integer,
            embedding_json text,
            content_hash text
        )
        """
    )

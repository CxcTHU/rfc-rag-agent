import sqlite3

from scripts.backfill_phase46_image_page_numbers import backfill_page_numbers


def test_backfill_page_numbers_updates_only_image_chunks() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        create table chunks (
            id integer primary key,
            chunk_type text,
            source_image_path text,
            page_number integer
        );
        insert into chunks (id, chunk_type, source_image_path, page_number)
        values (1, 'image_description', 'data/images/1/page12_img3.png', null);
        insert into chunks (id, chunk_type, source_image_path, page_number)
        values (2, 'image_description', 'data/images/1/page8_render1.png', 8);
        insert into chunks (id, chunk_type, source_image_path, page_number)
        values (3, 'text', null, null);
        insert into chunks (id, chunk_type, source_image_path, page_number)
        values (4, 'image_description', 'data/images/1/not_a_page.png', null);
        """
    )

    dry_run = backfill_page_numbers(connection, apply=False)
    assert dry_run.total_image_chunks == 3
    assert dry_run.parsed_page_numbers == 2
    assert dry_run.already_had_page_number == 1
    assert dry_run.updated_rows == 0
    assert dry_run.failed_to_parse == 1
    assert connection.execute("select page_number from chunks where id = 1").fetchone()[0] is None

    applied = backfill_page_numbers(connection, apply=True)

    assert applied.updated_rows == 1
    assert connection.execute("select page_number from chunks where id = 1").fetchone()[0] == 12
    assert connection.execute("select page_number from chunks where id = 2").fetchone()[0] == 8

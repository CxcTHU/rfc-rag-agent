from sqlalchemy import inspect, text

from app.db.session import create_sqlite_engine
from scripts.migrate_parent_chunks import migrate_parent_chunk_id


def test_migrate_parent_chunk_id_adds_nullable_column(tmp_path) -> None:
    database_path = tmp_path / "migration.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE chunks (id INTEGER PRIMARY KEY, content TEXT NOT NULL)"))

    result = migrate_parent_chunk_id(target_engine=engine)

    columns = {column["name"] for column in inspect(engine).get_columns("chunks")}
    assert result == "chunks.parent_chunk_id added"
    assert "parent_chunk_id" in columns


def test_migrate_parent_chunk_id_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "migration_idempotent.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE chunks (id INTEGER PRIMARY KEY, parent_chunk_id INTEGER NULL)")
        )

    result = migrate_parent_chunk_id(target_engine=engine)

    assert result == "chunks.parent_chunk_id already exists"


def test_migrate_parent_chunk_id_supports_dry_run(tmp_path) -> None:
    database_path = tmp_path / "migration_dry_run.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE chunks (id INTEGER PRIMARY KEY, content TEXT NOT NULL)"))

    result = migrate_parent_chunk_id(target_engine=engine, dry_run=True)

    columns = {column["name"] for column in inspect(engine).get_columns("chunks")}
    assert result == "chunks.parent_chunk_id missing; dry-run only"
    assert "parent_chunk_id" not in columns

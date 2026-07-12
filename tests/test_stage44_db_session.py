from sqlalchemy import inspect, text
from sqlalchemy.pool import QueuePool, SingletonThreadPool

from app.db.session import (
    create_database_engine,
    create_sqlite_engine,
    ensure_sqlite_compat_columns,
)


def test_stage44_create_database_engine_uses_sqlite_connect_args(tmp_path) -> None:
    database_path = tmp_path / "nested" / "stage44.sqlite"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")

    assert database_path.parent.exists()
    assert engine.url.get_backend_name() == "sqlite"


def test_stage44_create_sqlite_engine_keeps_existing_helper(tmp_path) -> None:
    database_path = tmp_path / "stage44-helper.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")

    assert engine.url.get_backend_name() == "sqlite"
    assert isinstance(engine.pool, (QueuePool, SingletonThreadPool))


def test_stage44_create_database_engine_supports_postgresql_without_connecting() -> None:
    engine = create_database_engine(
        "postgresql+psycopg2://rfc_user:rfc_pass@example.invalid:5432/rfc_rag"
    )

    assert engine.url.get_backend_name() == "postgresql"
    assert engine.pool._pre_ping is True


def test_stage44_create_database_engine_rejects_unknown_backend() -> None:
    try:
        create_database_engine("mysql+pymysql://user:pass@example.invalid/db")
    except ValueError as exc:
        assert "Unsupported DATABASE_URL backend" in str(exc)
    else:
        raise AssertionError("unsupported backend should fail fast")


def test_stage44_sqlite_compat_adds_missing_embedding_vector(tmp_path) -> None:
    database_path = tmp_path / "legacy-vector.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE chunk_embeddings ("
                "id INTEGER PRIMARY KEY, "
                "embedding_json TEXT NOT NULL"
                ")"
            )
        )

    ensure_sqlite_compat_columns(engine)

    columns = {
        column["name"] for column in inspect(engine).get_columns("chunk_embeddings")
    }
    assert "embedding_vector" in columns


def test_stage44_alembic_initial_migration_declares_existing_and_user_tables() -> None:
    migration = (
        "alembic/versions/20260617_0001_initial_schema.py"
    )
    with open(migration, encoding="utf-8") as handle:
        content = handle.read()

    for table_name in [
        "documents",
        "sources",
        "chunks",
        "chunk_embeddings",
        "users",
        "conversations",
        "messages",
        "qa_logs",
    ]:
        assert f'"{table_name}"' in content
    assert '"user_id"' in content
    assert "ForeignKeyConstraint" in content

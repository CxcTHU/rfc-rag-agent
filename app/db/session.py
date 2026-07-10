from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def ensure_sqlite_parent_dir(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return

    database_path = url.database
    if not database_path or database_path == ":memory:":
        return

    Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def create_sqlite_engine(database_url: str) -> Engine:
    ensure_sqlite_parent_dir(database_url)
    return create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )


def create_database_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    backend_name = url.get_backend_name()
    if backend_name == "sqlite":
        return create_sqlite_engine(database_url)
    if backend_name in {"postgresql", "postgres"}:
        return create_engine(database_url, pool_pre_ping=True)
    raise ValueError(f"Unsupported DATABASE_URL backend: {backend_name}")


engine = create_database_engine(get_settings().database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine: Engine = engine) -> None:
    from app.db.models import Base

    Base.metadata.create_all(bind=target_engine)
    ensure_sqlite_compat_columns(target_engine)


def ensure_sqlite_compat_columns(target_engine: Engine) -> None:
    """Apply narrow SQLite-only compatibility fixes for local dev databases.

    Production migrations run through Alembic/PostgreSQL. Local SQLite files from
    older phases may predate small hardening columns, and `create_all()` does not
    alter existing tables. Keep this deliberately narrow so startup can repair
    developer databases without becoming a second migration framework.
    """
    if target_engine.dialect.name != "sqlite":
        return
    inspector = inspect(target_engine)
    if "users" not in inspector.get_table_names():
        return
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" in user_columns:
        return
    with target_engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
        first_user_id = connection.execute(
            text("SELECT id FROM users ORDER BY id ASC LIMIT 1")
        ).scalar()
        if first_user_id is not None:
            connection.execute(
                text("UPDATE users SET role='admin' WHERE id=:user_id"),
                {"user_id": first_user_id},
            )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

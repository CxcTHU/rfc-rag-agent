from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
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


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

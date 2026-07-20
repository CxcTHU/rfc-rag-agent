from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.session import create_sqlite_engine, get_db
from app.main import app


@contextmanager
def make_test_client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "feedback_api.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_feedback_api_creates_feedback_and_reports_stats(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        create_response = client.post(
            "/feedback",
            json={
                "question": "What affects RFC compactness?",
                "answer": "Compaction quality and mix ratio affect compactness.",
                "rating": "positive",
            },
        )
        stats_response = client.get("/feedback/stats")

    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["id"] > 0
    assert payload["rating"] == "positive"
    assert payload["reason"] is None

    assert stats_response.status_code == 200
    stats_payload = stats_response.json()
    assert stats_payload["total"] == 1
    assert stats_payload["positive"] == 1
    assert stats_payload["negative"] == 0
    assert stats_payload["positive_rate"] == 1.0
    assert stats_payload["exportable_count"] == 1


def test_feedback_api_rejects_negative_feedback_without_reason(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/feedback",
            json={
                "question": "Question",
                "answer": "Answer",
                "rating": "negative",
            },
        )

    assert response.status_code == 422

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.session import create_sqlite_engine, get_db
from app.main import app
from app.services.agent.react_actions import parse_react_action_json


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


def test_phase47_react_action_reservations_parse() -> None:
    table_action = parse_react_action_json(
        {
            "action": "search_tables",
            "query": "28 day compressive strength table",
            "reasoning_summary": "The user asks for tabular strength data.",
        }
    )
    image_action = parse_react_action_json(
        {
            "action": "analyze_user_image",
            "image_path": "data/user_uploads/2026-06-20/example.png",
            "question": "Is this crack severe?",
            "reasoning_summary": "The user uploaded an image.",
        }
    )

    assert table_action.action == "search_tables"
    assert image_action.action == "analyze_user_image"
    assert image_action.safe_input_summary() == "question=Is this crack severe?"

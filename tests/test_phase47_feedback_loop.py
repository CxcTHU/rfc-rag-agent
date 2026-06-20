from __future__ import annotations

import csv

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.feedback_export import router as feedback_export_router
from app.db.models import Base
from app.db.session import create_sqlite_engine, get_db
from app.services.feedback.exporter import (
    build_export_rows,
    contains_sensitive_material,
    export_feedback_to_eval,
)
from app.services.feedback.feedback_service import FeedbackService
from app.services.feedback.keyword_extractor import extract_keywords


def make_session(tmp_path):
    database_path = tmp_path / "phase47_feedback.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_feedback_service_validates_and_reports_stats(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        service = FeedbackService(db)
        service.submit_feedback(
            question="What affects RFC strength?",
            answer="Compressive strength depends on mix ratio and compaction quality.",
            rating="positive",
        )
        service.submit_feedback(
            question="Where is the citation?",
            answer="This answer did not cite evidence.",
            rating="negative",
            reason="no_citation",
        )
        stats = service.get_feedback_stats()

    assert stats.total == 2
    assert stats.positive == 1
    assert stats.negative == 1
    assert stats.top_negative_reasons == [("no_citation", 1)]


def test_feedback_service_rejects_invalid_reason(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        try:
            FeedbackService(db).submit_feedback(
                question="Q",
                answer="A",
                rating="negative",
                reason=None,
            )
        except ValueError as exc:
            assert "valid reason" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("invalid negative feedback was accepted")


def test_keyword_extractor_prioritizes_domain_terms() -> None:
    keywords = extract_keywords(
        "Rock-filled concrete compressive strength depends on mix ratio and durability controls.",
        top_k=4,
    )

    assert "rock-filled concrete" in keywords
    assert "compressive strength" in keywords


def test_export_feedback_to_eval_filters_sensitive_and_duplicates(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    output_path = tmp_path / "feedback_eval.csv"
    with TestingSessionLocal() as db:
        service = FeedbackService(db)
        service.submit_feedback(
            question="How does mix ratio affect strength?",
            answer="Mix ratio and water-cement ratio influence compressive strength and durability in RFC.",
            rating="positive",
        )
        service.submit_feedback(
            question="How does mix ratio affect strength?",
            answer="Duplicate positive answer that should be skipped even though it is long enough.",
            rating="positive",
        )
        service.submit_feedback(
            question="Should this be exported?",
            answer="This answer leaks bearer sk-12345678901234567890 and should not export.",
            rating="positive",
        )

        result = export_feedback_to_eval(db, output_path=output_path, min_length=10)

    assert result.exported == 1
    assert result.skipped_duplicate == 1
    assert result.skipped_sensitive == 1
    with output_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["source"] == "user_feedback"


def test_export_helpers_detect_sensitive_material(tmp_path) -> None:
    assert contains_sensitive_material("Authorization: Bearer abcdefghijklmnop")
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        feedback = FeedbackService(db).submit_feedback(
            question="Show table evidence",
            answer="The table evidence includes mix ratio, strength, and durability keywords.",
            rating="positive",
        )
        rows, skipped_sensitive, skipped_duplicate = build_export_rows([feedback])

    assert rows[0]["category"] == "table_evidence"
    assert skipped_sensitive == 0
    assert skipped_duplicate == 0


def test_feedback_export_api_dry_run(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    app = FastAPI()
    app.include_router(feedback_export_router)

    def override_db():
        with TestingSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestingSessionLocal() as db:
        FeedbackService(db).submit_feedback(
            question="How does crack width matter?",
            answer="Crack width, continuity, leakage, and structural context guide inspection priority.",
            rating="positive",
        )
    with TestClient(app) as client:
        response = client.get("/feedback/export?dry_run=true&min_length=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["exported"] == 1

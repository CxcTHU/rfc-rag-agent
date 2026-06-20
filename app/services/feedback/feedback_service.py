from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.feedback_repository import FeedbackCreate, FeedbackRepository
from app.db.models import QAFeedback


VALID_NEGATIVE_REASONS = {
    "irrelevant",
    "inaccurate",
    "incomplete",
    "no_citation",
    "wrong_citation",
    "other",
}


@dataclass(frozen=True)
class FeedbackStats:
    total: int
    positive: int
    negative: int
    positive_rate: float
    top_negative_reasons: list[tuple[str, int]]
    recent_7d_total: int
    recent_7d_positive_rate: float
    exportable_count: int


class FeedbackService:
    def __init__(self, db: Session, repository: FeedbackRepository | None = None) -> None:
        self.db = db
        self.repo = repository or FeedbackRepository(db)

    def submit_feedback(
        self,
        *,
        question: str,
        answer: str,
        rating: str,
        reason: str | None = None,
        comment: str | None = None,
        conversation_id: int | None = None,
        message_id: int | None = None,
        question_answer_log_id: int | None = None,
    ) -> QAFeedback:
        clean_question = clean_required_text(question, "question")
        clean_answer = clean_required_text(answer, "answer")
        clean_rating = rating.strip().lower()
        clean_reason = reason.strip().lower() if reason else None
        clean_comment = clean_optional_text(comment)
        if clean_rating not in {"positive", "negative"}:
            raise ValueError("rating must be positive or negative")
        if clean_rating == "negative" and clean_reason not in VALID_NEGATIVE_REASONS:
            raise ValueError("negative feedback requires a valid reason")
        if clean_rating == "positive" and clean_reason is not None:
            raise ValueError("positive feedback must not include reason")
        return self.repo.create_feedback(
            FeedbackCreate(
                question_answer_log_id=question_answer_log_id,
                conversation_id=conversation_id,
                message_id=message_id,
                question=clean_question,
                answer=clean_answer,
                rating=clean_rating,
                reason=clean_reason,
                comment=clean_comment,
            )
        )

    def get_positive_feedback_for_export(
        self,
        *,
        min_answer_length: int = 50,
        since_days: int | None = None,
    ) -> list[QAFeedback]:
        statement = (
            select(QAFeedback)
            .where(QAFeedback.rating == "positive")
            .where(func.length(QAFeedback.answer) >= max(min_answer_length, 0))
            .order_by(QAFeedback.created_at.desc(), QAFeedback.id.desc())
        )
        if since_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=max(since_days, 0))
            statement = statement.where(QAFeedback.created_at >= cutoff)
        return list(self.db.scalars(statement).all())

    def get_feedback_stats(self) -> FeedbackStats:
        total = self.repo.count_feedback()
        positive = self.repo.count_feedback("positive")
        negative = self.repo.count_feedback("negative")
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent_total = self.count_since(recent_cutoff)
        recent_positive = self.count_since(recent_cutoff, rating="positive")
        reason_rows = self.db.execute(
            select(QAFeedback.reason, func.count(QAFeedback.id))
            .where(QAFeedback.rating == "negative")
            .where(QAFeedback.reason.is_not(None))
            .group_by(QAFeedback.reason)
            .order_by(func.count(QAFeedback.id).desc(), QAFeedback.reason.asc())
            .limit(5)
        ).all()
        return FeedbackStats(
            total=total,
            positive=positive,
            negative=negative,
            positive_rate=positive / total if total else 0.0,
            top_negative_reasons=[(str(reason), int(count)) for reason, count in reason_rows],
            recent_7d_total=recent_total,
            recent_7d_positive_rate=recent_positive / recent_total if recent_total else 0.0,
            exportable_count=len(self.get_positive_feedback_for_export()),
        )

    def count_since(self, cutoff: datetime, rating: str | None = None) -> int:
        statement = select(func.count(QAFeedback.id)).where(QAFeedback.created_at >= cutoff)
        if rating is not None:
            statement = statement.where(QAFeedback.rating == rating)
        return self.db.scalar(statement) or 0


def clean_required_text(value: str, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required")
    return cleaned


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import QAFeedback


@dataclass(frozen=True)
class FeedbackCreate:
    question: str
    answer: str
    rating: str
    reason: str | None = None
    comment: str | None = None
    question_answer_log_id: int | None = None
    conversation_id: int | None = None
    message_id: int | None = None


class FeedbackRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_feedback(
        self,
        feedback_data: FeedbackCreate,
        commit: bool = True,
    ) -> QAFeedback:
        feedback = QAFeedback(
            question_answer_log_id=feedback_data.question_answer_log_id,
            conversation_id=feedback_data.conversation_id,
            message_id=feedback_data.message_id,
            question=feedback_data.question,
            answer=feedback_data.answer,
            rating=feedback_data.rating,
            reason=feedback_data.reason,
            comment=feedback_data.comment,
        )
        self.db.add(feedback)
        if commit:
            self.db.commit()
            self.db.refresh(feedback)
        return feedback

    def get_by_id(self, feedback_id: int) -> QAFeedback | None:
        statement = select(QAFeedback).where(QAFeedback.id == feedback_id)
        return self.db.scalar(statement)

    def list_feedback(
        self,
        rating: str | None = None,
        limit: int = 100,
    ) -> list[QAFeedback]:
        statement = select(QAFeedback).order_by(QAFeedback.created_at.desc(), QAFeedback.id.desc()).limit(limit)
        if rating is not None:
            statement = statement.where(QAFeedback.rating == rating)
        return list(self.db.scalars(statement).all())

    def count_feedback(self, rating: str | None = None) -> int:
        statement = select(func.count(QAFeedback.id))
        if rating is not None:
            statement = statement.where(QAFeedback.rating == rating)
        return self.db.scalar(statement) or 0

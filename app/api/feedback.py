from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackResponse,
    FeedbackStatsResponse,
)
from app.services.feedback.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
def create_feedback(
    request: FeedbackCreateRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    feedback = FeedbackService(db).submit_feedback(
        question_answer_log_id=request.question_answer_log_id,
        conversation_id=request.conversation_id,
        message_id=request.message_id,
        question=request.question,
        answer=request.answer,
        rating=request.rating,
        reason=request.reason,
        comment=request.comment,
    )
    return FeedbackResponse.model_validate(feedback)


@router.get("/stats", response_model=FeedbackStatsResponse)
def get_feedback_stats(db: Session = Depends(get_db)) -> FeedbackStatsResponse:
    stats = FeedbackService(db).get_feedback_stats()
    return FeedbackStatsResponse(
        total=stats.total,
        positive=stats.positive,
        negative=stats.negative,
        positive_rate=stats.positive_rate,
        top_negative_reasons=dict(stats.top_negative_reasons),
        recent_7d_total=stats.recent_7d_total,
        recent_7d_positive_rate=stats.recent_7d_positive_rate,
        exportable_count=stats.exportable_count,
    )

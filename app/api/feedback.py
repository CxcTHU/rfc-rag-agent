from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.feedback_repository import FeedbackCreate, FeedbackRepository
from app.db.session import get_db
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackResponse,
    FeedbackStatsResponse,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
def create_feedback(
    request: FeedbackCreateRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    repository = FeedbackRepository(db)
    feedback = repository.create_feedback(
        FeedbackCreate(
            question_answer_log_id=request.question_answer_log_id,
            conversation_id=request.conversation_id,
            message_id=request.message_id,
            question=request.question,
            answer=request.answer,
            rating=request.rating,
            reason=request.reason,
            comment=request.comment,
        )
    )
    return FeedbackResponse.model_validate(feedback)


@router.get("/stats", response_model=FeedbackStatsResponse)
def get_feedback_stats(db: Session = Depends(get_db)) -> FeedbackStatsResponse:
    repository = FeedbackRepository(db)
    total = repository.count_feedback()
    positive = repository.count_feedback("positive")
    negative = repository.count_feedback("negative")
    positive_rate = positive / total if total else 0.0
    return FeedbackStatsResponse(
        total=total,
        positive=positive,
        negative=negative,
        positive_rate=positive_rate,
    )

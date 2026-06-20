from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.feedback.exporter import DEFAULT_OUTPUT_PATH, export_feedback_to_eval


router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackExportResponse(BaseModel):
    output_path: str
    dry_run: bool
    candidates: int
    exported: int
    skipped_sensitive: int
    skipped_duplicate: int


@router.get("/export", response_model=FeedbackExportResponse)
def export_feedback(
    dry_run: bool = True,
    since_days: int | None = Query(default=None, ge=0),
    min_length: int = Query(default=50, ge=0),
    output_path: str | None = None,
    db: Session = Depends(get_db),
) -> FeedbackExportResponse:
    result = export_feedback_to_eval(
        db,
        output_path=Path(output_path) if output_path else DEFAULT_OUTPUT_PATH,
        min_length=min_length,
        since_days=since_days,
        dry_run=dry_run,
    )
    return FeedbackExportResponse(
        output_path=result.output_path.as_posix(),
        dry_run=result.dry_run,
        candidates=result.candidates,
        exported=result.exported,
        skipped_sensitive=result.skipped_sensitive,
        skipped_duplicate=result.skipped_duplicate,
    )

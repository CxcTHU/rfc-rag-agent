from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.path_safety import ensure_child_path
from app.core.security import require_admin_when_auth_enabled
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
    settings: Settings = Depends(get_settings),
    _admin=Depends(require_admin_when_auth_enabled),
    db: Session = Depends(get_db),
) -> FeedbackExportResponse:
    try:
        safe_output_path = (
            ensure_child_path(output_path, settings.export_allowed_dir)
            if output_path
            else ensure_child_path(
                Path(settings.export_allowed_dir) / DEFAULT_OUTPUT_PATH.name,
                settings.export_allowed_dir,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    result = export_feedback_to_eval(
        db,
        output_path=safe_output_path,
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

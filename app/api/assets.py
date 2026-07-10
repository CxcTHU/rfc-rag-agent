from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.core.path_safety import ensure_child_path
from app.core.security import get_current_user


router = APIRouter(tags=["assets"])
IMAGE_ASSETS_DIR = Path("data/images")


@router.get("/assets/images/{asset_path:path}", include_in_schema=False)
def get_image_asset(
    asset_path: str,
    _current_user=Depends(get_current_user),
):
    try:
        resolved = ensure_child_path(IMAGE_ASSETS_DIR / asset_path, IMAGE_ASSETS_DIR)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="image asset was not found",
        ) from exc
    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="image asset was not found",
        )
    return FileResponse(resolved)

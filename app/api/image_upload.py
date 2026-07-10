from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.services.agent.image_storage import ImageStorageError, UserImageStorage


router = APIRouter(prefix="/agent", tags=["agent"])


class ImageUploadResponse(BaseModel):
    image_id: str
    path: str
    filename: str
    content_type: str | None = None
    size_bytes: int


def get_user_image_storage(settings: Settings = Depends(get_settings)) -> UserImageStorage:
    return UserImageStorage(max_size_mb=settings.user_image_max_size_mb)


@router.post("/upload-image", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    _current_user=Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    storage: UserImageStorage = Depends(get_user_image_storage),
) -> ImageUploadResponse:
    if not settings.enable_user_image_upload:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user image upload is disabled",
        )
    try:
        stored = await storage.save_upload_file(file)
    except ImageStorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ImageUploadResponse(
        image_id=stored.image_id,
        path=stored.path,
        filename=stored.filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]

    class UnidentifiedImageError(Exception):
        pass


ALLOWED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
ALLOWED_IMAGE_CONTENT_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/webp", "image/bmp", "image/x-ms-bmp"}
)
DEFAULT_USER_UPLOAD_DIR = Path("data/user_uploads")


class ImageStorageError(ValueError):
    status_code = 400


class ImageTooLargeError(ImageStorageError):
    status_code = 413


@dataclass(frozen=True)
class StoredUserImage:
    image_id: str
    path: str
    filename: str
    content_type: str | None
    size_bytes: int


class UserImageStorage:
    def __init__(
        self,
        *,
        base_dir: str | Path = DEFAULT_USER_UPLOAD_DIR,
        max_size_mb: float = 10.0,
    ) -> None:
        if max_size_mb <= 0:
            raise ValueError("max_size_mb must be greater than 0")
        self.base_dir = Path(base_dir)
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)

    async def save_upload_file(self, upload_file) -> StoredUserImage:
        content = await upload_file.read()
        return self.save_bytes(
            content,
            filename=upload_file.filename or "",
            content_type=upload_file.content_type,
        )

    def save_bytes(
        self,
        content: bytes,
        *,
        filename: str,
        content_type: str | None = None,
    ) -> StoredUserImage:
        suffix = validate_image_filename(filename)
        validate_image_content_type(content_type)
        validate_image_size(content, max_size_bytes=self.max_size_bytes)
        validate_image_bytes(content)

        image_id = uuid4().hex
        dated_dir = self.base_dir / datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dated_dir.mkdir(parents=True, exist_ok=True)
        stored_path = dated_dir / f"{image_id}{suffix}"
        stored_path.write_bytes(content)
        return StoredUserImage(
            image_id=image_id,
            path=stored_path.as_posix(),
            filename=Path(filename).name,
            content_type=content_type,
            size_bytes=len(content),
        )

    def validate_existing_upload_path(self, image_path: str | Path) -> Path:
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            raise ImageStorageError("uploaded image does not exist")
        if path.suffix.casefold() not in ALLOWED_IMAGE_EXTENSIONS:
            raise ImageStorageError("unsupported image format")
        resolved_path = path.resolve()
        resolved_base = self.base_dir.resolve()
        try:
            resolved_path.relative_to(resolved_base)
        except ValueError as exc:
            raise ImageStorageError("image path is outside the upload directory") from exc
        validate_image_bytes(path.read_bytes())
        return path

    def cleanup_old_uploads(
        self,
        *,
        days: int = 7,
        now: datetime | None = None,
    ) -> int:
        if days <= 0:
            raise ValueError("days must be greater than 0")
        if not self.base_dir.exists():
            return 0
        reference = now or datetime.now(timezone.utc)
        cutoff = reference.timestamp() - days * 24 * 60 * 60
        removed = 0
        for path in sorted(self.base_dir.rglob("*"), reverse=True):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        return removed


def validate_image_filename(filename: str) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise ImageStorageError(f"unsupported image format; allowed extensions: {allowed}")
    return suffix


def validate_image_content_type(content_type: str | None) -> None:
    if content_type is None:
        return
    normalized = content_type.split(";", 1)[0].strip().casefold()
    if normalized and normalized not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ImageStorageError("unsupported image content type")


def validate_image_size(content: bytes, *, max_size_bytes: int) -> None:
    if not content:
        raise ImageStorageError("uploaded image is empty")
    if len(content) > max_size_bytes:
        raise ImageTooLargeError("uploaded image exceeds the configured size limit")


def validate_image_bytes(content: bytes) -> None:
    if Image is None:
        return
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        raise ImageStorageError("uploaded file is not a readable image") from exc

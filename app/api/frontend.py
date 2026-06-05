from pathlib import Path

from fastapi import APIRouter
from fastapi import Response
from fastapi.responses import FileResponse


router = APIRouter(tags=["frontend"])

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
INDEX_PATH = FRONTEND_DIR / "index.html"


@router.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    return FileResponse(INDEX_PATH)


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)

import csv
from pathlib import Path

from fastapi import APIRouter
from fastapi import Response
from fastapi.responses import FileResponse, JSONResponse


router = APIRouter(tags=["frontend"])

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
ROOT_DIR = Path(__file__).resolve().parents[2]
INDEX_PATH = FRONTEND_DIR / "index.html"
QUALITY_REPORT_PATH = FRONTEND_DIR / "quality_report.html"
QUALITY_SUMMARY_PATH = ROOT_DIR / "data" / "evaluation" / "stage20_quality_summary.csv"


@router.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    return FileResponse(INDEX_PATH)


@router.get("/quality-report", include_in_schema=False)
def quality_report() -> FileResponse:
    return FileResponse(QUALITY_REPORT_PATH)


@router.get("/quality-report/data.json", include_in_schema=False)
def quality_report_data() -> JSONResponse:
    """只读返回阶段 20 质量门槛汇总（来自本地脱敏 CSV，不触发真实 API）。"""

    return JSONResponse(_read_quality_summary())


@router.get("/quality-report/export.csv", include_in_schema=False)
def quality_report_export_csv() -> Response:
    """只读导出阶段 20 质量门槛汇总 CSV。"""

    if not QUALITY_SUMMARY_PATH.exists():
        return Response(status_code=404)
    return FileResponse(
        QUALITY_SUMMARY_PATH,
        media_type="text/csv",
        filename="stage20_quality_summary.csv",
    )


def _read_quality_summary() -> list[dict[str, str]]:
    if not QUALITY_SUMMARY_PATH.exists():
        return []
    with QUALITY_SUMMARY_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)

import csv
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi import Body
from fastapi import HTTPException
from fastapi import Response
from fastapi.responses import FileResponse, JSONResponse


router = APIRouter(tags=["frontend"])

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
ROOT_DIR = Path(__file__).resolve().parents[2]
REACT_FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"
INDEX_PATH = FRONTEND_DIR / "index.html"
REACT_INDEX_PATH = REACT_FRONTEND_DIST_DIR / "index.html"
REACT_FAVICON_PATH = REACT_FRONTEND_DIST_DIR / "favicon.svg"
QUALITY_REPORT_PATH = FRONTEND_DIR / "quality_report.html"
QUALITY_REVIEW_PATH = FRONTEND_DIR / "quality_review.html"
QUALITY_SUMMARY_PATH = ROOT_DIR / "data" / "evaluation" / "stage30_quality_summary.csv"
STAGE29_RESULTS_PATH = ROOT_DIR / "data" / "evaluation" / "stage29_real_quality_results.csv"
STAGE30_DEDUCTIONS_PATH = ROOT_DIR / "data" / "evaluation" / "stage30_quality_deductions.csv"
STAGE30_JUDGE_PATH = ROOT_DIR / "data" / "evaluation" / "stage30_llm_judge_results.csv"
STAGE30_HUMAN_REVIEW_PATH = ROOT_DIR / "data" / "evaluation" / "stage30_human_review.csv"
HUMAN_REVIEW_FIELDS = [
    "reviewed_at",
    "query_id",
    "review_decision",
    "reviewer_note",
]
VALID_REVIEW_DECISIONS = {
    "accept_judge_low_score",
    "override_judge_too_strict",
    "needs_dataset_calibration",
    "needs_retrieval_tuning",
}


@router.get("/", include_in_schema=False)
@router.get("/app-v2", include_in_schema=False)
@router.get("/app-v2/", include_in_schema=False)
def frontend_index() -> FileResponse:
    if not REACT_INDEX_PATH.exists():
        raise HTTPException(status_code=503, detail="React frontend has not been built")
    return FileResponse(REACT_INDEX_PATH)


@router.get("/legacy", include_in_schema=False)
@router.get("/legacy/", include_in_schema=False)
def legacy_frontend_index() -> FileResponse:
    return FileResponse(INDEX_PATH)


@router.get("/app-v2/favicon.svg", include_in_schema=False)
def react_frontend_favicon() -> Response:
    if not REACT_FAVICON_PATH.exists():
        return Response(status_code=204)
    return FileResponse(REACT_FAVICON_PATH)


@router.get("/quality-report", include_in_schema=False)
def quality_report() -> FileResponse:
    return FileResponse(QUALITY_REPORT_PATH)


@router.get("/quality-review", include_in_schema=False)
def quality_review() -> FileResponse:
    return FileResponse(QUALITY_REVIEW_PATH)


@router.get("/quality-report/data.json", include_in_schema=False)
def quality_report_data() -> JSONResponse:
    """只读返回阶段 30 质量评分汇总（来自本地脱敏 CSV，不触发真实 API）。"""

    return JSONResponse(_read_quality_summary())


@router.get("/quality-review/data.json", include_in_schema=False)
def quality_review_data() -> JSONResponse:
    """Human review data assembled from local stage 29/30 CSV artifacts."""

    stage29_rows = _read_csv(STAGE29_RESULTS_PATH)
    deduction_rows = _read_csv(STAGE30_DEDUCTIONS_PATH)
    judge_rows = _read_csv(STAGE30_JUDGE_PATH)
    human_review_rows = _read_csv(STAGE30_HUMAN_REVIEW_PATH)
    return JSONResponse(
        _build_quality_review_payload(
            stage29_rows,
            deduction_rows,
            judge_rows,
            human_review_rows,
        )
    )


@router.post("/quality-review/reviews", include_in_schema=False)
def save_quality_review(payload: dict[str, str] = Body(...)) -> JSONResponse:
    """Persist one local human review decision to a CSV artifact."""

    query_id = (payload.get("query_id") or "").strip()
    decision = (payload.get("review_decision") or "").strip()
    note = (payload.get("reviewer_note") or "").strip()
    if not query_id:
        raise HTTPException(status_code=400, detail="query_id is required")
    if decision not in VALID_REVIEW_DECISIONS:
        raise HTTPException(status_code=400, detail="unsupported review_decision")

    existing_query_ids = {
        row.get("query_id", "")
        for row in _read_csv(STAGE29_RESULTS_PATH)
        if row.get("expected_refused") != "true"
    }
    if query_id not in existing_query_ids:
        raise HTTPException(status_code=404, detail="query_id not found")

    review_row = {
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "query_id": query_id,
        "review_decision": decision,
        "reviewer_note": _sanitize_review_note(note),
    }
    _upsert_human_review(STAGE30_HUMAN_REVIEW_PATH, review_row)
    return JSONResponse({"status": "saved", "review": review_row})


@router.get("/quality-report/export.csv", include_in_schema=False)
def quality_report_export_csv() -> Response:
    """只读导出阶段 30 质量评分汇总 CSV。"""

    if not QUALITY_SUMMARY_PATH.exists():
        return Response(status_code=404)
    return FileResponse(
        QUALITY_SUMMARY_PATH,
        media_type="text/csv",
        filename="stage30_quality_summary.csv",
    )


def _read_quality_summary() -> list[dict[str, str]]:
    return _read_csv(QUALITY_SUMMARY_PATH)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _build_quality_review_payload(
    stage29_rows: list[dict[str, str]],
    deduction_rows: list[dict[str, str]],
    judge_rows: list[dict[str, str]],
    human_review_rows: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    deductions_by_query: dict[str, list[dict[str, str]]] = {}
    for row in deduction_rows:
        deductions_by_query.setdefault(row.get("query_id", ""), []).append(row)

    judge_by_query = {row.get("query_id", ""): row for row in judge_rows}
    human_review_by_query = {
        row.get("query_id", ""): row for row in human_review_rows or []
    }
    cases = []
    for row in stage29_rows:
        if row.get("expected_refused") == "true":
            continue
        query_id = row.get("query_id", "")
        judge = judge_by_query.get(query_id, {})
        deductions = deductions_by_query.get(query_id, [])
        human_review = human_review_by_query.get(query_id, {})
        semantic_average = _average_scores(
            [
                judge.get("faithfulness_score", ""),
                judge.get("answer_relevancy_score", ""),
                judge.get("groundedness_score", ""),
            ]
        )
        case_status = _review_case_status(row, judge, deductions, semantic_average)
        cases.append(
            {
                "query_id": query_id,
                "question": row.get("question", ""),
                "category": row.get("category", ""),
                "expected_source_type": row.get("expected_source_type", ""),
                "top1_source_type": row.get("top1_source_type", ""),
                "top1_document_title": row.get("top1_document_title", ""),
                "top_titles": _split_compact(row.get("top_titles", ""), "||"),
                "precision_at_1": row.get("precision_at_1", ""),
                "precision_at_3": row.get("precision_at_3", ""),
                "precision_at_5": row.get("precision_at_5", ""),
                "rule_based_coverage_ratio": row.get("coverage_ratio", ""),
                "covered_points": _split_compact(row.get("covered_points", ""), ";"),
                "missing_points": _split_compact(row.get("missing_points", ""), ";"),
                "source_type_distribution": row.get("source_type_distribution", ""),
                "stage29_status": row.get("status", ""),
                "judge": {
                    "provider": judge.get("judge_provider", ""),
                    "model": judge.get("judge_model", ""),
                    "faithfulness_score": judge.get("faithfulness_score", ""),
                    "answer_relevancy_score": judge.get("answer_relevancy_score", ""),
                    "groundedness_score": judge.get("groundedness_score", ""),
                    "semantic_average": semantic_average,
                    "reason": judge.get("judge_reason", ""),
                    "error_summary": judge.get("error_summary", ""),
                },
                "deductions": deductions,
                "human_review": {
                    "reviewed_at": human_review.get("reviewed_at", ""),
                    "review_decision": human_review.get("review_decision", ""),
                    "reviewer_note": human_review.get("reviewer_note", ""),
                },
                "review_status": case_status,
            }
        )

    cases.sort(key=_review_sort_key)
    return {
        "summary": {
            "case_count": str(len(cases)),
            "needs_review_count": str(
                sum(1 for case in cases if case["review_status"] != "ok")
            ),
            "blocking_count": str(
                sum(1 for case in cases if case["review_status"] == "critical")
            ),
            "artifact_note": "Read-only view assembled from stage29 results, stage30 deductions, and optional DeepSeek judge CSV.",
        },
        "cases": cases,
    }


def _average_scores(values: list[str]) -> str:
    scores = []
    for value in values:
        try:
            scores.append(float(value))
        except (TypeError, ValueError):
            continue
    if not scores:
        return ""
    return f"{sum(scores) / len(scores):.3f}"


def _review_case_status(
    row: dict[str, str],
    judge: dict[str, str],
    deductions: list[dict[str, str]],
    semantic_average: str,
) -> str:
    if judge.get("error_summary"):
        return "judge_error"
    try:
        semantic_score = float(semantic_average)
    except (TypeError, ValueError):
        semantic_score = 1.0
    try:
        coverage = float(row.get("coverage_ratio", "1"))
    except ValueError:
        coverage = 1.0
    if semantic_score <= 0.25:
        return "critical"
    if deductions or semantic_score < 0.6 or coverage < 0.5:
        return "needs_review"
    return "ok"


def _review_sort_key(case: dict[str, object]) -> tuple[int, float, str]:
    status_rank = {"critical": 0, "needs_review": 1, "judge_error": 2, "ok": 3}
    judge = case.get("judge", {})
    semantic_average = ""
    if isinstance(judge, dict):
        semantic_average = str(judge.get("semantic_average", ""))
    try:
        score = float(semantic_average)
    except ValueError:
        score = 1.0
    return (status_rank.get(str(case.get("review_status", "ok")), 9), score, str(case["query_id"]))


def _split_compact(value: str, separator: str) -> list[str]:
    return [item.strip() for item in value.split(separator) if item.strip()]


def _sanitize_review_note(value: str) -> str:
    text = " ".join((value or "").split())
    blocked_terms = ["api_key", "authorization", "bearer", "raw_response"]
    lowered = text.lower()
    if any(term in lowered for term in blocked_terms):
        raise HTTPException(status_code=400, detail="reviewer_note contains blocked sensitive term")
    if len(text) > 500:
        return f"{text[:497]}..."
    return text


def _upsert_human_review(path: Path, review_row: dict[str, str]) -> None:
    rows = _read_csv(path)
    updated = False
    for index, row in enumerate(rows):
        if row.get("query_id") == review_row["query_id"]:
            rows[index] = review_row
            updated = True
            break
    if not updated:
        rows.append(review_row)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=HUMAN_REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)

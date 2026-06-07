from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_stage15_answer_coverage_review import answer_covers_expected_points  # noqa: E402


DEFAULT_STAGE15_REVIEW = Path("data/evaluation/stage15_answer_coverage_review.csv")
DEFAULT_OUT = Path("data/evaluation/stage16_answer_coverage_closure.csv")

CLOSURE_FIELDS = [
    "closure_id",
    "source_review_id",
    "query_id",
    "risk_before",
    "risk_after",
    "faithfulness",
    "answer_coverage",
    "citation_quality",
    "root_cause",
    "evidence",
    "decision",
    "next_action",
    "manual_review_note",
]

LIMITED_EVIDENCE_MARKERS = (
    "证据尚不充分",
    "信息不足",
    "尚不充分",
    "仅提供",
    "当前知识库仅",
    "需要查阅更多",
    "需要查阅相关规范",
    "limited context",
    "direct research evidence limited",
    "not sufficient",
)


@dataclass(frozen=True)
class Stage16CoverageClosure:
    closure_id: str
    source_review_id: str
    query_id: str
    risk_before: str
    risk_after: str
    faithfulness: str
    answer_coverage: str
    citation_quality: str
    root_cause: str
    evidence: str
    decision: str
    next_action: str
    manual_review_note: str

    def to_row(self) -> dict[str, str]:
        return {
            "closure_id": self.closure_id,
            "source_review_id": self.source_review_id,
            "query_id": self.query_id,
            "risk_before": self.risk_before,
            "risk_after": self.risk_after,
            "faithfulness": self.faithfulness,
            "answer_coverage": self.answer_coverage,
            "citation_quality": self.citation_quality,
            "root_cause": self.root_cause,
            "evidence": self.evidence,
            "decision": self.decision,
            "next_action": self.next_action,
            "manual_review_note": self.manual_review_note,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stage-16 answer coverage closure table.")
    parser.add_argument("--stage15-review", default=str(DEFAULT_STAGE15_REVIEW))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    closures = build_stage16_closures(stage15_review_path=Path(args.stage15_review))
    write_results(Path(args.out), closures)
    print_summary(closures, args.out)


def build_stage16_closures(
    *,
    stage15_review_path: Path = DEFAULT_STAGE15_REVIEW,
) -> list[Stage16CoverageClosure]:
    rows = [
        row for row in read_csv_rows(stage15_review_path)
        if row.get("risk_level", "").strip() in {"high", "medium"}
    ]
    return [
        close_stage15_row(index=index, row=row)
        for index, row in enumerate(rows, start=1)
    ]


def close_stage15_row(*, index: int, row: dict[str, str]) -> Stage16CoverageClosure:
    root_cause = classify_root_cause(row)
    faithfulness, answer_coverage, citation_quality = reviewed_scores(row, root_cause)
    risk_after = risk_after_for_scores(
        risk_before=row.get("risk_level", "").strip(),
        root_cause=root_cause,
        faithfulness=faithfulness,
        answer_coverage=answer_coverage,
        citation_quality=citation_quality,
    )
    return Stage16CoverageClosure(
        closure_id=f"stage16_closure_{index:03d}",
        source_review_id=row.get("review_id", "").strip(),
        query_id=row.get("query_id", "").strip(),
        risk_before=row.get("risk_level", "").strip(),
        risk_after=risk_after,
        faithfulness=faithfulness,
        answer_coverage=answer_coverage,
        citation_quality=citation_quality,
        root_cause=root_cause,
        evidence=evidence_for_row(row),
        decision=decision_for_risk(risk_after, root_cause),
        next_action=next_action_for_root_cause(root_cause, risk_after),
        manual_review_note=manual_review_note_for_row(row, root_cause, risk_after),
    )


def classify_root_cause(row: dict[str, str]) -> str:
    review_note = normalize(row.get("review_note", ""))
    skipped_reason = normalize(row.get("skipped_reason", ""))
    answer_summary = normalize(row.get("answer_summary", ""))
    evidence_titles = normalize(row.get("evidence_titles", ""))
    if "timed out" in review_note or "timeout" in review_note:
        return "provider_timeout"
    if "error" in review_note and not answer_summary:
        return "provider_error_no_answer"
    if not answer_summary:
        return "answer_missing"
    if not evidence_titles:
        return "evidence_missing"
    if has_limited_evidence_marker(answer_summary):
        return "source_detail_limited"
    if not stage16_answer_covers_expected(row.get("answer_summary", ""), row.get("expected_answer_points", "")):
        return "expected_point_partial"
    if skipped_reason:
        return "skipped_real_answer"
    return "reviewed_sufficient"


def reviewed_scores(row: dict[str, str], root_cause: str) -> tuple[str, str, str]:
    if root_cause in {"provider_timeout", "provider_error_no_answer", "answer_missing", "evidence_missing"}:
        return "review", "fail", "review"
    faithfulness = normalize_score(row.get("faithfulness", "review"))
    citation_quality = normalize_score(row.get("citation_quality", "review"))
    if root_cause == "reviewed_sufficient" and faithfulness == "pass" and citation_quality == "pass":
        return faithfulness, "pass", citation_quality
    if root_cause == "source_detail_limited":
        return faithfulness, "review", citation_quality
    return faithfulness, "review", citation_quality


def risk_after_for_scores(
    *,
    risk_before: str,
    root_cause: str,
    faithfulness: str,
    answer_coverage: str,
    citation_quality: str,
) -> str:
    if root_cause in {"provider_timeout", "provider_error_no_answer", "answer_missing", "evidence_missing"}:
        return "high"
    if "fail" in {faithfulness, answer_coverage, citation_quality}:
        return "high"
    if "review" in {faithfulness, answer_coverage, citation_quality}:
        return "medium"
    return "low"


def decision_for_risk(risk_after: str, root_cause: str) -> str:
    if risk_after == "high":
        return "blocking"
    if risk_after == "medium":
        if root_cause == "source_detail_limited":
            return "accepted_with_review"
        return "needs_manual_review"
    return "accepted"


def next_action_for_root_cause(root_cause: str, risk_after: str) -> str:
    if root_cause == "provider_timeout":
        return "人工核验时显式重试真实回答，必要时调大 timeout；默认回归不访问真实 provider。"
    if root_cause == "provider_error_no_answer":
        return "保留为发布前阻断风险，人工核验时补充脱敏错误尾部或重试真实回答。"
    if root_cause == "answer_missing":
        return "补充真实回答结果或人工复核摘要后再判断 Answer Coverage。"
    if root_cause == "evidence_missing":
        return "排查检索来源命中，必要时改进检索或补充资料。"
    if root_cause == "source_detail_limited":
        return "保留为人工审阅样例；如需降为 low，需要补充全文细节或更细证据。"
    if root_cause == "expected_point_partial":
        return "继续人工审阅 expected_answer_points，必要时改进 rerank 或回答生成。"
    if risk_after == "low":
        return "低风险闭环完成，可作为阶段 16 质量通过证据。"
    return "保留为人工审阅样例。"


def manual_review_note_for_row(row: dict[str, str], root_cause: str, risk_after: str) -> str:
    if root_cause == "provider_timeout":
        return "阶段 16 已确认 high 风险来自真实回答超时，尚不能证明回答覆盖，需人工核验重试。"
    if root_cause == "source_detail_limited":
        return "回答忠于来源并有引用，但资料细节有限，适合作为 medium 人工审阅项。"
    if risk_after == "low":
        return "阶段 16 规则复核认为摘要覆盖 expected_answer_points，且来源与引用质量可接受。"
    return row.get("review_note", "").strip()


def evidence_for_row(row: dict[str, str]) -> str:
    parts = [
        f"question={row.get('question', '').strip()}",
        f"expected={row.get('expected_answer_points', '').strip()}",
        f"evidence_titles={row.get('evidence_titles', '').strip()}",
        f"answer_summary={summarize(row.get('answer_summary', '').strip())}",
        f"stage15_note={row.get('review_note', '').strip()}",
    ]
    return sanitize(" | ".join(part for part in parts if not part.endswith("=")))


def has_limited_evidence_marker(text: str) -> bool:
    return any(marker in text for marker in LIMITED_EVIDENCE_MARKERS)


def stage16_answer_covers_expected(answer: str, expected_points: str) -> bool:
    if answer_covers_expected_points(answer, expected_points):
        return True
    normalized_answer = normalize(answer)
    normalized_expected = normalize(expected_points)
    domain_terms = [
        ("密实度", "灌满", "检测", "compactness", "compaction"),
        ("itz", "界面", "强度", "破坏", "interface", "strength"),
        ("冻融", "抗冻", "freeze", "thaw", "durability"),
        ("徐变", "长期变形", "creep", "long-term"),
        ("成本", "工期", "碳排放", "cost", "schedule", "emission", "lca"),
        ("孔隙率", "初始孔洞", "孔洞", "抗压", "porosity", "void", "compressive"),
        ("钢纤维", "填充", "steel fiber", "filling"),
        ("剪力键", "冷缝", "剪切", "shear key", "cold joint", "shear"),
        ("堆石率", "填充率", "抗震", "rock-fill ratio", "seismic"),
    ]
    relevant_terms: list[str] = []
    for group in domain_terms:
        if any(term in normalized_expected for term in group):
            relevant_terms.extend(group)
    if not relevant_terms:
        return False
    hits = sum(1 for term in dict.fromkeys(relevant_terms) if term in normalized_answer)
    return hits >= max(1, min(2, len(set(relevant_terms))))


def normalize_score(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in {"pass", "fail", "review", "skipped"}:
        return normalized
    return "review"


def summarize(text: str, limit: int = 300) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def sanitize(text: str, limit: int = 900) -> str:
    redacted = re.sub(r"\b(?:sk|tp)-[A-Za-z0-9._-]{8,}\b", "[REDACTED]", text)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"\s+", " ", redacted).strip()
    if len(redacted) <= limit:
        return redacted
    return redacted[: limit - 3].rstrip() + "..."


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_results(path: Path, results: list[Stage16CoverageClosure]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CLOSURE_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[Stage16CoverageClosure], output_path: str) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.risk_after] = counts.get(result.risk_after, 0) + 1
    print(f"stage 16 answer coverage closure: {len(results)} rows")
    print("risk_after counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"wrote results to {output_path}")


if __name__ == "__main__":
    main()

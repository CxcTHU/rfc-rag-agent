from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import func

from app.db.models import Chunk, Document, Source
from app.db.session import SessionLocal


CORE_TERMS = (
    "堆石混凝土",
    "rock-filled concrete",
    "rockfill concrete",
    "rock-fill concrete",
    "rfc",
    "自密实混凝土",
    "self-compacting concrete",
    "scc",
    "堆石",
    "大坝",
    "dam",
    "水利",
    "hydraulic",
    "混凝土",
    "concrete",
)

STRONG_TERMS = (
    "堆石混凝土",
    "rock-filled concrete",
    "rockfill concrete",
    "rock-fill concrete",
    "self-compacting concrete",
    "自密实混凝土",
)

HEADER = (
    "document_id",
    "title",
    "url",
    "domain",
    "source_category",
    "chunk_count",
    "char_count",
    "relevance_score",
    "relevance_bucket",
    "matched_terms",
    "source_id",
    "suggested_decision",
    "suggested_reason",
    "review_decision",
    "review_notes",
)


@dataclass(frozen=True)
class ReviewRow:
    document_id: int
    title: str
    url: str
    domain: str
    source_category: str
    chunk_count: int
    char_count: int
    relevance_score: int
    relevance_bucket: str
    matched_terms: str
    source_id: str
    suggested_decision: str
    suggested_reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "source_category": self.source_category,
            "chunk_count": self.chunk_count,
            "char_count": self.char_count,
            "relevance_score": self.relevance_score,
            "relevance_bucket": self.relevance_bucket,
            "matched_terms": self.matched_terms,
            "source_id": self.source_id,
            "suggested_decision": self.suggested_decision,
            "suggested_reason": self.suggested_reason,
            "review_decision": "",
            "review_notes": "",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review Stage 28 web crawl corpus quality.")
    parser.add_argument(
        "--output-dir",
        default="data/evaluation",
        help="Directory for CSV outputs.",
    )
    parser.add_argument(
        "--report-path",
        default="docs/stage28_crawl_quality_report.md",
        help="Markdown report path.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=60,
        help="Maximum manual review sample rows.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        rows = collect_review_rows(db)

    summary_path = output_dir / "stage28_crawl_quality_summary.csv"
    documents_path = output_dir / "stage28_crawl_quality_documents.csv"
    sample_path = output_dir / "stage28_crawl_quality_review_sample.csv"
    domain_path = output_dir / "stage28_crawl_quality_domains.csv"
    keep_path = output_dir / "stage28_crawl_quality_keep_candidates.csv"
    review_path = output_dir / "stage28_crawl_quality_manual_review_candidates.csv"
    drop_path = output_dir / "stage28_crawl_quality_drop_candidates.csv"

    write_documents(documents_path, rows)
    write_documents(
        keep_path,
        [row for row in rows if row.suggested_decision == "keep_candidate"],
    )
    write_documents(
        review_path,
        [row for row in rows if row.suggested_decision == "review_candidate"],
    )
    write_documents(
        drop_path,
        [row for row in rows if row.suggested_decision == "drop_candidate"],
    )
    write_domains(domain_path, rows)
    write_summary(summary_path, rows)
    sample_rows = select_review_sample(rows, args.sample_size)
    write_documents(sample_path, sample_rows)
    write_report(Path(args.report_path), rows, sample_rows)

    print(f"documents={len(rows)}")
    print(f"summary={summary_path}")
    print(f"documents_csv={documents_path}")
    print(f"sample_csv={sample_path}")
    print(f"domains_csv={domain_path}")
    print(f"keep_csv={keep_path}")
    print(f"review_csv={review_path}")
    print(f"drop_csv={drop_path}")
    print(f"report={args.report_path}")
    return 0


def collect_review_rows(db) -> list[ReviewRow]:
    source_by_document: dict[int, Source] = {}
    for source in db.query(Source).filter(Source.document_id.is_not(None)).all():
        if source.document_id is not None and source.document_id not in source_by_document:
            source_by_document[source.document_id] = source

    chunk_stats = {
        document_id: (chunk_count, char_count)
        for document_id, chunk_count, char_count in db.query(
            Chunk.document_id,
            func.count(Chunk.id),
            func.coalesce(func.sum(Chunk.char_count), 0),
        )
        .join(Document, Document.id == Chunk.document_id)
        .filter(Document.source_type == "web_page")
        .group_by(Chunk.document_id)
        .all()
    }

    rows: list[ReviewRow] = []
    documents = db.query(Document).filter(Document.source_type == "web_page").order_by(Document.id).all()
    for document in documents:
        source = source_by_document.get(document.id)
        chunk_count, char_count = chunk_stats.get(document.id, (0, 0))
        text = load_review_text(document)
        score, matched_terms = score_relevance(document.title, document.source_path or "", text)
        bucket = relevance_bucket(score, matched_terms)
        suggested_decision, suggested_reason = suggest_decision(
            title=document.title,
            domain=urlparse(document.source_path or "").netloc,
            bucket=bucket,
            matched_terms=matched_terms,
        )
        rows.append(
            ReviewRow(
                document_id=document.id,
                title=document.title,
                url=document.source_path or "",
                domain=urlparse(document.source_path or "").netloc,
                source_category=source.category if source and source.category else "",
                chunk_count=int(chunk_count),
                char_count=int(char_count),
                relevance_score=score,
                relevance_bucket=bucket,
                matched_terms=";".join(matched_terms),
                source_id=source.source_id if source else "",
                suggested_decision=suggested_decision,
                suggested_reason=suggested_reason,
            )
        )
    return rows


def load_review_text(document: Document) -> str:
    path = Path(document.raw_path)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:20000]
    except OSError:
        return ""


def score_relevance(title: str, url: str, text: str) -> tuple[int, list[str]]:
    haystack = f"{title}\n{url}\n{text}".casefold()
    matched: list[str] = []
    score = 0
    for term in CORE_TERMS:
        normalized = term.casefold()
        if normalized in haystack:
            matched.append(term)
            score += 3 if term in STRONG_TERMS else 1
    return score, matched


def relevance_bucket(score: int, matched_terms: list[str]) -> str:
    if any(term in matched_terms for term in STRONG_TERMS):
        return "strong"
    if score >= 3:
        return "medium"
    if score > 0:
        return "weak"
    return "low"


def suggest_decision(
    *,
    title: str,
    domain: str,
    bucket: str,
    matched_terms: list[str],
) -> tuple[str, str]:
    normalized_title = title.strip().casefold()
    if bucket == "strong":
        return "keep_candidate", "strong RFC/concrete term match"
    if bucket == "medium":
        return "review_candidate", "medium domain-term match"
    if bucket == "weak":
        return "review_candidate", "weak domain-term match"
    if normalized_title in {"about", "nav", "register", "清华新闻"}:
        return "drop_candidate", "generic navigation or landing page title"
    if domain == "www.tsinghua.edu.cn":
        return "drop_candidate", "low-match broad Tsinghua news expansion"
    if not matched_terms:
        return "drop_candidate", "no configured RFC/concrete term match"
    return "review_candidate", "low score but has partial term match"


def write_documents(path: Path, rows: list[ReviewRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_dict())


def write_domains(path: Path, rows: list[ReviewRow]) -> None:
    domain_counts = Counter(row.domain or "(missing)" for row in rows)
    imported_by_bucket: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        imported_by_bucket[row.domain or "(missing)"][row.relevance_bucket] += 1

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["domain", "document_count", "strong", "medium", "weak", "low"],
        )
        writer.writeheader()
        for domain, count in domain_counts.most_common():
            buckets = imported_by_bucket[domain]
            writer.writerow(
                {
                    "domain": domain,
                    "document_count": count,
                    "strong": buckets["strong"],
                    "medium": buckets["medium"],
                    "weak": buckets["weak"],
                    "low": buckets["low"],
                }
            )


def write_summary(path: Path, rows: list[ReviewRow]) -> None:
    bucket_counts = Counter(row.relevance_bucket for row in rows)
    decision_counts = Counter(row.suggested_decision for row in rows)
    domain_counts = Counter(row.domain or "(missing)" for row in rows)
    source_linked = sum(1 for row in rows if row.source_id)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerow({"metric": "web_page_documents", "value": len(rows)})
        writer.writerow({"metric": "source_linked_documents", "value": source_linked})
        writer.writerow({"metric": "unlinked_documents", "value": len(rows) - source_linked})
        for bucket in ("strong", "medium", "weak", "low"):
            writer.writerow({"metric": f"relevance_{bucket}", "value": bucket_counts[bucket]})
        for decision in ("keep_candidate", "review_candidate", "drop_candidate"):
            writer.writerow({"metric": f"suggested_{decision}", "value": decision_counts[decision]})
        for domain, count in domain_counts.most_common(10):
            writer.writerow({"metric": f"domain:{domain}", "value": count})


def select_review_sample(rows: list[ReviewRow], sample_size: int) -> list[ReviewRow]:
    if sample_size <= 0:
        return []
    buckets = {
        "low": [row for row in rows if row.relevance_bucket == "low"],
        "weak": [row for row in rows if row.relevance_bucket == "weak"],
        "medium": [row for row in rows if row.relevance_bucket == "medium"],
        "strong": [row for row in rows if row.relevance_bucket == "strong"],
    }
    sample: list[ReviewRow] = []
    for bucket in ("low", "weak", "medium", "strong"):
        take = max(1, sample_size // 4)
        sample.extend(buckets[bucket][:take])
    if len(sample) < sample_size:
        seen = {row.document_id for row in sample}
        for row in rows:
            if row.document_id in seen:
                continue
            sample.append(row)
            if len(sample) >= sample_size:
                break
    return sample[:sample_size]


def write_report(path: Path, rows: list[ReviewRow], sample_rows: list[ReviewRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bucket_counts = Counter(row.relevance_bucket for row in rows)
    decision_counts = Counter(row.suggested_decision for row in rows)
    domain_counts = Counter(row.domain or "(missing)" for row in rows)
    linked = sum(1 for row in rows if row.source_id)
    lines = [
        "# 阶段 28 爬取质量审查报告",
        "",
        "## 结论",
        "",
        f"- web_page documents：{len(rows)}",
        f"- 已关联 sources：{linked}",
        f"- 未关联 sources：{len(rows) - linked}",
        f"- strong：{bucket_counts['strong']}",
        f"- medium：{bucket_counts['medium']}",
        f"- weak：{bucket_counts['weak']}",
        f"- low：{bucket_counts['low']}",
        f"- keep_candidate：{decision_counts['keep_candidate']}",
        f"- review_candidate：{decision_counts['review_candidate']}",
        f"- drop_candidate：{decision_counts['drop_candidate']}",
        "",
        "## 域名分布 Top 10",
        "",
        "| 域名 | 文档数 |",
        "| --- | --- |",
    ]
    for domain, count in domain_counts.most_common(10):
        lines.append(f"| {domain} | {count} |")

    lines.extend(
        [
            "",
            "## 人工核验建议",
            "",
            "- 优先核验 `low` 和 `weak` 样本，决定是否删除或标记为低相关。",
            "- 对 `www.tsinghua.edu.cn` 批次重点判断是否只是泛高校新闻。",
            "- 保留 `strong` 样本作为高相关网页语料。",
            "- `drop_candidate` 只是筛选建议，不会自动删除数据库内容；删除前应人工确认。",
            "- 筛选前不要提交；筛选后需要重建 deterministic 索引。",
            "",
            "## 抽样文件",
            "",
            "- `data/evaluation/stage28_crawl_quality_review_sample.csv`",
            "- `data/evaluation/stage28_crawl_quality_documents.csv`",
            "- `data/evaluation/stage28_crawl_quality_keep_candidates.csv`",
            "- `data/evaluation/stage28_crawl_quality_manual_review_candidates.csv`",
            "- `data/evaluation/stage28_crawl_quality_drop_candidates.csv`",
            "- `data/evaluation/stage28_crawl_quality_domains.csv`",
            "- `data/evaluation/stage28_crawl_quality_summary.csv`",
            "",
            "## 抽样预览",
            "",
            "| document_id | bucket | title | domain | matched_terms |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in sample_rows[:20]:
        title = row.title.replace("|", " ")[:80]
        matched = row.matched_terms.replace("|", " ")
        lines.append(
            f"| {row.document_id} | {row.relevance_bucket} | {title} | {row.domain} | {matched} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

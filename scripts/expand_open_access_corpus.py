"""阶段 18：开放获取全文语料深度扩充管线（可复跑、诚实报数）。

一条龙：
    OpenAlex 发现 -> RFC 相关性过滤 -> 仅保留许可允许的开放获取 PDF
    -> 礼貌下载到 data/fulltext/open_access_auto（gitignore）
    -> 用加固后的 PDF 解析导入 documents/chunks（source_type=open_access_pdf）
    -> 追加 data/fulltext_manifest.csv 全文权限标注
    -> 诚实打印真实导入篇数

合规与数据安全：
- 只下载许可允许（CC BY / CC BY-NC / CC0 / public domain / 明确 OA）的全文。
- 不绕付费墙、登录、验证码；尊重 robots.txt 与网站条款；下载有 1s 间隔。
- 全文与 DB 都被 gitignore；本脚本是“可复跑导入管线”，真实全文不进 Git。
- 不为凑 40–60 造假；真实导入篇数如实打印。

默认 dry-run（只发现+筛选，不下载、不导入），加 --download --import-to-db 才真正执行。
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.service import (  # noqa: E402
    EmptyDocumentError,
    IngestionConfig,
    IngestionService,
)
from app.services.source_collection import (  # noqa: E402
    SourceCandidate,
    dedupe_candidates,
    filter_relevant_candidates,
    normalize_title,
    read_candidates_csv,
    write_candidates_csv,
)
from scripts.collect_sources import (  # noqa: E402
    DEFAULT_QUERIES,
    collect_openalex,
    download_candidates,
)


# 许可允许重分发/本地保存的开放获取标记（小写包含匹配）。
PERMISSIVE_LICENSE_TOKENS = (
    "cc-by",
    "cc by",
    "cc0",
    "public-domain",
    "public domain",
    "creativecommons",
)
# OpenAlex open_access.oa_status / access_rights 中视为开放的取值。
OPEN_ACCESS_STATUSES = {"gold", "green", "hybrid", "bronze", "diamond", "open"}

MANIFEST_FIELDS = [
    "source_id",
    "title",
    "authors",
    "year",
    "category",
    "source_type",
    "access_rights",
    "license_or_terms",
    "url",
    "pdf_url",
    "local_path",
    "status",
    "notes",
]


def is_permissive_open_access(candidate: SourceCandidate) -> bool:
    """判断候选是否“许可允许的开放获取”，可本地保存全文。"""

    license_text = (candidate.license_or_terms or "").casefold()
    if any(token in license_text for token in PERMISSIVE_LICENSE_TOKENS):
        return True
    access = (candidate.access_rights or "").casefold()
    if access in OPEN_ACCESS_STATUSES:
        return True
    return False


def manifest_row_from_candidate(candidate: SourceCandidate) -> dict[str, str]:
    """把已下载候选转成 fulltext_manifest.csv 行。"""

    license_text = candidate.license_or_terms or "open access (verify exact license before redistribution)"
    return {
        "source_id": candidate.source_id,
        "title": candidate.title,
        "authors": candidate.authors,
        "year": candidate.year,
        "category": candidate.category,
        "source_type": "open_access_pdf",
        "access_rights": "open access",
        "license_or_terms": license_text,
        "url": candidate.url,
        "pdf_url": candidate.pdf_url,
        "local_path": candidate.local_path,
        "status": candidate.status or "downloaded",
        "notes": "stage18 open-access auto expansion; "
        + (candidate.notes or ""),
    }


def append_manifest_rows(manifest_path: Path, rows: list[dict[str, str]]) -> int:
    """把新下载的全文追加到 manifest（按 local_path 和归一化标题双重去重）。"""

    if not rows:
        return 0
    existing_paths: set[str] = set()
    existing_titles: set[str] = set()
    existing_rows: list[dict[str, str]] = []
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                existing_rows.append(row)
                if row.get("local_path"):
                    existing_paths.add(row["local_path"])
                if row.get("title"):
                    existing_titles.add(normalize_title(row["title"]))

    fieldnames = list(existing_rows[0].keys()) if existing_rows else MANIFEST_FIELDS
    new_rows: list[dict[str, str]] = []
    for row in rows:
        local_path = row.get("local_path")
        title_key = normalize_title(row.get("title", ""))
        if not local_path or local_path in existing_paths or title_key in existing_titles:
            continue
        existing_paths.add(local_path)
        existing_titles.add(title_key)
        new_rows.append(row)
    if not new_rows:
        return 0

    with manifest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in [*existing_rows, *new_rows]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return len(new_rows)


def import_downloaded_pdfs(
    candidates: list[SourceCandidate],
    raw_dir: str,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[list[SourceCandidate], int]:
    """把已下载的全文 PDF 用加固解析导入 DB。

    返回 ``(imported_candidates, duplicate_count)``。``imported_candidates`` 只
    包含真正新导入（非 content-hash 重复）的候选，用于精确更新 manifest。
    """

    init_db()
    imported: list[SourceCandidate] = []
    duplicate = 0
    with SessionLocal() as db:
        service = IngestionService(
            db,
            IngestionConfig(raw_dir=raw_dir, chunk_size=chunk_size, chunk_overlap=chunk_overlap),
        )
        for candidate in candidates:
            local_path = Path(candidate.local_path)
            if not local_path.exists() or local_path.suffix.lower() != ".pdf":
                continue
            try:
                result = service.import_document(
                    local_path,
                    title=candidate.title or local_path.stem,
                    source_path=candidate.url or candidate.pdf_url or str(local_path),
                    file_name=local_path.name,
                    source_type="open_access_pdf",
                )
            except EmptyDocumentError:
                print(f"empty\t{candidate.title}")
                continue
            if result.status == "duplicate":
                duplicate += 1
            else:
                imported.append(candidate)
            print(f"{result.status}\tdocument_id={result.document_id}\tchunks={result.chunk_count}\t{candidate.title[:60]}")
    return imported, duplicate


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 18 open-access RFC fulltext corpus expansion.")
    parser.add_argument("--query", action="append", dest="queries", help="Search query. Repeatable.")
    parser.add_argument("--limit", type=int, default=80, help="Results per OpenAlex query.")
    parser.add_argument(
        "--candidates-out",
        default="data/metadata/stage18_oa_discovery.csv",
        help="RFC-relevant discovery output (separate file; does not pollute curated source_candidates.csv).",
    )
    parser.add_argument("--download-dir", default="data/fulltext/open_access_auto")
    parser.add_argument("--manifest", default="data/fulltext_manifest.csv")
    parser.add_argument("--max-downloads", type=int, default=40)
    parser.add_argument("--mailto", default="rfc-rag-agent@example.org")
    parser.add_argument("--download", action="store_true", help="Actually download permissive OA PDFs.")
    parser.add_argument("--import-to-db", action="store_true", help="Import downloaded PDFs with hardened parser.")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    args = parser.parse_args()

    queries = args.queries or DEFAULT_QUERIES

    discovered: list[SourceCandidate] = []
    for query in queries:
        discovered.extend(collect_openalex(query, args.limit, args.mailto))
        time.sleep(1)

    # 只把 RFC 相关候选与已有 discovery 文件合并，避免把非相关 OpenAlex 噪声写入跟踪文件。
    relevant_discovered = filter_relevant_candidates(discovered)
    relevant = dedupe_candidates([*read_candidates_csv(Path(args.candidates_out)), *relevant_discovered])
    permissive = [c for c in relevant if is_permissive_open_access(c) and c.pdf_url]
    not_yet = [c for c in permissive if not (c.local_path or c.status == "downloaded")]

    print(f"discovered={len(discovered)} relevant={len(relevant)}")
    print(f"permissive_oa_with_pdf={len(permissive)} not_yet_downloaded={len(not_yet)}")

    if not args.download:
        print("dry-run: pass --download (and --import-to-db) to actually expand the corpus.")
        write_candidates_csv(Path(args.candidates_out), relevant)
        return

    downloaded_all = download_candidates(permissive, Path(args.download_dir), args.max_downloads)
    by_id = {c.source_id: c for c in relevant}
    for c in downloaded_all:
        by_id[c.source_id] = c
    write_candidates_csv(Path(args.candidates_out), dedupe_candidates(list(by_id.values())))

    just_downloaded = [c for c in downloaded_all if c.status == "downloaded" and c.local_path]
    print(f"downloaded_this_run={len(just_downloaded)}")

    if args.import_to_db:
        imported, duplicate = import_downloaded_pdfs(
            just_downloaded,
            raw_dir=args.raw_dir,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        # 只为真正新导入（非 content 重复）的论文写 manifest，避免重复论文行。
        added = append_manifest_rows(
            Path(args.manifest), [manifest_row_from_candidate(c) for c in imported]
        )
        print(f"imported={len(imported)} duplicate={duplicate} manifest_rows_added={added}")
    else:
        added = append_manifest_rows(
            Path(args.manifest), [manifest_row_from_candidate(c) for c in just_downloaded]
        )
        print(f"manifest_rows_added={added}")


if __name__ == "__main__":
    main()

"""把本地全文 PDF 批量导入语料库（documents/chunks）。统一导入器。

用于导入用户合法下载/本地授权的全文（开放获取或机构授权），例如：

    # 通用：导入一个目录里的全部 PDF
    python scripts/import_papers_corpus.py --dir "G:/Codex/program/papers_NEW"

    # CNKI 场景：知网下载常是 .caj，其中一部分是改名的真 PDF（头 %PDF）；
    # 复制到本地 gitignore 目录、按主题统计、并把真正的专有 CAJ 列入待转换清单
    python scripts/import_papers_corpus.py --dir "G:/Codex/program/papers" \
        --glob "*.caj,*.pdf" --copy-to data/fulltext/cnki_pdf --classify --clean-title

特点：
- 逐文件 try/except（单篇坏 PDF 不中断整批）。
- content_hash 去重（IngestionService 内置），可重复运行（幂等）。
- 只导入真 PDF（文件头 `%PDF`）；专有 CAJ（HN/KDH/CAJ 头）pypdf 读不了，自动跳过，
  并可写入“待用 CAJViewer 转换”清单。
- 可选主题粗分类（rfc_core / dam_engineering）、文件名清洗、复制到本地 gitignore 目录。
- 真实全文只进本地 DB 与 data/raw（均 gitignore），不写入 Git。

合规：仅处理用户已合法获取的文献；受版权/机构授权全文只留本地，不提交、不再分发。
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.service import (  # noqa: E402
    EmptyDocumentError,
    IngestionConfig,
    IngestionService,
)


RFC_CORE_TERMS = [
    "堆石混凝土",
    "自密实",
    "充填堆石",
    "rock-filled concrete",
    "rock filled concrete",
]


def is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(4) == b"%PDF"
    except OSError:
        return False


def classify_topic(name: str) -> str:
    lowered = name.casefold()
    if any(term.casefold() in lowered for term in RFC_CORE_TERMS):
        return "rfc_core"
    return "dam_engineering"


def clean_title(stem: str) -> str:
    """去掉常见文件名噪声：重复标记 " (1)" 与 "_作者" 后缀。"""

    title = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    title = re.sub(r"_[^_]+$", "", title) if "_" in title else title
    return title.strip() or stem


def collect_files(directory: Path, glob_spec: str) -> list[Path]:
    patterns = [p.strip() for p in glob_spec.split(",") if p.strip()]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(directory.glob(pattern))
    return sorted(set(files))


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch import local full-text PDFs into the corpus (unified importer).")
    parser.add_argument("--dir", required=True, help="Directory containing the papers.")
    parser.add_argument("--glob", default="*.pdf", help="Comma-separated file globs (e.g. '*.pdf' or '*.caj,*.pdf').")
    parser.add_argument("--source-type", default="institutional_access_pdf", help="documents.source_type for imported papers.")
    parser.add_argument("--copy-to", default="", help="Copy real PDFs into this local (gitignored) dir before import.")
    parser.add_argument("--classify", action="store_true", help="Print rfc_core/dam_engineering topic counts.")
    parser.add_argument("--clean-title", action="store_true", help="Clean CNKI-style filenames into titles and dedupe by title.")
    parser.add_argument("--pending-list", default="", help="Write skipped true-CAJ filenames needing conversion to this file.")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--limit", type=int, default=0, help="Import at most N files (0 = all).")
    parser.add_argument("--dry-run", action="store_true", help="Report PDF/CAJ split (and topics) without importing.")
    args = parser.parse_args()

    source_dir = Path(args.dir)
    if not source_dir.is_dir():
        raise SystemExit(f"directory not found: {source_dir}")

    files = collect_files(source_dir, args.glob)
    if args.limit:
        files = files[: args.limit]

    real_pdfs = [f for f in files if is_pdf(f)]
    true_caj = [f for f in files if not is_pdf(f)]
    print(f"scanned={len(files)} real_pdf={len(real_pdfs)} non_pdf_skipped={len(true_caj)}")

    if args.pending_list and true_caj:
        pending = Path(args.pending_list)
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(
            "# 需用 CAJViewer 等转成 PDF 后再导入（本文件可被 gitignore）\n"
            + "\n".join(f.name for f in true_caj),
            encoding="utf-8",
        )
        print(f"wrote CAJ pending list ({len(true_caj)}) to {pending}")

    if args.dry_run:
        if args.classify:
            topics: dict[str, int] = {}
            for f in real_pdfs:
                topic = classify_topic(f.name)
                topics[topic] = topics.get(topic, 0) + 1
            print("real_pdf topics:", topics)
        print("dry-run: no import performed.")
        return

    copy_dir = Path(args.copy_to) if args.copy_to else None
    if copy_dir:
        copy_dir.mkdir(parents=True, exist_ok=True)

    init_db()
    imported = duplicate = empty = failed = 0
    total_new_chunks = 0
    topic_counts: dict[str, int] = {}
    seen_titles: set[str] = set()
    failures: list[tuple[str, str]] = []

    with SessionLocal() as db:
        service = IngestionService(
            db,
            IngestionConfig(raw_dir=args.raw_dir, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap),
        )
        for index, path in enumerate(real_pdfs, start=1):
            title = clean_title(path.stem) if args.clean_title else path.stem
            if args.clean_title:
                if title in seen_titles:
                    continue
                seen_titles.add(title)

            import_path = path
            if copy_dir:
                safe_name = re.sub(r"[^\w一-鿿.-]+", "_", title)[:120] + ".pdf"
                import_path = copy_dir / safe_name
                try:
                    shutil.copy(path, import_path)
                except OSError as exc:
                    failed += 1
                    failures.append((path.name, f"copy_failed: {exc}"))
                    continue

            try:
                result = service.import_document(
                    import_path,
                    title=title,
                    source_path=str(path),
                    file_name=import_path.name,
                    source_type=args.source_type,
                )
            except EmptyDocumentError:
                db.rollback()
                empty += 1
                failures.append((path.name, "EmptyDocumentError"))
                continue
            except Exception as exc:  # noqa: BLE001 - keep batch alive
                db.rollback()
                failed += 1
                failures.append((path.name, f"{type(exc).__name__}: {exc}"))
                continue

            topic = classify_topic(path.name)
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
            if result.status == "duplicate":
                duplicate += 1
            else:
                imported += 1
                total_new_chunks += result.chunk_count
            if index % 25 == 0 or index == len(real_pdfs):
                print(f"[{index}/{len(real_pdfs)}] imported={imported} duplicate={duplicate} empty={empty} failed={failed}")

    print("=" * 60)
    print(f"real PDFs            : {len(real_pdfs)}")
    print(f"newly imported       : {imported} (chunks={total_new_chunks})")
    print(f"duplicate (skipped)  : {duplicate}")
    print(f"empty (no text)      : {empty}")
    print(f"failed               : {failed}")
    if args.classify:
        print(f"topics               : {topic_counts}")
    if failures:
        print("--- failures (first 15) ---")
        for name, err in failures[:15]:
            print(f"  {name}: {err}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingestion.service import IngestionConfig, IngestionService  # noqa: E402


BASE_URL = "http://127.0.0.1:23119"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Zotero PDF attachments through the local Zotero API.")
    parser.add_argument("--query", default="rock-filled concrete", help="Zotero search query.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    args = parser.parse_args()

    if not zotero_available():
        print("Zotero local API is not available. Start Zotero Desktop and enable the local API, then rerun.")
        return

    items = zotero_items(args.query, args.limit)
    attachments = []
    for item in items:
        data = item.get("data") or {}
        title = data.get("title") or ""
        for child in zotero_children(item.get("key", "")):
            child_data = child.get("data") or {}
            if child_data.get("itemType") != "attachment":
                continue
            if "pdf" not in (child_data.get("contentType") or "").casefold():
                continue
            file_path = zotero_attachment_path(child.get("key", ""))
            if file_path and file_path.exists():
                attachments.append((title or file_path.stem, data.get("url") or "", file_path))

    init_db()
    with SessionLocal() as db:
        service = IngestionService(
            db,
            IngestionConfig(
                raw_dir=args.raw_dir,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            ),
        )
        for title, url, path in attachments:
            result = service.import_document(
                path,
                title=title,
                source_path=url or str(path),
                file_name=path.name,
                source_type="zotero_attachment_pdf",
            )
            print(f"{result.status}\tdocument_id={result.document_id}\tchunks={result.chunk_count}\t{title}")


def zotero_available() -> bool:
    try:
        data = request_json(f"{BASE_URL}/api/")
        return bool(data)
    except Exception:
        return False


def zotero_items(query: str, limit: int) -> list[dict]:
    params = urllib.parse.urlencode({"q": query, "limit": limit, "include": "data"})
    return request_json(f"{BASE_URL}/api/users/0/items?{params}")


def zotero_children(item_key: str) -> list[dict]:
    if not item_key:
        return []
    return request_json(f"{BASE_URL}/api/users/0/items/{item_key}/children?include=data")


def zotero_attachment_path(attachment_key: str) -> Path | None:
    if not attachment_key:
        return None
    request = urllib.request.Request(f"{BASE_URL}/api/users/0/items/{attachment_key}/file/view/url")
    with urllib.request.urlopen(request, timeout=10) as response:
        text = response.read().decode("utf-8").strip().strip('"')
    if not text.startswith("file:"):
        return None
    return Path(urllib.parse.unquote(urllib.parse.urlparse(text).path.lstrip("/")))


def request_json(url: str):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()

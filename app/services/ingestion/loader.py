import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredRawFile:
    source_path: str
    raw_path: str
    content_hash: str


def store_raw_file(source_path: str | Path, raw_dir: str | Path = "data/raw") -> StoredRawFile:
    source = Path(source_path)
    content_hash = calculate_file_hash(source)
    destination_dir = Path(raw_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    destination = destination_dir / f"{content_hash}{source.suffix.lower()}"
    if not destination.exists():
        shutil.copy2(source, destination)

    return StoredRawFile(
        source_path=str(source),
        raw_path=str(destination),
        content_hash=content_hash,
    )


def calculate_file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

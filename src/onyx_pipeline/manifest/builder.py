from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from ..hashing import streaming_sha256

SKIP_DIRS = {".git", "__pycache__", "dist", "build", ".venv", "venv"}
ALLOWED_EXT = {".pdf", ".txt", ".md"}


def scan_library(lib_root: Path, out_root: Path) -> list[dict]:
    rows: list[dict] = []
    for p in lib_root.rglob("*"):
        if p.is_dir():
            if p.name in SKIP_DIRS:
                continue
            continue
        if p.suffix.lower() not in ALLOWED_EXT:
            continue
        # Avoid scanning inside output root if nested
        try:
            p.relative_to(out_root)
            # inside out_root -> skip
            continue
        except ValueError:
            pass
        size = p.stat().st_size
        file_hash = streaming_sha256(p)
        doc_type = "pdf" if p.suffix.lower() == ".pdf" else "text"
        media_type = "application/pdf" if doc_type == "pdf" else "text/plain"
        rows.append({
            "path": p.relative_to(lib_root).as_posix(),
            "file_hash": file_hash,
            "size": size,
            "doc_type": doc_type,
            "media_type": media_type,
        })
    return rows


def write_manifest_jsonl(rows: Iterable[dict], dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            line = json.dumps(r, ensure_ascii=False)
            f.write(line + "\n")
    tmp.replace(dst)
    return dst

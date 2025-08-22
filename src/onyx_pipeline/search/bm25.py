from __future__ import annotations

from pathlib import Path

from ..storage.atomic import atomic_write_json

# Placeholder BM25 index writer (no real scoring) just stores rows metadata

def write_bm25(chunks: list[dict], idx_path: Path, meta_path: Path) -> None:
    atomic_write_json(idx_path, {"chunks": len(chunks)})
    atomic_write_json(meta_path, {"chunk_count": len(chunks)})

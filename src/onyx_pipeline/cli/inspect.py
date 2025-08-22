from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..manifest.reader import iter_manifest
from ..storage import paths


def inspect_doc(out_root: Path, doc_id: str, *, max_chunks: int = 5) -> dict[str, Any]:
    """Return a JSON-able dict describing a document's derived artifacts."""
    result: dict[str, Any] = {"doc_id": doc_id}
    manifest = paths.manifest_path(out_root)
    manifest_row = None
    if manifest.exists():
        for row in iter_manifest(manifest):
            if row.get("file_hash") and row["file_hash"].startswith(doc_id):
                manifest_row = row
                break
    result["manifest"] = manifest_row
    metas_index = paths.metas_index_path(out_root)
    meta_row = None
    if metas_index.exists():
        for line in metas_index.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("doc_id") == doc_id:
                meta_row = obj
                break
    result["meta"] = meta_row
    chunk_file = paths.chunks_path(out_root, doc_id)
    chunks: list[dict] = []
    if chunk_file.exists():
        for line in chunk_file.read_text(encoding="utf-8").splitlines()[:max_chunks]:
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except Exception:
                pass
    result["chunks_preview"] = chunks
    result["chunks_preview_count"] = len(chunks)
    return result

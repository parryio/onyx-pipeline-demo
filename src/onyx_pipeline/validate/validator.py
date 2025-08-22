from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..chunking.schema import REQUIRED_FIELDS as CHUNK_REQ
from ..metas.schema import REQUIRED_FIELDS as META_REQ
from ..reporting.quarantine import quarantine_path
from ..storage import paths


def validate(out_root: Path) -> dict:
    report: dict = {"chunks": 0, "metas": 0, "errors": [], "warnings": []}
    # manifest presence
    m_path = paths.manifest_path(out_root)
    if not m_path.exists():
        report["errors"].append({"missing_manifest": str(m_path)})
        return report
    # metas index
    metas_index = paths.metas_index_path(out_root)
    if metas_index.exists():
        for line in metas_index.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            try:
                obj = json.loads(line)
                if all(k in obj for k in META_REQ):
                    report["metas"] += 1
            except Exception:
                report["errors"].append({"bad_meta": line[:80]})
    # Chunks
    chunks_dir = out_root / paths.CHUNKS_DIR
    if chunks_dir.exists():
        for f in chunks_dir.glob("*.jsonl"):
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if all(k in obj for k in CHUNK_REQ):
                        report["chunks"] += 1
                except Exception:
                    report["errors"].append({"bad_chunk": f.name})
    # bm25 meta consistency
    bm25_meta = paths.bm25_meta_path(out_root)
    if bm25_meta.exists():
        try:
            meta_obj = json.loads(bm25_meta.read_text(encoding="utf-8"))
            cc = meta_obj.get("chunk_count")
            if cc is not None and cc != report["chunks"]:
                report["errors"].append({"bm25_chunk_mismatch": {"meta": cc, "observed": report["chunks"]}})
        except Exception:
            report["errors"].append({"bm25_meta_invalid": str(bm25_meta)})
    # embeddings consistency
    emb_npy = paths.embeddings_npy_path(out_root)
    rowmap = paths.embeddings_rowmap_path(out_root)
    if emb_npy.exists() and rowmap.exists():
        try:
            arr = np.load(emb_npy)
            rowmap_obj = json.loads(rowmap.read_text(encoding="utf-8"))
            if arr.shape[0] != len(rowmap_obj) or arr.shape[0] != report["chunks"]:
                report["errors"].append({"embeddings_mismatch": {"rows": arr.shape[0], "rowmap": len(rowmap_obj), "chunks": report["chunks"]}})
        except Exception:
            report["errors"].append({"embeddings_invalid": str(emb_npy)})
    # quarantine
    q_path = quarantine_path(out_root)
    if q_path.exists():
        lines = [ln for ln in q_path.read_text(encoding="utf-8").splitlines() if ln]
        report["quarantine"] = {"count": len(lines)}
        # surface first up to 3 reasons as warnings (non-fatal)
        reasons = []
        for ln in lines[:3]:
            try:
                obj = json.loads(ln)
                r = obj.get("reason")
                if r:
                    reasons.append(r)
            except Exception:
                continue
        for r in reasons:
            report["warnings"].append({"quarantine": r})
    # lingering tmp files
    lingering_tmp = list(out_root.rglob("*.tmp"))
    if lingering_tmp:
        report["errors"].append({"tmp_leftovers": len(lingering_tmp)})
    report["error_count"] = len(report["errors"])
    return report

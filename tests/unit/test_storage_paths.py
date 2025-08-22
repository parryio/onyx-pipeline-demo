from pathlib import Path
from onyx_pipeline.storage import paths
import os


def _endswith_path(p: Path, suffix: str) -> bool:
    # Normalize to POSIX-style for suffix comparison
    return p.as_posix().endswith(suffix)


def test_layout_contracts(tmp_path: Path):
    out = tmp_path
    doc_id = "a" * 64
    assert paths.manifest_path(out).is_absolute()
    assert _endswith_path(paths.chunks_path(out, doc_id), f"chunks@v2/{doc_id}.jsonl")
    assert _endswith_path(paths.text_file_path(out, doc_id), f"text@v1/{doc_id}.txt")
    assert _endswith_path(paths.ocr_page_text_path(out, doc_id, 1), f"ocr@v1/{doc_id}/page_000001.txt")
    assert _endswith_path(paths.embeddings_npy_path(out), "embeddings/text@v1/embeddings.npy")
    assert _endswith_path(paths.metas_index_path(out), "metas@v3/metas@v3.index.jsonl")

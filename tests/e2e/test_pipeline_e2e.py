from pathlib import Path
from onyx_pipeline.orchestrator import run_safe_pipeline
from onyx_pipeline.storage.paths import chunks_path, metas_index_path, bm25_meta_path, embeddings_npy_path
import numpy as np


def test_e2e_pipeline(tmp_path: Path):
    lib = tmp_path / "lib"
    out = tmp_path / "out"
    lib.mkdir()
    (lib / "a.txt").write_text("Some example text document for chunking.", encoding="utf-8")
    summary = run_safe_pipeline(lib, out)
    # at least one chunk file
    chunk_files = list((out / "chunks@v2").glob("*.jsonl"))
    assert chunk_files
    assert metas_index_path(out).exists()
    assert bm25_meta_path(out).exists()
    assert embeddings_npy_path(out).exists()
    arr = np.load(embeddings_npy_path(out))
    assert arr.shape[1] == 8192
    assert summary.stats["error_count"] == 0

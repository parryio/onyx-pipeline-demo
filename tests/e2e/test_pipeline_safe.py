from pathlib import Path
import json
import numpy as np
from onyx_pipeline.orchestrator import Orchestrator
from onyx_pipeline.storage import paths


def _read_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l]


def test_pipeline_safe_end_to_end(tmp_path: Path):
    lib = tmp_path / "lib"
    out = tmp_path / "out"
    lib.mkdir()
    # create fixtures
    (lib / "a.txt").write_text("Alpha text file", encoding="utf-8")
    (lib / "b.txt").write_text("Bravo document second file", encoding="utf-8")
    # run pipeline
    summary = Orchestrator.run(lib, out)
    assert summary["stats"]["error_count"] == 0
    # manifest snapshot
    manifest_rows = _read_jsonl(paths.manifest_path(out))
    assert len(manifest_rows) == 2
    keys = {"path", "file_hash", "size", "doc_type", "media_type"}
    for r in manifest_rows:
        assert keys <= set(r)
    # chunks present
    chunk_files = list((out / paths.CHUNKS_DIR).glob("*.jsonl"))
    assert chunk_files
    total_chunks = 0
    for cf in chunk_files:
        rows = _read_jsonl(cf)
        assert rows
        total_chunks += len(rows)
        # schema keys
        ck = {"doc_id", "chunk_id", "text", "order", "char_start", "char_end"}
        for row in rows:
            assert ck <= set(row)
    bm25_meta = json.loads(paths.bm25_meta_path(out).read_text(encoding="utf-8"))
    assert bm25_meta.get("chunk_count") == total_chunks
    arr = np.load(paths.embeddings_npy_path(out))
    assert arr.shape[0] == total_chunks

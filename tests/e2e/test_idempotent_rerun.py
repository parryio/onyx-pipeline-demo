from __future__ import annotations
from pathlib import Path
import hashlib, json
from onyx_pipeline.orchestrator import Orchestrator

def dir_signature(root: Path) -> set[str]:
    sig = set()
    for p in root.rglob('*'):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            sig.add(rel)
    return sig

def test_idempotent_rerun(tmp_path: Path):
    lib = tmp_path / "lib"; out = tmp_path / "out"
    lib.mkdir()
    (lib / "d1.txt").write_text("one two three", encoding="utf-8")
    (lib / "d2.txt").write_text("four five six", encoding="utf-8")
    Orchestrator.run(lib, out)
    sig1 = dir_signature(out)
    bm25_meta = (out / 'bm25.meta.json').read_text(encoding='utf-8')
    Orchestrator.run(lib, out)
    sig2 = dir_signature(out)
    bm25_meta2 = (out / 'bm25.meta.json').read_text(encoding='utf-8')
    assert sig1 == sig2
    assert bm25_meta == bm25_meta2

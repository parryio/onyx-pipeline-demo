from pathlib import Path
from onyx_pipeline.manifest.builder import scan_library, write_manifest_jsonl
from onyx_pipeline.storage.paths import manifest_path


def test_manifest_builder(tmp_path: Path):
    lib = tmp_path / "lib"
    out = tmp_path / "out"
    lib.mkdir()
    (lib / "doc1.txt").write_text("hello", encoding="utf-8")
    rows = scan_library(lib, out)
    assert len(rows) == 1
    m_path = manifest_path(out)
    write_manifest_jsonl(rows, m_path)
    assert m_path.exists()
    content = m_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1

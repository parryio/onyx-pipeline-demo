from pathlib import Path
from onyx_pipeline.hashing import streaming_sha256

def test_streaming_sha256(tmp_path: Path):
    p = tmp_path / "f.txt"
    p.write_text("hello world", encoding="utf-8")
    h = streaming_sha256(p)
    assert h.startswith("sha256:")
    assert len(h) == 7 + 64

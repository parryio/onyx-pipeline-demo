from pathlib import Path
from onyx_pipeline.storage.atomic import atomic_write_text
from onyx_pipeline.storage.safe_fs import safe_join


def test_atomic_no_tmp(tmp_path: Path):
    dst = tmp_path / "out.txt"
    atomic_write_text(dst, "hello")
    assert dst.exists()
    leftovers = list(tmp_path.glob("*.tmp"))
    assert not leftovers


def test_safe_join_basic(tmp_path: Path):
    p = safe_join(tmp_path, "normal")
    assert str(p).endswith("normal")

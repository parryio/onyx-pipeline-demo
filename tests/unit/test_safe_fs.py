from pathlib import Path
import pytest
from onyx_pipeline.storage.safe_fs import safe_join, PathTraversalError


def test_safe_join_ok(tmp_path: Path):
    root = tmp_path
    p = safe_join(root, "a", "b.txt")
    assert p == root / "a" / "b.txt"


def test_safe_join_traversal(tmp_path: Path):
    root = tmp_path
    with pytest.raises(PathTraversalError):
        safe_join(root, "..", "evil.txt")

from pathlib import Path
from onyx_pipeline.storage.atomic import atomic_write_text, atomic_write_json, atomic_write_lines


def test_atomic_write_text(tmp_path: Path):
    p = tmp_path / "a.txt"
    atomic_write_text(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"


def test_atomic_write_json(tmp_path: Path):
    p = tmp_path / "a.json"
    atomic_write_json(p, {"x": 1})
    assert p.read_text(encoding="utf-8").startswith("{")


def test_atomic_write_lines(tmp_path: Path):
    p = tmp_path / "l.txt"
    atomic_write_lines(p, ["a", "b", "c"])
    assert p.read_text(encoding="utf-8").splitlines() == ["a", "b", "c"]

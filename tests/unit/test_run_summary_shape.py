from __future__ import annotations
from pathlib import Path
import json
from onyx_pipeline.orchestrator import Orchestrator

def test_run_summary_shape(tmp_path: Path):
    lib = tmp_path / "lib"; out = tmp_path / "out"
    lib.mkdir()
    (lib / "a.txt").write_text("alpha beta gamma", encoding="utf-8")
    Orchestrator.run(lib, out)
    rs = out / "reports" / "run_summary.json"
    assert rs.exists()
    data = json.loads(rs.read_text(encoding="utf-8"))
    assert "schema_versions" in data
    assert "counts" in data and "chunks" in data["counts"]
    assert "timings" in data

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()  # noqa: S324 (test-only deterministic hash)


def run_pipeline(lib: Path, out: Path) -> dict:
    subprocess.run(["onyx-manifest", "build", "--lib", str(lib), "--out", str(out)], check=True)
    subprocess.run(["onyx-pipeline", "run", "--lib", str(lib), "--out", str(out), "--ocr-lang", "eng"], check=True)
    return json.loads((out / "reports" / "run_summary.json").read_text())


def test_repeat_runs_stable(tmp_path: Path) -> None:
    lib = Path("tests/fixtures")
    out = tmp_path / "out"
    # first run
    summary1 = run_pipeline(lib, out)
    chunks1 = sorted((out / "chunks@v2").glob("*.jsonl"))
    md51 = [md5(p) for p in chunks1]
    # second (idempotent) run - should reuse outputs / stay the same
    summary2 = run_pipeline(lib, out)
    chunks2 = sorted((out / "chunks@v2").glob("*.jsonl"))
    md52 = [md5(p) for p in chunks2]

    assert summary1["counts"] == summary2["counts"], "Document / chunk counts changed between runs"
    assert [p.name for p in chunks1] == [p.name for p in chunks2], "Chunk file set changed"
    assert md51 == md52, "Chunk file contents changed (non-deterministic?)"

import subprocess, sys, os
from pathlib import Path

def _run_cli_timeout(args, timeout=240):
    env = os.environ.copy()
    env.setdefault("ONYX_TEST_STUB_OCR", "1")
    subprocess.run([sys.executable, "-m", "onyx_scribe.cli", *args], check=True, env=env, timeout=timeout)

def _write_text(path: Path, content: str = "Hello determinism world\nThis is stable."):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _count_lines(p: Path) -> int:
    return sum(1 for _ in p.open(encoding="utf-8")) if p.exists() else 0

def test_phase1_deterministic(tmp_path):
    lib = tmp_path / "Library"
    _write_text(lib / "a.txt")
    art_root = tmp_path / "artifacts"
    phase1 = art_root / "phase1"
    phase1.mkdir(parents=True, exist_ok=True)

    _run_cli_timeout(["phase1", "--root", str(lib), "--artifacts", str(art_root), "--config", "config/onyx.yml"], timeout=120)
    with open(phase1 / "chunks.jsonl", "r", encoding="utf-8") as f:
        first_chunks = f.read().splitlines()

    # Clean only isolated directory
    for f in phase1.glob("*.jsonl"):
        f.unlink()

    _run_cli_timeout(["phase1", "--root", str(lib), "--artifacts", str(art_root), "--config", "config/onyx.yml"], timeout=120)
    with open(phase1 / "chunks.jsonl", "r", encoding="utf-8") as f:
        second_chunks = f.read().splitlines()

    assert first_chunks and first_chunks == second_chunks

def test_phase2_verifier(tmp_path):
    lib = tmp_path / "Library"
    _write_text(lib / "a.txt")
    art_root = tmp_path / "artifacts"
    _run_cli_timeout(["phase1", "--root", str(lib), "--artifacts", str(art_root), "--config", "config/onyx.yml"], timeout=120)
    _run_cli_timeout(["phase2", "--root", str(lib), "--artifacts", str(art_root), "--config", "config/onyx.yml"], timeout=120)
    assert (art_root / "phase2" / "provenance.jsonl").exists()
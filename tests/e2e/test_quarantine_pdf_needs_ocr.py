from __future__ import annotations
from pathlib import Path
from onyx_pipeline.orchestrator import Orchestrator
from onyx_pipeline.config import PipelineConfig
import json


def test_quarantine_created_when_pdf_needs_ocr(tmp_path: Path):
    # Create minimal fake PDF (not a valid PDF but triggers empty extraction and OCR attempt)
    lib = tmp_path / "lib"
    out = tmp_path / "out"
    lib.mkdir()
    fake_pdf = lib / "image_only.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n%EOF\n")
    # Run pipeline (OCR language arbitrary)
    summary = Orchestrator.run(lib, out, ocr_lang="eng", include_images=False)
    # Validate quarantine presence via validator logic
    q_file = out / "reports" / "quarantine.jsonl"
    assert q_file.exists(), "quarantine file not created"
    lines = [ln for ln in q_file.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert last["reason"] in {"no_text_after_ocr", "no_text_found_after_ocr", "exception"}
    assert last["stage"] in {"ocr", "processing"}

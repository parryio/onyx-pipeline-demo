from __future__ import annotations

from pathlib import Path

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional
    fitz = None  # type: ignore


def extract_pdf_text(pdf_path: Path) -> list[str]:
    if fitz is None:
        return []
    doc = fitz.open(pdf_path)
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return pages

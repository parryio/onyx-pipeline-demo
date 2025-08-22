from __future__ import annotations

from pathlib import Path

try:
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

def needs_ocr(pdf_path: Path) -> bool:
    """Return True if PDF appears to lack extractable text layer.

    If PyMuPDF missing, return True to allow OCR attempt.
    """
    if fitz is None:
        return True
    try:
        with fitz.open(pdf_path) as doc:  # type: ignore
            if not doc.page_count:  # type: ignore
                return False
            first = doc[0]  # type: ignore
            txt = first.get_text().strip()  # type: ignore
            return len(txt) == 0
    except Exception:
        return True

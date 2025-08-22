from __future__ import annotations

from pathlib import Path

try:  # optional
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

try:  # optional
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore

def run_ocr(pdf_path: Path, lang: str) -> list[str]:
    """Very small OCR implementation.

    Raster pages at low DPI and run pytesseract if available. Empty list
    indicates OCR not possible or produced no content.
    """
    if fitz is None or pytesseract is None:
        return []
    pages: list[str] = []
    try:
        with fitz.open(pdf_path) as doc:  # type: ignore
            for page in doc:  # type: ignore
                pix = page.get_pixmap(dpi=150)  # type: ignore
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)  # type: ignore
                try:
                    txt = pytesseract.image_to_string(img, lang=lang)  # type: ignore
                except Exception:
                    txt = ""
                pages.append(txt.strip())
    except Exception:
        return []
    return [p for p in pages if p]

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # optional dependency
    import fitz  # type: ignore
except Exception:  # pragma: no cover - absence path
    fitz = None  # type: ignore

def harvest_pdf(pdf_path: Path, doc_dir: Path) -> dict[str, Any]:
    """Harvest basic PDF properties (metadata & image count).

    Deterministic and side-effect minimal: does not export image files yet.
    Returns a small dictionary for possible future logging.
    """
    doc_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"images": 0, "meta": {}}
    if fitz is None:
        return report
    try:
        with fitz.open(pdf_path) as doc:  # type: ignore
            report["meta"] = {k: v for k, v in doc.metadata.items() if isinstance(v, (str, int, float))}
            img_count = 0
            for page in doc:  # type: ignore
                img_list = page.get_images(full=True)
                img_count += len(img_list)
            report["images"] = img_count
    except Exception:
        return report
    return report

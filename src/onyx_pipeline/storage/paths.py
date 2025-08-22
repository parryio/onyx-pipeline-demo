from __future__ import annotations

from pathlib import Path

DOCS_DIR = "docs@v1"
IMAGES_DIR = "images@v1"
CHUNKS_DIR = "chunks@v2"
METAS_DIR = "metas@v3"
EMB_DIR = Path("embeddings") / "text@v1"
TEXT_DIR = "text@v1"
OCR_DIR = "ocr@v1"

__all__ = [
    "DOCS_DIR",
    "IMAGES_DIR",
    "CHUNKS_DIR",
    "METAS_DIR",
    "EMB_DIR",
    "manifest_path",
    "doc_folder",
    "images_dir",
    "images_thumbs_dir",
    "text_file_path",
    "ocr_page_text_path",
    "ocr_page_hocr_path",
    "ocr_page_alto_path",
    "chunks_path",
    "chunks_file",  # alias
    "metas_index_path",
    "meta_doc_path",
    "bm25_index_path",
    "bm25_meta_path",
    "embeddings_npy_path",
    "embeddings_rowmap_path",
]


def _abs(out_root: Path) -> Path:
    return out_root if out_root.is_absolute() else out_root.resolve()


def manifest_path(out_root: Path) -> Path:
    return _abs(out_root) / "reports" / "manifest.jsonl"


def doc_folder(out_root: Path, doc_id: str) -> Path:
    return _abs(out_root) / DOCS_DIR / doc_id


def images_dir(out_root: Path, doc_dirname: str) -> Path:
    return _abs(out_root) / IMAGES_DIR / doc_dirname


def images_thumbs_dir(out_root: Path, doc_dirname: str) -> Path:
    return images_dir(out_root, doc_dirname) / "thumbs"


def text_file_path(out_root: Path, doc_id: str) -> Path:
    return _abs(out_root) / TEXT_DIR / f"{doc_id}.txt"


def ocr_doc_dir(out_root: Path, doc_id: str) -> Path:
    return _abs(out_root) / OCR_DIR / doc_id


def _ocr_page_base(out_root: Path, doc_id: str, page: int) -> Path:
    return ocr_doc_dir(out_root, doc_id) / f"page_{page:06d}"


def ocr_page_text_path(out_root: Path, doc_id: str, page: int) -> Path:
    return _ocr_page_base(out_root, doc_id, page).with_suffix(".txt")


def ocr_page_hocr_path(out_root: Path, doc_id: str, page: int) -> Path:
    return _ocr_page_base(out_root, doc_id, page).with_suffix(".hocr")


def ocr_page_alto_path(out_root: Path, doc_id: str, page: int) -> Path:
    return _ocr_page_base(out_root, doc_id, page).with_suffix(".alto.xml")


def chunks_path(out_root: Path, doc_id: str) -> Path:
    return _abs(out_root) / CHUNKS_DIR / f"{doc_id}.jsonl"


def chunks_file(doc_id: str, out_root: Path) -> Path:
    """Alias used in probes/tests."""
    return chunks_path(out_root, doc_id)


def metas_index_path(out_root: Path) -> Path:
    # index file naming convention metas@v3.index.jsonl inside metas@v3
    return _abs(out_root) / METAS_DIR / "metas@v3.index.jsonl"


def meta_doc_path(out_root: Path, doc_id: str) -> Path:
    return _abs(out_root) / METAS_DIR / f"{doc_id}.meta.jsonl"


def bm25_index_path(out_root: Path) -> Path:
    return _abs(out_root) / "bm25_index.pkl"


def bm25_meta_path(out_root: Path) -> Path:
    return _abs(out_root) / "bm25.meta.json"


def embeddings_npy_path(out_root: Path) -> Path:
    return _abs(out_root) / EMB_DIR / "embeddings.npy"


def embeddings_rowmap_path(out_root: Path) -> Path:
    return _abs(out_root) / EMB_DIR / "rowmap.json"

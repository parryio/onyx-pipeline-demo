import json
import hashlib
import io
import contextlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
from pypdf import PdfReader
try:  # pypdf error class (defensive import; older versions may differ)
    from pypdf.errors import PdfReadError  # type: ignore
except Exception:  # pragma: no cover
    PdfReadError = Exception  # fallback

# Optional OCR dependencies; imported lazily-safe for environments without OCR
try:
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore
try:
    from pdf2image import convert_from_path  # type: ignore
except Exception:  # pragma: no cover
    convert_from_path = None  # type: ignore
try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore

LIGATURES = {
    "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st"
}
INVISIBLE = {"\u00ad", "\u200b", "\u200c", "\u200d"}

def normalize_text(text: str) -> str:
    if not text:
        return ""
    for k, v in LIGATURES.items():
        text = text.replace(k, v)
    for ch in INVISIBLE:
        text = text.replace(ch, "")
    # Standardize newlines
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text

def build_chunks(text: str, target_chars: int, overlap: int, split_on: List[str]) -> List[str]:
    text = normalize_text(text)
    if not text.strip():
        return []
    segments = [text]
    for sep in split_on:
        new_segments: List[str] = []
        for seg in segments:
            if len(seg) <= target_chars * 1.2:
                if sep in seg and len(seg) > target_chars:
                    parts = seg.split(sep)
                    for p in parts:
                        if p.strip():
                            new_segments.append(p)
                else:
                    new_segments.append(seg)
            else:
                parts = seg.split(sep)
                for p in parts:
                    if p.strip():
                        new_segments.append(p)
        if new_segments:
            segments = new_segments
    chunks: List[str] = []
    buf: List[str] = []
    cur = 0
    def flush():
        nonlocal buf, cur
        if not buf:
            return
        joined = ' '.join(s.strip() for s in buf if s.strip())
        if joined:
            chunks.append(joined)
        buf = []
        cur = 0
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        l = len(seg)
        if cur + l + 1 <= target_chars:
            buf.append(seg)
            cur += l + 1
        else:
            flush()
            if l > target_chars:
                start = 0
                while start < l:
                    end = min(start + target_chars, l)
                    slice_text = seg[start:end].strip()
                    if slice_text:
                        chunks.append(slice_text)
                    # backward overlap
                    start = end - min(overlap, max(1, target_chars // 4))
            else:
                buf.append(seg)
                cur = l
    flush()
    if overlap > 0 and len(chunks) > 1:
        for i in range(len(chunks) - 1):
            tail = chunks[i][-overlap:]
            if not chunks[i+1].startswith(tail):
                chunks[i+1] = (tail + ' ' + chunks[i+1]).strip()
    out: List[str] = []
    for c in chunks:
        clean = ' '.join(c.split())
        if clean:
            out.append(clean)
    return out

def process_documents(library_root: Path, manifest: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process each document described in the manifest.

    Returns (chunks, events, quarantine, media_assets, qa_report).

    Enhancements:
      - Multi-modal ingestion (images, audio) -> media_assets records + deterministic stub text chunks
      - Explicit chunk provenance via `source_doc_id`
      - Page-level quarantine reason for PDFs (captures failing page index)
    """
    chunk_cfg = (config.get('phase1', {}) or {}).get('chunking', {})
    target_chars = int(chunk_cfg.get('target_chars', 1200))
    overlap = int(chunk_cfg.get('overlap', 120))
    split_on = list(chunk_cfg.get('split_on', ['\n\n', '\n', '. ', '; ', ', ']))
    pdf_cfg = config.get('ingestion', {}).get('pdf', {})
    min_text_chars = int(pdf_cfg.get('min_text_chars', 40))
    doc_nonempty_ratio_min = float(pdf_cfg.get('doc_nonempty_ratio_min', 0.02))
    doc_min_total_chars = int(pdf_cfg.get('doc_min_total_chars', 500))
    partial_rescue = bool(pdf_cfg.get('partial_rescue', False))
    pdf_max_pages = pdf_cfg.get('max_pages')  # optional int limit
    ingestion_cfg = (config.get('ingestion') or {})
    ocr_cfg = ingestion_cfg.get('ocr_deterministic_settings', {})
    phase1_cfg = (config.get('phase1') or {})
    ocr_enabled = bool(((phase1_cfg.get('ocr') or {}).get('enabled', False)))

    chunks: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    quarantine: List[Dict[str, Any]] = []
    media_assets: List[Dict[str, Any]] = []
    qa_report: List[Dict[str, Any]] = []

    for idx, entry in enumerate(manifest):
        if idx and idx % 50 == 0:
            print(f"[phase1] progress docs={idx}/{len(manifest)}", flush=True)
        doc_id = entry['doc_id']
        rel_path = entry['path']
        abs_path = library_root / rel_path
        ext = entry.get('ext', '').lower()
        try:
            if ext == '.txt':
                data = abs_path.read_bytes()
                text = data.decode('utf-8')
                chunk_texts = build_chunks(text, target_chars, overlap, split_on)
                if not chunk_texts:
                    raise ValueError('empty_text')
                for i, ct in enumerate(chunk_texts):
                    chunks.append({
                        'chunk_id': f"{doc_id}_{i:05d}",
                        'doc_id': doc_id,
                        'source_doc_id': doc_id,
                        'text': ct,
                        # PDR Provenance Patch: Non-paged documents use sentinel page id 0
                        'source_page_id': 0
                    })
                events.append({'doc_id': doc_id, 'status': 'text_direct', 'details': f"chunks={len(chunk_texts)}"})
            elif ext == '.pdf':
                # Harden PDF ingestion against corruption; classify known pypdf failures.
                try:
                    # Suppress noisy stdout prints from pypdf (e.g., "Advanced encoding [] not implemented yet")
                    _capture_buf = io.StringIO()
                    with contextlib.redirect_stdout(_capture_buf):
                        reader = PdfReader(str(abs_path))
                    _noise = _capture_buf.getvalue()
                    if _noise:
                        # Optionally log at debug; currently discard to keep console clean.
                        logging.getLogger('onyx_scribe.pdf').debug(_noise.strip())
                except PdfReadError as pe:  # explicit corruption classification
                    reason = f"Corrupt PDF structure: {type(pe).__name__}: {pe}".strip()
                    quarantine.append({'doc_id': doc_id, 'path': rel_path, 'reason': reason})
                    events.append({'doc_id': doc_id, 'status': 'quarantined', 'details': reason})
                    continue
                except Exception as pe_generic:  # other unforeseen failures
                    reason = f"PDF open failed: {type(pe_generic).__name__}: {pe_generic}".strip()
                    quarantine.append({'doc_id': doc_id, 'path': rel_path, 'reason': reason})
                    events.append({'doc_id': doc_id, 'status': 'quarantined', 'details': reason})
                    continue

                raw_pages: List[str] = []
                page_extraction_error = None
                for page_index, p in enumerate(getattr(reader, 'pages', [])):
                    if isinstance(pdf_max_pages, int) and page_index >= pdf_max_pages:
                        break
                    try:
                        raw_pages.append(p.extract_text() or '')
                    except Exception as page_err:
                        page_extraction_error = f"page_error:{page_index}:{type(page_err).__name__}"
                        break
                if page_extraction_error:
                    quarantine.append({'doc_id': doc_id, 'path': rel_path, 'reason': page_extraction_error})
                    events.append({'doc_id': doc_id, 'status': 'quarantined', 'details': page_extraction_error})
                    continue
                norm_pages = [normalize_text(t) for t in raw_pages]
                nonempty_idx = [i for i, t in enumerate(norm_pages) if len(t.strip()) >= min_text_chars]
                doc_nonempty_ratio = len(nonempty_idx) / max(1, len(norm_pages))
                doc_total_chars = sum(len(t) for t in norm_pages)
                mode = 'TEXT_LAYER' if (doc_nonempty_ratio >= doc_nonempty_ratio_min or doc_total_chars >= doc_min_total_chars) else 'OCR_FULL'
                rescue_pages = []
                if partial_rescue and mode == 'TEXT_LAYER':
                    rescue_pages = [i for i, t in enumerate(norm_pages) if len(t.strip()) < min_text_chars]
                if mode == 'OCR_FULL':
                    if not ocr_enabled or pytesseract is None or convert_from_path is None:
                        # Deterministic offline outcome
                        quarantine.append({'doc_id': doc_id, 'path': rel_path, 'reason': 'ocr_full_offline'})
                        events.append({'doc_id': doc_id, 'status': 'quarantined', 'details': json.dumps({
                            'mode': mode,
                            'doc_nonempty_ratio': doc_nonempty_ratio,
                            'doc_total_chars': doc_total_chars
                        }, sort_keys=True)})
                        continue
                    # Perform deterministic OCR with pinned settings
                    dpi = int(ocr_cfg.get('dpi', 300))
                    lang = str(ocr_cfg.get('tesseract_lang', 'eng+osd'))
                    oem = int(ocr_cfg.get('tesseract_oem', 3))
                    psm = int(ocr_cfg.get('tesseract_psm', 3))
                    tess_config = f"--oem {oem} --psm {psm}"
                    try:
                        images = convert_from_path(str(abs_path), dpi=dpi)
                    except Exception as ocr_pdf_err:
                        reason = f"ocr_rasterize_failed:{type(ocr_pdf_err).__name__}: {ocr_pdf_err}"
                        quarantine.append({'doc_id': doc_id, 'path': rel_path, 'reason': reason})
                        events.append({'doc_id': doc_id, 'status': 'quarantined', 'details': reason})
                        continue
                    ocr_texts: List[str] = []
                    ocr_errors = 0
                    for img in images:
                        try:
                            txt = pytesseract.image_to_string(img, lang=lang, config=tess_config)
                        except Exception as tserr:  # deterministic failure path
                            txt = ''
                            ocr_errors += 1
                        ocr_texts.append(normalize_text(txt))
                    # Build chunks from OCR text per page, honoring provenance
                    page_count = 0
                    first_chunk_id = None
                    first_chunk_text = None
                    for i, page_text in enumerate(ocr_texts):
                        if len(page_text.strip()) >= min_text_chars:
                            chunk_id = f"{doc_id}_{i:05d}"
                            chunks.append({
                                'chunk_id': chunk_id,
                                'doc_id': doc_id,
                                'source_doc_id': doc_id,
                                'text': page_text.strip(),
                                'source_page_id': i
                            })
                            page_count += 1
                            if first_chunk_id is None:
                                first_chunk_id = chunk_id
                                first_chunk_text = page_text.strip()
                    # If OCR engine consistently failed and produced no acceptable text, quarantine with specific reason
                    if page_count == 0 and ocr_errors > 0:
                        reason = 'ocr_engine_failed'
                        quarantine.append({'doc_id': doc_id, 'path': rel_path, 'reason': reason})
                        events.append({'doc_id': doc_id, 'status': 'quarantined', 'details': reason})
                        continue
                    # Record as text_layer since output is paginated text with page-level provenance
                    events.append({'doc_id': doc_id, 'status': 'text_layer', 'details': json.dumps({
                        'source': 'ocr',
                        'pages_ocrd': page_count,
                        'dpi': dpi,
                        'lang': lang,
                        'oem': oem,
                        'psm': psm
                    }, sort_keys=True)})
                    # QA report entry for OCR'ed PDFs (first generated chunk only)
                    if first_chunk_id and first_chunk_text is not None:
                        qa_report.append({
                            'doc_id': doc_id,
                            'path': rel_path,
                            'first_chunk_id': first_chunk_id,
                            'text_snippet': first_chunk_text[:250],
                            'ocr_confidence': None
                        })
                    continue
                for i, page_text in enumerate(norm_pages):
                    page_text = page_text.strip()
                    if len(page_text) >= min_text_chars:
                        chunks.append({
                            'chunk_id': f"{doc_id}_{i:05d}",
                            'doc_id': doc_id,
                            'source_doc_id': doc_id,
                            'text': page_text,
                            'source_page_id': i
                        })
                status = 'text_layer'
                events.append({'doc_id': doc_id, 'status': status, 'details': json.dumps({
                    'mode': mode,
                    'doc_nonempty_ratio': doc_nonempty_ratio,
                    'doc_total_chars': doc_total_chars,
                    'rescue_pages': rescue_pages
                }, sort_keys=True)})
            elif ext in {'.png', '.jpg', '.jpeg'}:
                data = abs_path.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                asset_id = f"asset_{sha[:12]}"
                media_assets.append({
                    'asset_id': asset_id,
                    'doc_id': doc_id,
                    'path': rel_path,
                    'media_type': 'image',
                    'sha256': sha
                })
                if ocr_enabled and pytesseract is not None:
                    lang = str(ocr_cfg.get('tesseract_lang', 'eng+osd'))
                    oem = int(ocr_cfg.get('tesseract_oem', 3))
                    psm = int(ocr_cfg.get('tesseract_psm', 3))
                    tess_config = f"--oem {oem} --psm {psm}"
                    txt = ''
                    try:
                        if Image is not None:
                            with Image.open(abs_path) as im:
                                txt = pytesseract.image_to_string(im, lang=lang, config=tess_config)
                    except Exception:
                        txt = ''
                    text_norm = normalize_text(txt)
                    if not text_norm.strip():
                        text_norm = f"[OCR_IMAGE {sha[:16]} bytes={len(data)}]"
                    chunk_id = f"{doc_id}_00000"
                    chunks.append({
                        'chunk_id': chunk_id,
                        'doc_id': doc_id,
                        'source_doc_id': doc_id,
                        'text': text_norm,
                        'source_page_id': 0
                    })
                    events.append({'doc_id': doc_id, 'status': 'ocr_full', 'details': json.dumps({'mode': 'ocr', 'asset_id': asset_id}, sort_keys=True)})
                    # QA entry for OCR'ed images
                    qa_report.append({
                        'doc_id': doc_id,
                        'path': rel_path,
                        'first_chunk_id': chunk_id,
                        'text_snippet': text_norm[:250],
                        'ocr_confidence': None
                    })
                else:
                    stub_text = f"[OCR_IMAGE {sha[:16]} bytes={len(data)}]"
                    chunks.append({
                        'chunk_id': f"{doc_id}_00000",
                        'doc_id': doc_id,
                        'source_doc_id': doc_id,
                        'text': stub_text,
                        # PDR Provenance Patch: sentinel page id for non-paged asset
                        'source_page_id': 0
                    })
                    events.append({'doc_id': doc_id, 'status': 'ocr_full', 'details': json.dumps({'mode': 'stub', 'asset_id': asset_id}, sort_keys=True)})
            elif ext in {'.mp3', '.wav'}:
                data = abs_path.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                asset_id = f"asset_{sha[:12]}"
                media_assets.append({
                    'asset_id': asset_id,
                    'doc_id': doc_id,
                    'path': rel_path,
                    'media_type': 'audio',
                    'sha256': sha
                })
                # Per PDR update, audio assets are catalogued but not chunked.
                # A 'audio_cataloged' event is created to signal that Phase 1 has completed its duty for this file.
                events.append({'doc_id': doc_id, 'status': 'audio_cataloged', 'details': json.dumps({'mode': 'stub', 'asset_id': asset_id}, sort_keys=True)})
            else:
                quarantine.append({'doc_id': doc_id, 'path': rel_path, 'reason': 'unsupported_extension'})
                events.append({'doc_id': doc_id, 'status': 'quarantined', 'details': 'unsupported_extension'})
        except Exception as e:
            quarantine.append({'doc_id': doc_id, 'path': rel_path, 'reason': str(e)})
            events.append({'doc_id': doc_id, 'status': 'quarantined', 'details': str(e)})

    return chunks, events, quarantine, media_assets, qa_report

__all__ = ["process_documents", "build_chunks", "normalize_text"]

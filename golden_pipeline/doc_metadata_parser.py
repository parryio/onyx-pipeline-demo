from __future__ import annotations
import json, re
from pathlib import Path
from typing import List, Dict, Any


def build_doc_metadata(manifest_path: Path) -> List[Dict[str, Any]]:
    """Build Phase 3 doc metadata records from Phase 1 manifest.

    Schema (phase3_doc_metadata.schema.json) requires:
        doc_id, path, metadata{collection,title, optional: tradition, author, topic}

    Heuristics (deterministic, offline):
      - collection: first path segment
      - title: final path segment with extension removed (if present)
      - author: segment containing a pattern like 'author-' or 'by-' stripped, else unknown
      - tradition: if collection matches a known tradition list, reuse; else leave absent
      - topic: second to last segment if it looks like a folder (length > 3) and not purely numeric
    All optional fields only emitted if confidently derived so gate does not fail due to empty strings.
    """
    KNOWN_TRADITIONS = {
        'Golden Dawn', 'Enochian', 'Astrology', 'Tarot', 'Alchemy', 'Rosicrucian', 'Sacred Geometry'
    }
    rows: List[Dict[str, Any]] = []
    with open(manifest_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            m = json.loads(line)
            path = m['path']
            parts = [p for p in path.split('/') if p]
            collection = parts[0] if parts else 'UNKNOWN'
            raw_title = parts[-1] if parts else 'untitled'
            title = _strip_ext(raw_title)
            metadata: Dict[str, Any] = {
                'collection': collection,
                'title': title
            }
            # Attempt tradition inference
            if collection in KNOWN_TRADITIONS:
                metadata['tradition'] = collection
            # Author heuristic: look for ' - ' separated pattern or a segment containing a comma
            possible_author = None
            for seg in parts[1:-1]:
                if 'author' in seg.lower() or 'by-' in seg.lower() or ',' in seg:
                    possible_author = _clean_author(seg)
                    break
            if possible_author:
                metadata['author'] = possible_author
            # Topic heuristic: penultimate segment if not same as collection and not clearly an author
            if len(parts) > 2:
                penult = parts[-2]
                if penult not in (collection, possible_author or '') and len(penult) > 3 and not re.match(r'^\d+$', penult):
                    metadata['topic'] = penult
            rows.append({'doc_id': m['doc_id'], 'path': path, 'metadata': metadata})
    rows.sort(key=lambda r: r['doc_id'])
    return rows


def _strip_ext(name: str) -> str:
    if '.' in name and not name.startswith('.'):
        return name.rsplit('.', 1)[0]
    return name


def _clean_author(seg: str) -> str:
    seg = re.sub(r'(?i)author[-_]?','', seg)
    seg = re.sub(r'(?i)by[-_]?', '', seg)
    seg = seg.replace('_',' ').replace('-', ' ').strip()
    return seg

__all__ = ['build_doc_metadata']

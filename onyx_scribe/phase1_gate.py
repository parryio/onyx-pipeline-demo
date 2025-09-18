"""Phase 1 Gate (PDR canonical)

Performs deterministic validation of Phase 1 artifacts:
 - Schema validation for manifest / chunks / events / quarantine
 - Ordering guarantees (sorted by key)
 - LF line endings across all artifacts (reject CRLF)
 - Parity: one event per manifest doc_id
 - Uniqueness: exactly one event per doc_id, no duplicate doc_id or sha256 in manifest
 - Quarantine referential integrity (doc_ids must exist in manifest)
 - Chunk integrity: non-empty text, pattern validated by schema, optional page provenance
 - Page provenance: For PDF-derived chunks (presence of source_page_id), enforce integer >=0 and uniqueness per (doc_id, source_page_id)
 - Event vocabulary restricted to: text_direct (plain text), text_layer (PDF extracted), quarantined (failed or offline OCR full)

This module is imported by the CLI and thin wrapper script `scripts/verify_phase1.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Set
import sys
import jsonschema

VALID_EVENT_STATUSES = {"text_direct", "text_layer", "ocr_full", "ocr_rescue", "audio_cataloged", "quarantined"}

def _load_schema(name: str) -> Dict[str, Any]:
    return json.loads(Path("tools/schemas") / name .read_text())  # type: ignore

def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8') as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise GateError(f"Invalid JSON in {path} line {ln}: {e}")
    return data

class GateError(Exception):
    pass

def verify_phase1_artifacts(artifacts_root: str | Path) -> None:
    phase1_dir = Path(artifacts_root) / 'phase1'
    if not phase1_dir.exists():
        raise GateError(f"Missing phase1 directory: {phase1_dir}")

    manifest_path = phase1_dir / 'manifest.jsonl'
    chunks_path = phase1_dir / 'chunks.jsonl'
    events_path = phase1_dir / 'events.jsonl'
    quarantine_path = phase1_dir / 'quarantine.jsonl'
    media_assets_path = phase1_dir / 'media_assets.jsonl'

    required = [manifest_path, chunks_path, events_path, quarantine_path, media_assets_path]
    for p in required:
        if not p.exists():
            raise GateError(f"Missing artifact: {p}")

    # Line ending enforcement (CRLF forbidden)
    for p in required:
        raw = p.read_bytes()
        if b'\r\n' in raw:
            raise GateError(f"CRLF line endings detected in {p.name}; must be LF only")

    # Load schemas
    schema_dir = Path('tools/schemas')
    manifest_schema = json.loads((schema_dir / 'phase1_manifest.schema.json').read_text())
    chunks_schema = json.loads((schema_dir / 'phase1_chunks.schema.json').read_text())
    events_schema = json.loads((schema_dir / 'phase1_events.schema.json').read_text())
    quarantine_schema = json.loads((schema_dir / 'phase1_quarantine.schema.json').read_text())
    media_schema = json.loads((schema_dir / 'phase1_media_assets.schema.json').read_text())

    # Load data
    manifest = _load_jsonl(manifest_path)
    chunks = _load_jsonl(chunks_path)
    events = _load_jsonl(events_path)
    quarantine = _load_jsonl(quarantine_path)
    media_assets = _load_jsonl(media_assets_path)

    errors: List[str] = []

    # Schema validation & ordering
    _validate_and_order(manifest, manifest_schema, 'doc_id', 'manifest', errors)
    _validate_and_order(chunks, chunks_schema, 'chunk_id', 'chunks', errors)
    _validate_and_order(events, events_schema, 'doc_id', 'events', errors)
    _validate_and_order(quarantine, quarantine_schema, 'doc_id', 'quarantine', errors)
    if media_assets:
        _validate_and_order(media_assets, media_schema, 'asset_id', 'media_assets', errors)

    manifest_doc_ids = [m['doc_id'] for m in manifest]
    manifest_doc_id_set = set(manifest_doc_ids)

    # Manifest uniqueness (doc_id, sha256)
    seen_doc: Set[str] = set()
    seen_sha: Set[str] = set()
    for m in manifest:
        d = m['doc_id']
        if d in seen_doc:
            errors.append(f"Duplicate doc_id in manifest: {d}")
        else:
            seen_doc.add(d)
        sha = m['sha256']
        if sha in seen_sha:
            errors.append(f"Duplicate sha256 in manifest: {sha}")
        else:
            seen_sha.add(sha)

    # Parity + event uniqueness
    if len(events) != len(manifest):
        errors.append(f"Parity mismatch: manifest count {len(manifest)} vs events {len(events)}")
    event_seen: Set[str] = set()
    for ev in events:
        st = ev.get('status')
        if st not in VALID_EVENT_STATUSES:
            errors.append(f"Invalid events.status: {st}")
        d = ev['doc_id']
        if d not in manifest_doc_id_set:
            errors.append(f"Event doc_id not in manifest: {d}")
        if d in event_seen:
            errors.append(f"Multiple events for doc_id: {d}")
        else:
            event_seen.add(d)

    # Cross-check: event.status must be appropriate for source file extension
    # Derive extension map from manifest.path
    ext_map: Dict[str, str] = {}
    for m in manifest:
        # Robust single-extension extraction using pathlib (patch PDR resilience)
        p = m['path']
        ext_map[m['doc_id']] = Path(p).suffix.lower()
    status_allowed: Dict[str, Set[str]] = {
        '.txt': {'text_direct', 'quarantined'},
        '.pdf': {'text_layer', 'quarantined'},  # pdf images not yet extracted; full OCR -> quarantined or text_layer
        '.png': {'ocr_full', 'quarantined'},
        '.jpg': {'ocr_full', 'quarantined'},
        '.jpeg': {'ocr_full', 'quarantined'},
        '.mp3': {'audio_cataloged', 'quarantined'},
        '.wav': {'audio_cataloged', 'quarantined'},
    }
    for ev in events:
        doc_ext = ext_map.get(ev['doc_id'])
        if not doc_ext:
            continue
        allowed = status_allowed.get(doc_ext, {'quarantined'})
        if ev['status'] not in allowed:
            errors.append(f"events.status '{ev['status']}' not valid for extension {doc_ext} (doc_id={ev['doc_id']})")

    # Quarantine referential integrity
    for q in quarantine:
        if q['doc_id'] not in manifest_doc_id_set:
            errors.append(f"Quarantine doc_id not in manifest: {q['doc_id']}")
    # Media referential integrity
    for a in media_assets:
        if a.get('doc_id') not in manifest_doc_id_set:
            errors.append(f"Media asset doc_id not in manifest: {a.get('doc_id')}")

    # Chunk integrity & universal provenance (PDR Provenance Patch)
    provenance_map: Dict[str, Set[int]] = {}
    # Build an event status index for cross-referencing
    event_status: Dict[str, str] = {e['doc_id']: e.get('status', '') for e in events}
    for c in chunks:
        cid = c.get('chunk_id')
        if not c.get('text', '').strip():
            errors.append(f"Blank chunk text: {cid}")
        # Required provenance fields
        sd = c.get('source_doc_id')
        if not sd or sd not in manifest_doc_id_set:
            errors.append(f"Invalid or missing source_doc_id for chunk {cid}")
        if 'source_page_id' not in c:
            errors.append(f"Missing source_page_id for chunk {cid} (must be present for all chunks; non-paged sentinel=0)")
            continue
        val = c['source_page_id']
        if not isinstance(val, int):
            errors.append(f"source_page_id must be integer for {cid}: {val}")
            continue
        # Determine rule set from events.status
        st = event_status.get(c['doc_id'])
        if st == 'text_layer':
            if val < 0:
                errors.append(f"PDF chunk {cid} has negative source_page_id {val}")
            # Uniqueness per (doc_id, source_page_id)
            s = provenance_map.setdefault(c['doc_id'], set())
            if val in s:
                errors.append(f"Duplicate source_page_id {val} for doc_id {c['doc_id']}")
            else:
                s.add(val)
        elif st in {'text_direct', 'ocr_full'}:
            if val != 0:
                errors.append(f"Non-paged chunk {cid} has non-zero source_page_id {val}; must be 0")
        else:
            # Unknown/missing status falls back to extension rule
            ext = ext_map.get(c['doc_id'])
            if ext == '.pdf':
                if val < 0:
                    errors.append(f"PDF chunk {cid} has negative source_page_id {val}")
                s = provenance_map.setdefault(c['doc_id'], set())
                if val in s:
                    errors.append(f"Duplicate source_page_id {val} for doc_id {c['doc_id']}")
                else:
                    s.add(val)
            else:
                if val != 0:
                    errors.append(f"Non-paged chunk {cid} has non-zero source_page_id {val}; must be 0")

    # PDR Compliance: Contract enforcement for chunk presence based on event status.
    chunk_doc_ids = {c['doc_id'] for c in chunks}
    quarantined_ids = {q['doc_id'] for q in quarantine}
    text_generating_statuses = {'text_layer', 'ocr_full', 'text_direct'}

    for doc_id, status in event_status.items():
        if status == 'audio_cataloged':
            if doc_id in chunk_doc_ids:
                errors.append(f"Contract violation: doc_id {doc_id} has 'audio_cataloged' status but has chunks in chunks.jsonl")
        elif status in text_generating_statuses:
            if doc_id not in chunk_doc_ids and doc_id not in quarantined_ids:
                errors.append(f"Contract violation: doc_id {doc_id} has status '{status}' but has no chunks and is not quarantined.")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}", file=sys.stderr)
        raise GateError("Phase 1 gate failed")

    print("  [PASS] Phase 1 verification successful.")

def _validate_and_order(data: List[Dict[str, Any]], schema: Dict[str, Any], key: str, label: str, errors: List[str]) -> None:
    for i, item in enumerate(data):
        try:
            jsonschema.validate(instance=item, schema=schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation failed for {label} line {i+1}: {e.message}")
    if data:
        keys = [d[key] for d in data]
        if keys != sorted(keys):
            errors.append(f"Ordering Error: {label} not sorted by {key}")

__all__ = ["verify_phase1_artifacts", "GateError"]

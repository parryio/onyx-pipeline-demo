"""
Phase 3 Gate (Hardened)

Validates Phase 3 artifacts against PDR v2.2.0 contracts.
Checks:
 1. Schema validation for doc_metadata.jsonl & entities.jsonl
 2. Canonical ordering
 3. Traceability to phase1/chunks.jsonl
 4. Enrichment cache digest pin (metrics vs actual)
"""
from __future__ import annotations
import json, hashlib, sys, yaml
from pathlib import Path
from typing import List, Dict, Any
import jsonschema

class GateError(Exception):
    pass

DOC_SCHEMA_PATH = Path('tools/schemas/phase3_doc_metadata.schema.json')
CACHE_SCHEMA_PATH = Path('tools/schemas/phase3_enrichment_cache.schema.json')
EMPTY_CACHE_DIGEST = hashlib.sha256(b'').hexdigest()

ENTITY_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'title': 'Phase 3 Entities',
    'type': 'object',
    'properties': {
    'entity_id': {'type': 'string', 'pattern': '^ent_[a-z0-9\-]+_[a-f0-9]{12}$'},
        'raw_value': {'type': 'string', 'minLength': 1},
        'norm_value': {'type': 'string', 'minLength': 1},
        'type': {'type': 'string', 'minLength': 1},
        'source_chunk_id': {'type': ['string', 'number']},
        'char_start': {'type': 'integer', 'minimum': 0},
        'char_end': {'type': 'integer', 'minimum': 1}
    },
    'required': ['entity_id', 'raw_value', 'norm_value', 'type', 'source_chunk_id', 'char_start', 'char_end']
}

def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8') as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise GateError(f"Invalid JSON in {path} line {ln}: {e}")
    return out


def _file_sha256(path: Path) -> str:
    h=hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_phase3_artifacts(artifacts_root: str | Path, config_path: str | Path = 'config/onyx.yml') -> None:
    artifacts_root = Path(artifacts_root)
    phase1 = artifacts_root / 'phase1'
    phase3 = artifacts_root / 'phase3'

    doc_metadata_path = phase3 / 'doc_metadata.jsonl'
    entities_path = phase3 / 'entities.jsonl'
    metrics_path = phase3 / 'metrics_phase3.json'
    chunks_path = phase1 / 'chunks.jsonl'
    # Load config to resolve enrichment cache path
    try:
        cfg = yaml.safe_load(Path(config_path).read_text())
    except Exception as e:
        raise GateError(f"Failed to load config {config_path}: {e}")
    cache_cfg_path = (cfg.get('phase3') or {}).get('enrichment_cache') or 'datasets/phase3/enrichment_cache.jsonl'
    cache_path = Path(cache_cfg_path)

    for p in [doc_metadata_path, entities_path, metrics_path, chunks_path]:
        if not p.exists():
            raise GateError(f"Missing required artifact: {p}")

    doc_schema = json.loads(DOC_SCHEMA_PATH.read_text()) if DOC_SCHEMA_PATH.exists() else None

    doc_metadata = _load_jsonl(doc_metadata_path)
    entities = _load_jsonl(entities_path)
    chunks = _load_jsonl(chunks_path)
    chunk_ids = {c['chunk_id'] for c in chunks}

    errors: List[str] = []

    # 1. Schema validation
    if not doc_schema:
        errors.append(f"Missing doc metadata schema: {DOC_SCHEMA_PATH}")
    else:
        for i, row in enumerate(doc_metadata):
            try:
                jsonschema.validate(row, doc_schema)
            except jsonschema.ValidationError as e:
                errors.append(f"doc_metadata line {i+1} schema error: {e.message}")
    for i, row in enumerate(entities):
        try:
            jsonschema.validate(row, ENTITY_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"entities line {i+1} schema error: {e.message}")

    # 2. Canonical ordering
    if doc_metadata and [r['doc_id'] for r in doc_metadata] != sorted(r['doc_id'] for r in doc_metadata):
        errors.append('doc_metadata not sorted by doc_id')
    if entities and [r['entity_id'] for r in entities] != sorted(r['entity_id'] for r in entities):
        errors.append('entities not sorted by entity_id')

    # 3. Traceability & span sanity
    chunk_map = {c['chunk_id']: c for c in chunks}
    for ent in entities:
        if ent['source_chunk_id'] not in chunk_ids:
            errors.append(f"Traceability failure: entity {ent['entity_id']} references missing chunk {ent['source_chunk_id']}")
            continue
        ch_text = chunk_map[ent['source_chunk_id']].get('text','')
        cs, ce = ent.get('char_start'), ent.get('char_end')
        if not isinstance(cs, int) or not isinstance(ce, int) or cs < 0 or ce <= cs or ce > len(ch_text):
            errors.append(f"Invalid span for entity {ent['entity_id']} ({cs},{ce})")
            continue
        slice_txt = ch_text[cs:ce]
        if slice_txt != ent.get('raw_value'):
            errors.append(f"Span fidelity mismatch entity {ent['entity_id']} raw_value != text slice")

    # 4. Cache digest pin
    try:
        metrics = json.loads(metrics_path.read_text())
    except Exception as e:
        errors.append(f"Failed to read metrics: {e}")
        metrics = {}
    expected_digest = metrics.get('enrichment_cache_digest')
    metrics_empty = bool(metrics.get('enrichment_cache_empty'))
    actual_digest = None
    if cache_path.exists():
        actual_digest = _file_sha256(cache_path)
        if metrics_empty and actual_digest != EMPTY_CACHE_DIGEST:
            errors.append('Metrics flagged empty cache but cache file digest is not empty sha256')
        if not metrics_empty and actual_digest == EMPTY_CACHE_DIGEST:
            errors.append('Cache file digest is empty sha256 but metrics did not flag empty cache')
    else:
        if metrics_empty:
            actual_digest = EMPTY_CACHE_DIGEST
        else:
            errors.append(f"Missing required artifact: {cache_path}")

    if expected_digest is None:
        errors.append('Metrics missing enrichment_cache_digest')
    elif actual_digest is None:
        errors.append('Unable to compute enrichment cache digest for comparison')
    elif expected_digest != actual_digest:
        errors.append(f"Cache digest mismatch expected={expected_digest} actual={actual_digest}")

    # 5. Spot-check random subset for stronger fidelity (if large)
    import random
    if not errors and entities:
        random.seed(0)
        sample_size = min(200, len(entities))
        sample = random.sample(entities, sample_size)
        for s in sample:
            ch_text = chunk_map[s['source_chunk_id']].get('text','')
            if ch_text[s['char_start']:s['char_end']] != s['raw_value']:
                errors.append(f"Random spot-check failed for entity {s['entity_id']}")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}", file=sys.stderr)
        raise GateError('Phase 3 gate failed')
    print('  [PASS] Phase 3 verification successful.')

if __name__ == '__main__':
    try:
        verify_phase3_artifacts('artifacts')
    except GateError as e:
        print(f"Error: {e}")
        sys.exit(1)

import json
import math
from pathlib import Path

from onyx_scribe.hash_embedder import build_hash_embeddings
from onyx_scribe.provenance_builder import build_provenance


def _make_minimal_phase1(tmp_path: Path):
    phase1 = tmp_path / 'phase1'
    phase1.mkdir()
    # chunks.jsonl with crafted texts
    chunks = [
        {"chunk_id": 1, "doc_id": 10, "text": "alpha"},
        {"chunk_id": 2, "doc_id": 11, "text": "beta"},
    ]
    with open(phase1 / 'chunks.jsonl', 'w', encoding='utf-8') as f:
        for c in chunks:
            f.write(json.dumps(c) + '\n')
    # events.jsonl
    with open(phase1 / 'events.jsonl', 'w', encoding='utf-8') as f:
        for c in chunks:
            f.write(json.dumps({"doc_id": c['doc_id'], "status": "ingested"}) + '\n')
    # manifest.jsonl with platform dependent path examples
    with open(phase1 / 'manifest.jsonl', 'w', encoding='utf-8') as f:
        f.write(json.dumps({"doc_id": 10, "path": "C:/Data/alpha.txt"}) + '\n')
        f.write(json.dumps({"doc_id": 11, "path": "C:/Data/beta.txt"}) + '\n')
    return phase1


def test_hash_embedder_sanitization(tmp_path):
    # Build scenario ensuring deterministic output and metric presence
    phase1 = _make_minimal_phase1(tmp_path)
    artifacts_dir = tmp_path
    config = {
        'paths': {
            'artifacts_phase1': str(phase1),
            'artifacts_phase2': str(tmp_path / 'phase2')
        }
    }
    metrics = build_hash_embeddings(config)
    assert 'non_finite_replacements' in metrics
    assert 'total_vectors' in metrics
    # Validate embedding file structure
    # Dynamic naming now: default slug localhash-8d-v1
    emb_file = Path(config['paths']['artifacts_phase2']) / 'embeddings.localhash-8d-v1.jsonl'
    assert emb_file.exists()
    with open(emb_file, 'r', encoding='utf-8') as f:
        for line in f:
            rec = json.loads(line)
            assert len(rec['vector']) == 8
            assert all(math.isfinite(v) for v in rec['vector'])


def test_provenance_canonical_paths(tmp_path):
    phase1 = _make_minimal_phase1(tmp_path)
    config = {
        'paths': {
            'artifacts_phase1': str(phase1),
            'artifacts_phase2': str(tmp_path / 'phase2')
        }
    }
    build_provenance(config)
    prov_file = Path(config['paths']['artifacts_phase2']) / 'provenance.jsonl'
    assert prov_file.exists()
    with open(prov_file, 'r', encoding='utf-8') as f:
        rows = [json.loads(l) for l in f]
    # Ensure canonical forward slashes
    assert all('/' in r['source_doc_path'] for r in rows)
    # Ensure mapping correctness
    assert {r['doc_id'] for r in rows} == {10, 11}

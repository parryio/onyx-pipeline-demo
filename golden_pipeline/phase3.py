"""Phase 3 Orchestrator (Offline)

Consumes the deterministic enrichment cache produced by `onyx enrich phase3`.
No network calls are made here. All outputs are derived purely from:
  - artifacts/phase1/*.jsonl
  - datasets/phase3/enrichment_cache.jsonl

Artifacts produced:
  - artifacts/phase3/doc_metadata.jsonl
  - artifacts/phase3/entities.jsonl
  - artifacts/phase3/metrics_phase3.json

"""
from __future__ import annotations
import json, hashlib, os
from pathlib import Path
from typing import Dict, Any, List
from . import cache_manager as cache_mod
from . import doc_metadata_parser
from . import entity_parser  # lexicon-driven entity parsing
from .phase3_gate import verify_phase3_artifacts, GateError
from . import ritual_step_parser


def run_phase3(config: Dict[str, Any]) -> None:
    artifacts_dir = Path(config.get('artifacts_dir', 'artifacts'))
    phase1_dir = artifacts_dir / 'phase1'
    phase3_dir = artifacts_dir / 'phase3'
    phase3_dir.mkdir(parents=True, exist_ok=True)
    # Resolve enrichment cache path from config if available
    cfg_phase3 = (config.get('phase3') or {})
    cache_path = Path(cfg_phase3.get('enrichment_cache', 'datasets/phase3/enrichment_cache.jsonl'))
    cache_synthesized = False
    if not cache_path.exists():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text('', encoding='utf-8')
        cache_synthesized = True

    cache_items = cache_mod.read_cache(cache_path)
    cache_empty = len(cache_items) == 0

    # 1. Doc metadata
    manifest_path = phase1_dir / 'manifest.jsonl'
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    doc_metadata_out = phase3_dir / 'doc_metadata.jsonl'
    doc_metadata_records = doc_metadata_parser.build_doc_metadata(manifest_path)
    _write_jsonl(doc_metadata_out, doc_metadata_records)

    # 2. Entities
    chunks_path = phase1_dir / 'chunks.jsonl'
    if not chunks_path.exists():
        raise FileNotFoundError(chunks_path)
    entities_out = phase3_dir / 'entities.jsonl'
    # Resolve lexicon directory
    lex_dir = None
    lex_path_cfg = (config.get('paths') or {}).get('lexicons')
    if lex_path_cfg:
        lex_dir = Path(lex_path_cfg)
    entities = entity_parser.build_entities(chunks_path, cache_items, lexicon_dir=lex_dir)
    _write_jsonl(entities_out, entities)

    # 3. Ritual Steps
    ritual_steps_out = phase3_dir / 'ritual_steps.jsonl'
    lex_dir = None
    lex_path_cfg = (config.get('paths') or {}).get('lexicons')
    if lex_path_cfg:
        lex_dir = Path(lex_path_cfg)
    else:
        lex_dir = Path('lexicons')
    actions_lexicon = lex_dir / 'ritual_actions.yaml'
    try:
        if actions_lexicon.exists():
            steps = ritual_step_parser.extract_ritual_steps(phase1_dir / 'chunks.jsonl', actions_lexicon)
            ritual_step_parser.write_ritual_steps(ritual_steps_out, steps)
        else:
            steps = []
    except Exception as e:
        print(f"[WARN] Ritual step extraction failed: {e}")
        steps = []

    # 4. Metrics (incl cache digest pin)
    metrics_path = phase3_dir / 'metrics_phase3.json'
    digest = _file_sha256(cache_path)
    metrics = {
        'enrichment_cache_path': str(cache_path),
        'enrichment_cache_digest': digest,
        'enrichment_cache_empty': cache_empty,
        'entity_count': len(entities),
        'doc_count': len(doc_metadata_records),
        'ritual_step_count': len(steps)
    }
    if cache_synthesized:
        metrics['enrichment_cache_synthesized'] = True
    metrics_path.write_text(json.dumps(metrics, sort_keys=True, indent=2))

    # 5. Gate
    try:
        verify_phase3_artifacts(artifacts_dir, config_path=config.get('config_path','config/onyx.yml'))
    except GateError:
        raise


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]):
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + '\n')

def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

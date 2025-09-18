from pathlib import Path
from typing import Dict, Any

from .manifest_builder import build_manifest
from .document_processor import process_documents

def run_phase1(config: Dict[str, Any]):
    print("Running Phase 1: Ingest")
    library_root = Path(config['root'])
    artifacts_dir = Path(config['artifacts_dir'])
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    phase1_dir = artifacts_dir / 'phase1'
    phase1_dir.mkdir(parents=True, exist_ok=True)

    patterns = config.get('pattern', ['**/*.txt'])
    manifest = build_manifest(library_root, patterns)
    # Optional max documents limiter for large libraries (quick iteration mode)
    max_docs = (config.get('phase1', {}) or {}).get('max_documents')
    import os as _os
    env_override = _os.environ.get('ONYX_PHASE1_MAX_DOCS')
    if env_override:
        try:
            max_docs = int(env_override)
        except ValueError:
            pass
    if isinstance(max_docs, int) and max_docs > 0 and len(manifest) > max_docs:
        print(f"[phase1] limiting documents {max_docs} of {len(manifest)} (max_documents)")
        manifest = manifest[:max_docs]
    chunks, events, quarantine, media_assets, qa_report = process_documents(library_root, manifest, config)

    # Sorting & integrity (canonical ordering)
    manifest.sort(key=lambda x: x['doc_id'])
    chunks.sort(key=lambda x: x['chunk_id'])
    events.sort(key=lambda x: x['doc_id'])
    quarantine.sort(key=lambda x: x['doc_id'])
    media_assets.sort(key=lambda x: x.get('asset_id', ''))

    write_jsonl(phase1_dir / 'manifest.jsonl', [{k: v for k, v in m.items() if k != 'ext'} for m in manifest])
    write_jsonl(phase1_dir / 'chunks.jsonl', chunks)
    write_jsonl(phase1_dir / 'events.jsonl', events)
    write_jsonl(phase1_dir / 'quarantine.jsonl', quarantine)
    # Always write media_assets.jsonl (may be empty list) to satisfy PDR contract.
    write_jsonl(phase1_dir / 'media_assets.jsonl', media_assets)
    # Optional metrics and QA report
    aux_cfg = (config.get('auxiliary') or {})
    if aux_cfg.get('phase1_metrics') is True:
        metrics = {
            'documents_total': len(manifest),
            'chunks_total': len(chunks),
            'events_total': len(events),
            'quarantine_total': len(quarantine),
            'media_assets_total': len(media_assets),
            'by_event_status': _count_by(events, 'status'),
            'by_extension': _ext_summary(manifest)
        }
        import json as _json
        with open(phase1_dir / 'metrics.json', 'w', encoding='utf-8', newline='\n') as mf:
            _json.dump(metrics, mf, sort_keys=True, indent=2)
    if aux_cfg.get('phase1_qa_report') is True and qa_report:
        write_jsonl(phase1_dir / 'qa_report.jsonl', qa_report)
    print(f"Phase 1 complete. Artifacts written to {phase1_dir}")

def write_jsonl(path, data):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for item in data:
            f.write(__import__('json').dumps(item, sort_keys=True) + '\n')

def _count_by(rows, key):
    out = {}
    for r in rows:
        v = r.get(key)
        out[v] = out.get(v, 0) + 1
    return out

def _ext_summary(manifest):
    out = {}
    for m in manifest:
        # Use only the final suffix (robust extension handling per PDR patch)
        p = m['path']
        ext = Path(p).suffix.lower()
        out[ext] = out.get(ext, 0) + 1
    return out

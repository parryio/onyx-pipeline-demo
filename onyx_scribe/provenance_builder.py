import json
from pathlib import Path

def build_provenance(config):
    """
    Builds a detailed provenance manifest by linking chunks to their ingestion events.
    """
    print("Building provenance manifest...")
    phase1_dir = Path(config['paths']['artifacts_phase1'])
    phase2_dir = Path(config['paths']['artifacts_phase2'])
    phase2_dir.mkdir(exist_ok=True)

    chunks_path = phase1_dir / "chunks.jsonl"
    events_path = phase1_dir / "events.jsonl"
    manifest_path = phase1_dir / "manifest.jsonl"

    if not chunks_path.exists() or not events_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Phase 1 artifacts (chunks/events/manifest) not found at {phase1_dir}. Run Phase 1 first.")

    with open(chunks_path, 'r', encoding='utf-8') as f:
        chunks = [json.loads(line) for line in f]

    with open(events_path, 'r', encoding='utf-8') as f:
        events = {e['doc_id']: e for e in (json.loads(line) for line in f)}

    # Load manifest for authoritative source path mapping (PDR Provenance fidelity)
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest_paths = {m['doc_id']: m.get('path', 'unknown') for m in (json.loads(line) for line in f)}

    provenance = []
    missing_paths = 0
    for chunk in chunks:
        doc_id = chunk['doc_id']
        event = events.get(doc_id, {})
        source_path = manifest_paths.get(doc_id) or event.get('source_path') or 'unknown'
        if source_path == 'unknown':
            missing_paths += 1
        # Canonicalize path for deterministic cross-platform artifact parity
        canonical_path = Path(source_path).as_posix() if source_path != 'unknown' else 'unknown'
        provenance.append({
            "chunk_id": chunk['chunk_id'],
            "doc_id": doc_id,
            "source_doc_path": canonical_path,
            "ingestion_method": event.get('status', 'unknown')
        })
    
    # Sort by chunk_id to ensure deterministic order
    provenance.sort(key=lambda x: x['chunk_id'])

    provenance_path = phase2_dir / "provenance.jsonl"
    with open(provenance_path, 'w', encoding='utf-8', newline='\n') as f:
        for item in provenance:
            f.write(json.dumps(item, sort_keys=True) + '\n')

    print(f"Provenance manifest written to {provenance_path}")
    if missing_paths:
        print(f"[WARN] {missing_paths} provenance rows still have unknown source_doc_path (should be 0).")
    else:
        print("[TRACEABILITY] All provenance rows have resolved source_doc_path.")

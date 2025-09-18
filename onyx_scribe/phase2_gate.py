import json
from pathlib import Path
import jsonschema
import math

def validate_jsonl_schema(file_path, schema_path):
    """Validates each line of a JSONL file against a schema."""
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            try:
                instance = json.loads(line)
                jsonschema.validate(instance=instance, schema=schema)
            except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                raise ValueError(f"Validation failed in {file_path} on line {i}: {e}")

def run_phase2_gate(config):
    """
    Validates the artifacts produced by Phase 2 for schema conformance,
    integrity, and PDR compliance.
    """
    print("Running Phase 2 Gate...")
    phase1_dir = Path(config['paths']['artifacts_phase1'])
    phase2_dir = Path(config['paths']['artifacts_phase2'])
    schemas_dir = Path(config['paths']['schemas'])

    # 1. Check for required files
    # Resolve dynamic embeddings filename from config
    slug = (
        config.get('phase2', {})
              .get('embeddings', {})
              .get('model_slug', 'localhash-8d-v1')
    )
    embeddings_filename = f"embeddings.{slug}.jsonl"
    required_files = {
        "bm25.index": phase2_dir / "search" / "bm25.index",
        embeddings_filename: phase2_dir / embeddings_filename,
        "entity_index.jsonl": phase2_dir / "entity_index.jsonl",
        "provenance.jsonl": phase2_dir / "provenance.jsonl"
    }
    for name, f in required_files.items():
        if not f.exists():
            raise FileNotFoundError(f"Required artifact not found: {f}")
        print(f"[OK] Found artifact: {name}")

    # Exact artifact set rule for embeddings.*.jsonl (PDR 3.1.0):
    # There must be exactly one embeddings artifact and it MUST be the dynamic filename.
    embedding_candidates = list(phase2_dir.glob("embeddings.*.jsonl"))
    if len(embedding_candidates) != 1:
        names = [p.name for p in embedding_candidates]
        raise ValueError(
            "Embedding artifact set violation: expected exactly 1 file '" +
            f"{embeddings_filename}' but found {len(embedding_candidates)} -> {names}. "
            "Remove legacy or extraneous embeddings.* artifacts (e.g. embeddings.hash.jsonl)."
        )
    if embedding_candidates[0].name != embeddings_filename:
        raise ValueError(
            f"Embedding artifact name mismatch: expected '{embeddings_filename}' got '{embedding_candidates[0].name}'. "
            "Rename/remove incorrect file to comply with PDR naming contract."
        )
    print(f"[OK] Exact artifact set enforced for embeddings: {embeddings_filename}")

    # 2. Load chunk and entity data for cross-validation
    with open(phase1_dir / "chunks.jsonl", 'r', encoding='utf-8') as f:
        chunks = [json.loads(line) for line in f]
        chunk_ids = {c['chunk_id'] for c in chunks}
    
    with open(required_files[embeddings_filename], 'r', encoding='utf-8') as f:
        embeddings = [json.loads(line) for line in f]

    with open(required_files["provenance.jsonl"], 'r', encoding='utf-8') as f:
        provenance = [json.loads(line) for line in f]

    # 3. PDR Checks
    # Parity checks
    if len(embeddings) != len(chunks):
        raise ValueError("Parity failed: Embeddings count does not match chunks count.")
    print("[OK] Parity check: Embeddings and chunks count match.")
    
    if len(provenance) != len(chunks):
        raise ValueError("Parity failed: Provenance count does not match chunks count.")
    print("[OK] Parity check: Provenance and chunks count match.")

    # Embedding dimensionality & finite value integrity (BLOCKER 1 guard)
    non_finite = 0
    for emb in embeddings:
        vec = emb.get('vector', [])
        if len(vec) != 8:
            raise ValueError(f"Embedding dimensionality error for {emb['chunk_id']}: expected 8, got {len(vec)}.")
        for v in vec:
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                non_finite += 1
    if non_finite:
        raise ValueError(f"Embedding integrity failure: {non_finite} non-finite values encountered (NaN/Inf disallowed).")
    print("[OK] Embedding dimensionality & finiteness check passed (all 8D & finite).")

    # Entity Traceability
    with open(required_files["entity_index.jsonl"], 'r', encoding='utf-8') as f:
        for line in f:
            entity = json.loads(line)
            if entity['source_chunk_id'] not in chunk_ids:
                raise ValueError(f"Entity traceability error: Entity '{entity['entity_text']}' references non-existent chunk_id '{entity['source_chunk_id']}'.")
    print("[OK] Entity traceability check passed.")

    # Provenance traceability (BLOCKER 2 guard)
    unknown_paths = [p for p in provenance if p.get('source_doc_path') in (None, '', 'unknown')]
    if unknown_paths:
        sample = unknown_paths[:3]
        raise ValueError(f"Provenance fidelity failure: {len(unknown_paths)} rows have source_doc_path=unknown (e.g. chunk_id(s) {[r['chunk_id'] for r in sample]})")
    print("[OK] Provenance source_doc_path resolved for all rows.")

    # 4. Schema Conformance (now enforced)
    embeddings_schema = schemas_dir / 'phase2_embeddings.schema.json'
    provenance_schema = schemas_dir / 'phase2_provenance.schema.json'
    entity_schema = schemas_dir / 'phase2_entity_index.schema.json'
    missing = [p.name for p in [embeddings_schema, provenance_schema, entity_schema] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Phase 2 schemas missing: {', '.join(missing)}")

    validate_jsonl_schema(required_files[embeddings_filename], embeddings_schema)
    validate_jsonl_schema(required_files["provenance.jsonl"], provenance_schema)
    validate_jsonl_schema(required_files["entity_index.jsonl"], entity_schema)
    print(f"[OK] Schema validation: {embeddings_filename}, provenance.jsonl, entity_index.jsonl conform to schemas.")

    # 5. Strict finite-value enforcement (no thresholds)
    bad_vectors = 0
    with open(required_files[embeddings_filename], 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            rec = json.loads(line)
            vec = rec.get('vector', [])
            if any((not isinstance(v, (int, float))) or (not math.isfinite(v)) for v in vec):
                bad_vectors += 1
                if bad_vectors <= 3:
                    print(f"[FAIL] Non-finite or invalid scalar in embedding line {i} (chunk_id={rec.get('chunk_id')})", flush=True)
    if bad_vectors:
        raise ValueError(f"Embedding integrity hard failure: {bad_vectors} vector(s) contained non-finite/invalid values.")
    print("[OK] All embedding vectors finite & valid.")

    # 6. Auxiliary artifact policy enforcement
    aux_flag = config.get('auxiliary', {}).get('phase2_metrics', False)
    metrics_candidate = phase2_dir / 'metrics_phase2.json'
    if aux_flag:
        if not metrics_candidate.exists():
            raise FileNotFoundError("Config auxiliary.phase2_metrics=true but metrics_phase2.json missing.")
    else:
        if metrics_candidate.exists():
            raise ValueError("metrics_phase2.json present but auxiliary.phase2_metrics flag is false.")
    print("[OK] Auxiliary artifact policy respected.")

    print("\nPhase 2 Gate: All checks passed successfully.")

if __name__ == '__main__':
    # Example of how to run this from a script if needed
    # with open('config/onyx.yml', 'r') as f:
    #     config = yaml.safe_load(f)
    # run_phase2_gate(config)
    pass

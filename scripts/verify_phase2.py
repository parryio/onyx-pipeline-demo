import hashlib
import json
import sys
from pathlib import Path
import jsonschema
import yaml

def _load_config(path: str = 'config/onyx.yml'):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}

def _calculate_sha256(filepath):
    """Calculates the SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def verify_phase2(artifacts_dir, config_path: str = 'config/onyx.yml'):
    print("Verifying Phase 2 artifacts...")
    phase1_dir = Path(artifacts_dir) / "phase1"
    phase2_dir = Path(artifacts_dir) / "phase2"
    cfg = _load_config(config_path)
    slug = (
        cfg.get('phase2', {})
           .get('embeddings', {})
           .get('model_slug', 'localhash-8d-v1')
    )
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9._\-]+", slug):
        print(f"  [FAIL] Invalid model_slug in config: {slug}", file=sys.stderr)
        sys.exit(1)
    embeddings_filename = f"embeddings.{slug}.jsonl"
    schemas_dir = Path("tools/schemas")

    # Schemas
    embeddings_schema_path = schemas_dir / "phase2_embeddings.schema.json"
    if not embeddings_schema_path.exists():
        print(f"  [FAIL] Missing schema file: {embeddings_schema_path}", file=sys.stderr)
        sys.exit(1)
    embeddings_schema = json.loads(embeddings_schema_path.read_text())

    # Artifacts
    chunks_path = phase1_dir / "chunks.jsonl"
    embeddings_path = phase2_dir / embeddings_filename
    bm25_path = phase2_dir / "search" / "bm25.index"
    bm25_digest_path = bm25_path.with_suffix('.index.sha256')

    errors = []

    # 1. Check for existence
    if not chunks_path.exists(): errors.append(f"Missing dependency: {chunks_path}")
    if not embeddings_path.exists(): errors.append(f"Missing artifact: {embeddings_path}")
    if not bm25_path.exists(): errors.append(f"Missing artifact: {bm25_path}")

    if errors:
        for error in errors: print(f"  [FAIL] {error}", file=sys.stderr)
        sys.exit(1)

    # 2. Schema validation and ordering for embeddings
    embeddings_data = validate_jsonl(embeddings_path, embeddings_schema, "chunk_id", errors)

    # 3. 1:1 Row Parity with chunks.jsonl
    with open(chunks_path, 'r', encoding='utf-8') as f:
        chunk_ids = [json.loads(line)['chunk_id'] for line in f]
    
    embedding_chunk_ids = [item['chunk_id'] for item in embeddings_data]

    if len(chunk_ids) != len(embedding_chunk_ids):
        errors.append(f"Parity Error: Mismatch in row count between chunks.jsonl ({len(chunk_ids)}) and {embeddings_filename} ({len(embedding_chunk_ids)}).")
    
    if chunk_ids != embedding_chunk_ids:
        errors.append(f"Parity Error: chunk_ids in {embeddings_filename} do not match or are not in the same order as in chunks.jsonl.")

    # 4. Determinism check for bm25.index
    # This is the PDR-compliant check. It treats the file as opaque bytes.
    current_digest = _calculate_sha256(bm25_path)
    if bm25_digest_path.exists():
        expected_digest = bm25_digest_path.read_text().strip()
        if current_digest != expected_digest:
            errors.append(f"Determinism Fail: {bm25_path} has changed. Expected SHA256: {expected_digest}, got: {current_digest}")
        else:
            print(f"  [INFO] Determinism check passed for {bm25_path}.")
    else:
        # If the digest doesn't exist, we create it for the next run.
        # This is the "first run" or "update" scenario.
        print(f"  [INFO] Digest file not found. Creating {bm25_digest_path} for future determinism checks.")
        bm25_digest_path.write_text(current_digest)

    if errors:
        for error in errors:
            print(f"  [FAIL] {error}", file=sys.stderr)
        sys.exit(1)

    print("  [PASS] Phase 2 verification successful.")

def validate_jsonl(path, schema, sort_key, errors):
    data = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                errors.append(f"Validation Error: {path} is empty.")
                return []
            for i, line in enumerate(lines):
                try:
                    item = json.loads(line)
                    jsonschema.validate(instance=item, schema=schema)
                    data.append(item)
                except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                    errors.append(f"Schema validation failed for {path} at line {i+1}: {e}")
        
        if data and [item[sort_key] for item in data] != sorted([item[sort_key] for item in data]):
            errors.append(f"Ordering Error: {path} is not sorted by '{sort_key}'.")
    except FileNotFoundError:
        errors.append(f"File not found: {path}")
    except Exception as e:
        errors.append(f"An unexpected error occurred while validating {path}: {e}")
        
    return data

if __name__ == "__main__":
    artifacts_root = "artifacts"
    config_path = 'config/onyx.yml'
    if len(sys.argv) > 1:
        artifacts_root = sys.argv[1]
    if len(sys.argv) > 2:
        config_path = sys.argv[2]
    
    verify_phase2(artifacts_root, config_path)

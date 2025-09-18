import os
from pathlib import Path
import yaml
from onyx_scribe.phase2_gate import run_phase2_gate
from onyx_scribe.hash_embedder import build_hash_embeddings
from pathlib import Path

def load_config(path: str = 'config/onyx.yml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def cleanup_legacy_embeddings(config_path: str = 'config/onyx.yml'):
    cfg = load_config(config_path)
    # Reconstruct paths map similar to phase2._ensure_paths
    artifacts_dir = Path(cfg['artifacts_dir']).resolve()
    paths = cfg.setdefault('paths', {})
    paths.setdefault('artifacts_phase1', str(artifacts_dir / 'phase1'))
    paths.setdefault('artifacts_phase2', str(artifacts_dir / 'phase2'))
    schemas_root = cfg.get('schemas_dir') or 'tools/schemas'
    paths.setdefault('schemas', str(Path(schemas_root)))
    phase2_dir = Path(paths['artifacts_phase2'])
    legacy = phase2_dir / 'embeddings.hash.jsonl'
    if legacy.exists():
        print(f"Removing legacy artifact: {legacy}")
        legacy.unlink()
    else:
        print("No legacy embeddings.hash.jsonl present.")
    # Rebuild embeddings to ensure current slug artifact exists
    build_hash_embeddings(cfg)
    run_phase2_gate(cfg)

if __name__ == '__main__':
    cleanup_legacy_embeddings()

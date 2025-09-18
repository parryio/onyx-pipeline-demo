from pathlib import Path
from .entity_recognizer import recognize_entities
from .hash_embedder import build_hash_embeddings
from .provenance_builder import build_provenance
from .search_indexer import build_search_index
from .phase2_gate import run_phase2_gate


def _ensure_paths(config):
    """Augment config with derived path map required by Phase 2 components (PDR compliance)."""
    artifacts_dir = Path(config['artifacts_dir']).resolve()
    paths = config.setdefault('paths', {})
    paths.setdefault('artifacts_phase1', str(artifacts_dir / 'phase1'))
    paths.setdefault('artifacts_phase2', str(artifacts_dir / 'phase2'))
    # Schemas directory (allow override via config['schemas_dir'])
    schemas_root = config.get('schemas_dir') or 'tools/schemas'
    paths.setdefault('schemas', str(Path(schemas_root)))
    # Ensure directories exist
    Path(paths['artifacts_phase2']).mkdir(parents=True, exist_ok=True)
    (Path(paths['artifacts_phase2']) / 'search').mkdir(exist_ok=True)
    return config


def run_phase2(config):
    """
    Orchestrate Phase 2: search index, hash embeddings, entity index, provenance + gate.
        Conforms to PDR artifact contract:
            artifacts/phase2/
                search/bm25.index
                embeddings.<model_slug>.jsonl  (e.g., embeddings.localhash-8d-v1.jsonl based on config.phase2.embeddings.model_slug)
                entity_index.jsonl
                provenance.jsonl
    """
    config = _ensure_paths(config)
    print("Running Phase 2: Index, Enrich & Provenance")

    # Ordered execution per PDR
    build_search_index(config)
    emb_metrics = build_hash_embeddings(config)
    recognize_entities(config)
    build_provenance(config)

    # Optional metrics persistence
    if config.get('auxiliary', {}).get('phase2_metrics'):
        metrics_path = Path(config['paths']['artifacts_phase2']) / 'metrics_phase2.json'
        payload = {
            "embedding_non_finite_replacements": emb_metrics.get('non_finite_replacements'),
            "embedding_vectors_sanitized": emb_metrics.get('sanitized_vectors'),
            "embedding_total_vectors": emb_metrics.get('total_vectors')
        }
        with open(metrics_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(payload, f, indent=2, sort_keys=True)
        print(f"Phase 2 metrics written to {metrics_path}")

    print("\nPhase 2 artifact generation complete. Running gate...")
    run_phase2_gate(config)
    print("\nPhase 2 completed successfully.")


# Note: No standalone CLI here; invoked via argparse-driven main in cli.py
# (run_phase2 is imported and executed with loaded config)

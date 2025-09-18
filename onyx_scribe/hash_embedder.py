import hashlib
import json
import math
from pathlib import Path
from typing import List
from .text_cleaner import clean_text

def build_hash_embeddings(config):
    """
    Generates 8-dimensional hash-based embeddings from Phase 1 chunks.
    """
    print("Building hash embeddings...")
    phase1_dir = Path(config['paths']['artifacts_phase1'])
    phase2_dir = Path(config['paths']['artifacts_phase2'])
    phase2_dir.mkdir(exist_ok=True)

    chunks_path = phase1_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"{chunks_path} not found. Run Phase 1 first.")
    
    with open(chunks_path, 'r', encoding='utf-8') as f:
        chunks = [json.loads(line) for line in f]

    embeddings = []
    non_finite_replacements = 0  # scalar-level replacements
    sanitized_vectors = 0        # count of vectors that had at least one replacement
    def _hash_bytes(data: bytes) -> bytes:
        return hashlib.sha256(data).digest()

    def _vector_from_digest(digest: bytes) -> List[float]:
        # Produce 8 deterministic sub-hash integers -> map to float in [-1,1]
        vec: List[float] = []
        for i in range(8):
            # 4 bytes per component
            start = i * 4
            part = digest[start:start+4]
            val = int.from_bytes(part, 'big', signed=False)
            # map to [0,1) then shift to [-1,1)
            comp = (val / 0xFFFFFFFF) * 2.0 - 1.0
            vec.append(comp)
        return vec

    def _safe_l2_normalize(vec: List[float], eps: float = 1e-12) -> List[float]:
        norm_sq = sum(v * v for v in vec)
        if norm_sq <= eps:
            return [0.0] * len(vec)
        inv = 1.0 / math.sqrt(norm_sq)
        return [v * inv for v in vec]

    for chunk in chunks:
        raw_text = chunk.get('text', '')
        cleaned = clean_text(raw_text)
        digest = _hash_bytes(cleaned.encode('utf-8'))
        base_vec = _vector_from_digest(digest)
        norm_vec = _safe_l2_normalize(base_vec)
        vector_sanitized = False
        safe_vec: List[float] = []
        for v in norm_vec:
            if not math.isfinite(v):
                non_finite_replacements += 1
                vector_sanitized = True
                safe_vec.append(0.0)
            else:
                safe_vec.append(v)
        if vector_sanitized:
            sanitized_vectors += 1
        embeddings.append({
            "chunk_id": chunk['chunk_id'],
            "doc_id": chunk['doc_id'],
            "vector": safe_vec
        })

    # Sort by chunk_id to ensure deterministic order and 1:1 alignment with chunks.jsonl
    embeddings.sort(key=lambda x: x['chunk_id'])

    # Dynamic artifact naming per PDR: embeddings.<model_slug>.jsonl
    slug = (
        config.get('phase2', {})
              .get('embeddings', {})
              .get('model_slug', 'localhash-8d-v1')
    )
    # basic safety: file-safe slug (alnum, dash, underscore, dot allowed)
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9._\-]+", slug):
        raise ValueError(f"Invalid model_slug for embeddings filename: {slug}")
    embeddings_path = phase2_dir / f"embeddings.{slug}.jsonl"
    with open(embeddings_path, 'w', encoding='utf-8', newline='\n') as f:
        for item in embeddings:
            f.write(json.dumps(item, sort_keys=True) + '\n')

    print(f"Hash embeddings written to {embeddings_path}")
    if non_finite_replacements:
        print(f"[SANITIZE] Hard guard replaced {non_finite_replacements} scalar(s) with 0.0 (should be 0 post-hardening).")
    else:
        print("[SANITIZE] No non-finite values (source stable).")
    # Expose metric for downstream gate / metrics writer
    return {
        "non_finite_replacements": non_finite_replacements,
        "sanitized_vectors": sanitized_vectors,
        "total_vectors": len(embeddings)
    }

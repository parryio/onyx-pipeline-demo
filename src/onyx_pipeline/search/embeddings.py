from __future__ import annotations

from pathlib import Path

import numpy as np

from ..storage.atomic import atomic_write_bytes, atomic_write_json

EMB_DIM = 8192


def build_embeddings(chunks: list[dict], emb_npy: Path, rowmap_path: Path, *, seed: int = 13) -> None:
    rng = np.random.default_rng(seed)
    if chunks:
        arr = rng.standard_normal((len(chunks), EMB_DIM), dtype=np.float32)
    else:
        arr = np.zeros((0, EMB_DIM), dtype=np.float32)
    emb_npy.parent.mkdir(parents=True, exist_ok=True)
    # Write .npy manually for simplicity (use numpy.save semantics)
    import io
    bio = io.BytesIO()
    np.save(bio, arr)
    atomic_write_bytes(emb_npy, bio.getvalue())
    rowmap = {i: c["chunk_id"] for i, c in enumerate(chunks)}
    atomic_write_json(rowmap_path, rowmap)

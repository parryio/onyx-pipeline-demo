from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

__all__ = ["streaming_sha256"]
PREFIX: Final = "sha256:"
BUF_SIZE: Final = 1024 * 1024  # 1 MiB


def streaming_sha256(p: Path, chunk_size: int = BUF_SIZE) -> str:
    """Compute a tagged streaming sha256 of a file.

    Returns 'sha256:<hex>'. Reads in fixed-size chunks (default 1 MiB).
    """
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            if not chunk:
                break
            h.update(chunk)
    return PREFIX + h.hexdigest()

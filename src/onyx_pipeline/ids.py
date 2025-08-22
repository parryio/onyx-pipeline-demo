from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Final

__all__ = ["doc_id_from_hash", "hash_bytes_tagged", "doc_dirname_from_path"]

PREFIX: Final = "sha256:"
_INVALID_DIR_CHARS = re.compile(r"[^a-zA-Z0-9_.-]+")


def doc_id_from_hash(h: str) -> str:
    """Return the 64 hex characters of a tagged sha256 hash.

    Input must be of the form 'sha256:<64hex>'. Extra characters after the 64 hex are ignored.
    """
    if not h.startswith(PREFIX) or len(h) < len(PREFIX) + 64:
        raise ValueError(f"Invalid tagged hash: {h}")
    core = h[len(PREFIX): len(PREFIX) + 64]
    if not re.fullmatch(r"[0-9a-f]{64}", core):
        raise ValueError("Hash hex portion invalid")
    return core


def hash_bytes_tagged(data: bytes) -> str:
    return PREFIX + sha256(data).hexdigest()


def doc_dirname_from_path(p: str | Path) -> str:
    """Derive deterministic directory name from a file path stem.

    Sanitizes to [a-zA-Z0-9_.-]; replaces sequences of invalid chars with '_'.
    Empty result becomes 'doc'.
    """
    stem = Path(p).stem if not isinstance(p, Path) else p.stem
    cleaned = _INVALID_DIR_CHARS.sub("_", stem)
    return cleaned or "doc"

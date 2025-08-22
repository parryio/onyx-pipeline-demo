from __future__ import annotations

from collections.abc import Sequence

CHUNK_SCHEMA_VERSION = 2
VERSION = f"v{CHUNK_SCHEMA_VERSION}"
REQUIRED_FIELDS: Sequence[str] = ["doc_id", "chunk_id", "text", "order", "char_start", "char_end"]

__all__ = ["CHUNK_SCHEMA_VERSION", "VERSION", "REQUIRED_FIELDS"]

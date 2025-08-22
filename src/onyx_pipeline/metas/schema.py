from __future__ import annotations

from collections.abc import Sequence

METAS_SCHEMA_VERSION = 3
VERSION = f"v{METAS_SCHEMA_VERSION}"
REQUIRED_FIELDS: Sequence[str] = ["doc_id", "num_chunks", "file_hash"]

__all__ = ["METAS_SCHEMA_VERSION", "VERSION", "REQUIRED_FIELDS"]

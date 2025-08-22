from __future__ import annotations

from collections.abc import Sequence

MANIFEST_VERSION = 1
VERSION = f"v{MANIFEST_VERSION}"
REQUIRED_FIELDS: Sequence[str] = ["path", "file_hash", "size", "doc_type", "media_type"]

__all__ = ["MANIFEST_VERSION", "VERSION", "REQUIRED_FIELDS"]

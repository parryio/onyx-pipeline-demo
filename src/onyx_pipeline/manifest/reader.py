from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


def iter_manifest(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Lazy import to keep tight
            import json
            yield json.loads(line)

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..storage.atomic import atomic_write_lines


def write_metas_index(rows: Iterable[dict], dst: Path) -> Path:
    return atomic_write_lines(dst, (json_line(r) for r in rows))


def json_line(obj: dict) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)

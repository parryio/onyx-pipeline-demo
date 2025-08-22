from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

__all__ = ["atomic_write_text", "atomic_write_bytes", "atomic_write_json", "atomic_write_lines"]


def _temp_target(dst: Path) -> Path:
    return dst.with_suffix(dst.suffix + ".tmp")


def atomic_write_bytes(dst: Path, data: bytes) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_target(dst)
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dst)
    return dst


def atomic_write_text(dst: Path, text: str) -> Path:
    return atomic_write_bytes(dst, text.encode("utf-8"))


def atomic_write_json(dst: Path, obj: Any, *, ensure_ascii: bool = False, indent: int | None = None) -> Path:
    return atomic_write_text(dst, json.dumps(obj, ensure_ascii=ensure_ascii, indent=indent))


def atomic_write_lines(dst: Path, lines: Iterable[str]) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_target(dst)
    with open(tmp, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line.rstrip("\n") + "\n")
    os.replace(tmp, dst)
    return dst

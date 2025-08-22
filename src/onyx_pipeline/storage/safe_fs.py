from __future__ import annotations

import os
import re
from pathlib import Path

__all__ = ["safe_join", "normalize_long_path", "PathTraversalError"]


class PathTraversalError(ValueError):
    """Raised when an unsafe path construction is attempted."""


_RESERVED_WINDOWS = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
_INVALID_SEGMENT = re.compile(r"[\x00]")


def normalize_long_path(p: Path) -> Path:
    """On Windows, prepend \\?\ to paths > 240 chars to avoid MAX_PATH issues."""
    if os.name == "nt":
        s = str(p)
        if len(s) > 240 and not s.startswith('\\\\?\\'):
            return Path('\\\\?\\' + s)
    return p


def _validate_segments(parts: tuple[str, ...]) -> None:
    for seg in parts:
        if seg in ("", "."):
            continue
        if seg == "..":
            raise PathTraversalError("parent traversal detected")
        if os.name == "nt" and seg.upper() in _RESERVED_WINDOWS:
            raise PathTraversalError(f"reserved name: {seg}")
        if _INVALID_SEGMENT.search(seg):
            raise PathTraversalError("null byte in segment")
        if Path(seg).is_absolute():
            raise PathTraversalError("absolute segment not allowed")


def safe_join(root: Path, *parts: str) -> Path:
    """Join parts under root with strong safety guarantees.

    - Rejects '..' traversal
    - Rejects absolute segments
    - Rejects Windows reserved device names
    - Normalizes long paths on Windows
    """
    _validate_segments(parts)
    root_abs = root.resolve()
    candidate = root_abs.joinpath(*parts)
    try:
        candidate.relative_to(root_abs)
    except ValueError as e:
        raise PathTraversalError(str(candidate)) from e
    return normalize_long_path(candidate)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkRules:
    max_chars: int = 1200
    overlap: int = 100

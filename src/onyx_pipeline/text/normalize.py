from __future__ import annotations


def normalize_text(s: str) -> str:
    return " ".join(s.strip().split())

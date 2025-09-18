"""Lightweight stub of the pypdf module used for tests."""
from __future__ import annotations

class PdfReader:
    def __init__(self, path):
        self.path = path
        self.pages = []

from . import errors  # noqa: F401  (re-export for import side-effects)

__all__ = ['PdfReader']

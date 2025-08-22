from __future__ import annotations

from collections.abc import Iterable

from .rules import ChunkRules


def chunk_text(doc_id: str, pages: Iterable[str], rules: ChunkRules) -> list[dict]:
    text = "\n".join(pages)
    chunks: list[dict] = []
    max_chars = rules.max_chars
    overlap = rules.overlap
    start = 0
    order = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunk_text = text[start:end]
        chunk_id = f"{doc_id}-{order}"
        chunks.append({
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "order": order,
            "text": chunk_text,
            "char_start": start,
            "char_end": end,
        })
        if end == len(text):
            break
        start = end - overlap
        order += 1
    return chunks

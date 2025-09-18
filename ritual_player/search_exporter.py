#!/usr/bin/env python3
"""
Export a lightweight search bundle for the renderer.

Reads artifacts/phase5/ui_catalog.jsonl (kit-centric) and writes
artifacts/phase5/ui_search.minisearch.json with fields:
  {
    "schema": {"fields": [..], "storeFields": [..]},
    "docs": [{"id","title","text","n_steps","tags"}]
  }

Deterministic order; no stemming; simple tokenization left to MiniSearch.
"""
import argparse, json, pathlib
from typing import Iterable, Set


def _merge_tags(*sources: Iterable[str]) -> Set[str]:
    tags: Set[str] = set()
    for src in sources:
        if not src:
            continue
        iterable = [src] if isinstance(src, str) else src
        for item in iterable:
            if isinstance(item, str):
                normalized = item.strip()
                if normalized:
                    tags.add(normalized)
    return tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts", help="artifacts root")
    args = ap.parse_args()

    P5 = pathlib.Path(args.artifacts) / "phase5"
    CAT = P5 / "ui_catalog.jsonl"
    OUT = P5 / "ui_search.minisearch.json"

    docs = []
    if CAT.exists():
        with CAT.open("r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                row = json.loads(s)
                if row.get("kind") != "kit":
                    continue
                kit_tags = _merge_tags(row.get("tags"), row.get("keywords"))
                text_blobs = [row.get("title", ""), row.get("subtitle", "")]
                if kit_tags:
                    text_blobs.extend(sorted(kit_tags))
                aggregated_tags = set(kit_tags)
                for st in row.get("steps", []):
                    step_text = st.get("text") or st.get("matched_text") or ""
                    text_blobs.append(step_text)
                    for m in st.get("materials", []) or []:
                        text_blobs.append(m)
                    if st.get("notes"):
                        text_blobs.append(st["notes"])
                    step_tags = _merge_tags(st.get("tags"), st.get("keywords"))
                    if step_tags:
                        aggregated_tags.update(step_tags)
                        text_blobs.extend(sorted(step_tags))
                fulltext = " \n".join([t for t in text_blobs if t])
                docs.append({
                    "id": row["kit_id"],
                    "title": row.get("title", row["kit_id"]),
                    "tags": sorted(aggregated_tags),
                    "n_steps": row.get("n_steps", 0),
                    "text": fulltext,
                })

    bundle = {
        "schema": {"fields": ["title", "text", "tags"], "storeFields": ["title", "n_steps", "tags"]},
        "docs": docs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, sort_keys=True)
    print(f"[phase5] wrote search bundle ({len(docs)} docs) -> {OUT}")


if __name__ == "__main__":
    main()

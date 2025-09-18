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
                text_blobs = [row.get("title", ""), row.get("subtitle", "")]
                for st in row.get("steps", []):
                    text_blobs.append(st.get("text", ""))
                    for m in st.get("materials", []) or []:
                        text_blobs.append(m)
                    if st.get("notes"):
                        text_blobs.append(st["notes"])
                fulltext = " \n".join([t for t in text_blobs if t])
                docs.append({
                    "id": row["kit_id"],
                    "title": row.get("title", row["kit_id"]),
                    "tags": row.get("tags", []),
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

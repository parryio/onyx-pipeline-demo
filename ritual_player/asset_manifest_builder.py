#!/usr/bin/env python3
"""
Builds artifacts/phase5/assets_manifest.jsonl deterministically from Phase 1 media assets.

Input:
- artifacts/phase1/media_assets.jsonl

Output:
- artifacts/phase5/assets_manifest.jsonl
"""
import argparse, json, os
from pathlib import Path

def read_jsonl(p: Path):
    if not p.exists(): return []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def write_jsonl(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--assets-root", default="Library", help="base for relative paths in rel_path")
    args = ap.parse_args()

    media_assets_p = Path(args.artifacts, "phase1", "media_assets.jsonl")
    out_p = Path(args.artifacts, "phase5", "assets_manifest.jsonl")

    rows = []
    for rec in read_jsonl(media_assets_p):
        aid = rec.get("asset_id")
        did = rec.get("source_doc_id") or rec.get("doc_id")
        raw_path = rec.get("rel_path") or rec.get("path") or ""
        rel_path = raw_path.replace("\\", "/")
        media_type = rec.get("mime") or rec.get("media_type") or ""
        if not (aid and did): continue
        rows.append({
            "asset_id": aid,
            "source_doc_id": did,
            "rel_path": rel_path,
            "media_type": media_type
        })
    rows.sort(key=lambda r: (r["source_doc_id"], r["asset_id"]))
    write_jsonl(out_p, rows)
    print(f"Wrote {len(rows)} rows -> {out_p}")

if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    main()


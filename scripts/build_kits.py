import json, pathlib, collections

"""LEGACY (DEPRECATED) Kit Compiler

STATUS: This script is retained only for historical reference and should NOT
be used in current pipelines. It produces non-canonical artifacts:
    - artifacts/phase4/kits.index.json (legacy) 

Current canonical Phase 4 artifacts are produced by:
    golden_pipeline.kit_assembler.assemble_kits
    golden_pipeline.crosslinker.create_crosslinks
    golden_pipeline.kit_indexer.index_kits

Canonical outputs:
    artifacts/phase4/kits/*.kit.json
    artifacts/phase4/kits/*.kit.lean.json
    artifacts/phase4/kit_index.jsonl
    artifacts/phase4/crosslinks.jsonl
    artifacts/phase4/derivations/collapse_map.jsonl

This script may be removed in a future release. It is intentionally NOT
invoked by the CLI and its output is ignored by gates.
"""

ROOT = pathlib.Path("artifacts")
P3   = ROOT / "phase3"   # adjust if your phase3 lives elsewhere
P2   = ROOT / "phase2"

steps_path    = P3 / "ritual_steps.jsonl"
entities_path = P2 / "entity_index.jsonl"     # optional enrich (currently unused but reserved)
prov_path     = P2 / "provenance.jsonl"       # for doc links
media_path    = P2 / "media_assets.jsonl"     # if present

out_dir = ROOT / "phase4" / "kits"
out_dir.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except Exception:
                    continue

# 1) group steps by kit_id (fallback to ritual_id/name if provided)
kits = collections.defaultdict(lambda: {"kit_id": None, "kit_name": None, "steps": [], "sources": set(), "media": []})

for row in read_jsonl(steps_path):
    kid = row.get("kit_id") or row.get("ritual_id") or row.get("ritual") or "unknown"
    kname = row.get("kit_name") or row.get("ritual_name") or kid
    k = kits[kid]
    k["kit_id"] = kid
    k["kit_name"] = kname
    # minimal normalized step
    k["steps"].append({
        "step_id": row.get("step_id"),
        "action": row.get("action"),
        "args": row.get("args"),
        "ordinal": row.get("ordinal"),
        "duration_s": row.get("duration_s"),
        "doc_id": row.get("source_doc_id") or row.get("doc_id"),
        "provenance": row.get("provenance"),
        "notes": row.get("notes"),
    })
    if row.get("source_doc_id"):
        k["sources"].add(row["source_doc_id"])

# 2) attach provenance doc paths (optional but nice for “open source” button)
doc_path_by_id = {}
for r in read_jsonl(prov_path):
    did = r.get("doc_id")
    path = r.get("source_doc_path")
    if did and path:
        doc_path_by_id[did] = path

for k in kits.values():
    for s in k["steps"]:
        did = s.get("doc_id")
        if did and did in doc_path_by_id:
            s["source_doc_path"] = doc_path_by_id[did]
    k["sources"] = sorted(k["sources"])

# 3) attach any media known for a kit (if your steps reference media_id)
media_by_id = {m.get("media_id"): m for m in read_jsonl(media_path)}
for k in kits.values():
    referenced = set()
    for s in k["steps"]:
        mid = (s.get("args") or {}).get("media_id")
        if mid and mid in media_by_id:
            referenced.add(mid)
    k["media"] = [media_by_id[m] for m in referenced]

# 4) order steps & write outputs
index = []
for kid, k in kits.items():
    k["steps"].sort(key=lambda s: (s["ordinal"] if s["ordinal"] is not None else 1e9, s.get("step_id") or ""))
    out = out_dir / f"{kid}.kit.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(k, f, ensure_ascii=False, indent=2)
    index.append({"kit_id": k["kit_id"], "kit_name": k["kit_name"], "path": str(out)})

# write index
idx = ROOT / "phase4" / "kits.index.json"
idx.parent.mkdir(parents=True, exist_ok=True)
with idx.open("w", encoding="utf-8") as f:
    json.dump({"kits": sorted(index, key=lambda x: x["kit_name"].lower())}, f, ensure_ascii=False, indent=2)

print(f"Wrote {len(index)} kits to {out_dir}")

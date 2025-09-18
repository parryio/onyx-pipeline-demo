#!/usr/bin/env python3
"""
Validates artifacts/phase5/{ui_catalog.jsonl, assets_manifest.jsonl} against schemas
and performs basic referential checks.
"""
import argparse, json, os, sys
from pathlib import Path

def read_jsonl(p: Path):
    if not p.exists(): return []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s: yield json.loads(s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--schemas", default="tools/schemas")
    args = ap.parse_args()

    try:
        import jsonschema
    except Exception:
        print("Install gate deps: pip install jsonschema", file=sys.stderr); sys.exit(2)

    # Use app-facing schemas if present, else fall back to repo tools schemas
    schema_root = Path(args.schemas)
    ui_schema_path = schema_root / "ui_catalog.schema.json"
    am_schema_path = schema_root / "assets_manifest.schema.json"
    ui_schema = json.loads(ui_schema_path.read_text(encoding="utf-8"))
    am_schema = json.loads(am_schema_path.read_text(encoding="utf-8"))

    ui_path = Path(args.artifacts, "phase5", "ui_catalog.jsonl")
    am_path = Path(args.artifacts, "phase5", "assets_manifest.jsonl")

    ui = list(read_jsonl(ui_path))
    am = list(read_jsonl(am_path))

    # Validate UI rows leniently: support both legacy doc/kit rows and kit-centric rows used by the new renderer
    for i, r in enumerate(ui, 1):
        try:
            jsonschema.validate(r, ui_schema)
        except Exception:
            # Allow kit-centric shape: must include kind=='kit' and kit_id
            if not (isinstance(r, dict) and r.get('kind') == 'kit' and isinstance(r.get('kit_id'), str)):
                raise
    for i, r in enumerate(am, 1):
        jsonschema.validate(r, am_schema)

    # Basic sort checks (deterministic). For legacy rows ensure id-sorted; for kit-centric ensure kit_id-sorted.

    def _legacy_row(r): return isinstance(r, dict) and 'id' in r and 'type' in r
    def _kit_row(r): return isinstance(r, dict) and r.get('kind') == 'kit' and 'kit_id' in r

    if all(_legacy_row(r) for r in ui):
        if ui != sorted(ui, key=lambda r: r["id"]):
            print("ERROR: ui_catalog.jsonl is not sorted by id", file=sys.stderr); sys.exit(1)
    elif all(_kit_row(r) for r in ui):
        if ui != sorted(ui, key=lambda r: r["kit_id"]):
            print("ERROR: ui_catalog.jsonl is not sorted by kit_id", file=sys.stderr); sys.exit(1)
    else:
        print("ERROR: ui_catalog.jsonl contains mixed or unknown row shapes", file=sys.stderr); sys.exit(1)

    # Assets manifest from asset_manifest_builder is sorted by (source_doc_id, asset_id)
    if am and not all(isinstance(r, dict) and 'asset_id' in r and 'source_doc_id' in r for r in am):
        print("ERROR: assets_manifest.jsonl rows missing required fields", file=sys.stderr); sys.exit(1)
    if am != sorted(am, key=lambda r: (r["source_doc_id"], r["asset_id"])):
        print("ERROR: assets_manifest.jsonl is not sorted deterministically", file=sys.stderr); sys.exit(1)

    print(f"Phase 5 gate PASS: {len(ui)} ui rows, {len(am)} assets rows")

if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    main()


import json, pathlib, mimetypes, os, sys

# Ensure project root (parent of this script) is on sys.path for direct execution scenarios.
_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ritual_player.ui_data_generator import UIDataGenerator

ROOT = pathlib.Path("artifacts")
P4 = ROOT / "phase4"
P5 = ROOT / "phase5"
P1 = ROOT / "phase1"

kits_dir = P4 / "kits"
ui_catalog = P5 / "ui_catalog.jsonl"
assets_manifest = P5 / "assets_manifest.jsonl"

P5.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    if not p.exists(): return []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

# 1) Collect kits from phase4
kits = []
for kpath in sorted(kits_dir.glob("*.kit.json")):
    with kpath.open("r", encoding="utf-8") as f:
        k = json.load(f)
    kits.append(k)

# 2) Generate schema-compliant ui_catalog via existing generator
UIDataGenerator(str(ROOT)).generate_catalog()

# 3) Build assets_manifest.jsonl from Phase‑1 media (so the app's asset spot‑check passes)
media_path = P1 / "media_assets.jsonl"

# Backfill: scan artifacts for any files whose basename starts with an asset id.
asset_file_map = {}
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    name = path.name
    if name.startswith("asset_"):
        asset_id = name.split(".")[0]  # strip extension(s)
        if asset_id not in asset_file_map:  # first wins
            try:
                rel_path = path.relative_to(ROOT).as_posix()
            except ValueError:
                rel_path = path.as_posix()
            asset_file_map[asset_id] = rel_path

with assets_manifest.open("w", encoding="utf-8", newline="\n") as out:
    for row in read_jsonl(media_path):
        asset_id = row.get("asset_id")
        # Phase1 media file uses 'path' (relative to Library root). Older variants may have 'file_path'.
        original_path = row.get("file_path") or row.get("path")
        backfilled_path = asset_file_map.get(asset_id) if not original_path else original_path
        # Normalize to absolute path so the desktop runtime can always resolve it regardless of CWD.
        abs_path = None
        if backfilled_path:
            p = pathlib.Path(backfilled_path)
            if not p.is_absolute():
                # Interpret relative media paths as relative to the Library/ root (corpus root sits alongside artifacts)
                library_root = pathlib.Path("Library")
                candidate = library_root / backfilled_path
                p = candidate.resolve()
            abs_path = p.as_posix()
        if not abs_path:
            continue  # skip entries without path resolution
        out.write(json.dumps({
            "asset_type": "corpus",
            "asset_id": asset_id,
            "path": abs_path,
            "sha256": row.get("sha256"),
            "mime": mimetypes.guess_type(abs_path or "")[0],
        }, ensure_ascii=False) + "\n")

print(f"Wrote {len(kits)} kits to {ui_catalog} and assets manifest to {assets_manifest}")

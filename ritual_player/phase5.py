"""Phase 5 orchestrator (doc+kit catalog + assets manifest + gate + digest).

Adds deterministic pipeline digest over contract artifacts to prove reproducibility.
Writes: artifacts/phase5/pipeline_digest.jsonl (one JSON object per line):
  {"path": relative_path_from_repo_root, "sha256": hex}
Ordering: lexicographic by path.
Excludes: any files under artifacts/aux/ and legacy patterns (kits.index.json).
"""
import subprocess, sys, os, hashlib
from pathlib import Path

EXCLUDE_SUFFIXES = {'.sha256'}
EXCLUDE_NAMES = {'kits.index.json'}

def _file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p,'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def _is_contract_artifact(p: Path, artifacts_root: Path) -> bool:
    rel = p.relative_to(artifacts_root)
    # Exclude aux directory
    if rel.parts and rel.parts[0] == 'aux':
        return False
    if p.name in EXCLUDE_NAMES:
        return False
    if any(p.name.endswith(suf) for suf in EXCLUDE_SUFFIXES):
        return False
    return p.is_file()

def _write_pipeline_digest(artifacts_dir: str):
    art_root = Path(artifacts_dir)
    records = []
    for p in art_root.rglob('*'):
        if not _is_contract_artifact(p, art_root):
            continue
        rel_path = p.relative_to(art_root).as_posix()
        records.append({"path": rel_path, "sha256": _file_sha256(p)})
    records.sort(key=lambda r: r['path'])
    out_path = art_root / 'phase5' / 'pipeline_digest.jsonl'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path,'w',encoding='utf-8',newline='\n') as f:
        for r in records:
            import json
            f.write(json.dumps(r, sort_keys=True) + '\n')
    print(f"[phase5] wrote pipeline digest ({len(records)} files) -> {out_path}")

def run_phase5(config):
    artifacts_dir = config['artifacts_dir']
    py = sys.executable
    print("Starting Phase 5: generating ui_catalog + assets_manifest …")
    subprocess.run([py, '-m', 'ritual_player.ui_data_generator', '--artifacts', artifacts_dir], check=True)
    subprocess.run([py, '-m', 'ritual_player.asset_manifest_builder', '--artifacts', artifacts_dir], check=True)
    # Build lightweight search bundle used by renderer search
    subprocess.run([py, '-m', 'ritual_player.search_exporter', '--artifacts', artifacts_dir], check=True)
    subprocess.run([py, '-m', 'ritual_player.phase5_gate', '--artifacts', artifacts_dir], check=True)
    # Digest last (post-gate) so it is not part of its own integrity check
    _write_pipeline_digest(artifacts_dir)
    print("Phase 5 completed successfully.")

__all__ = ["run_phase5"]


import json, tempfile, shutil, sys, subprocess
from pathlib import Path


def read_jsonl(p: Path):
    rows = []
    if not p.exists():
        return rows
    with p.open('r', encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s:
                rows.append(json.loads(s))
    return rows


def test_ui_catalog_not_empty_and_contains_known_kits():
    repo_root = Path(__file__).resolve().parents[1]
    artifacts = repo_root / 'artifacts'
    kits_dir = artifacts / 'phase4' / 'kits'
    if not kits_dir.exists():
        import pytest
        pytest.skip('No kits present; skipping phase5 guard test')

    with tempfile.TemporaryDirectory() as td:
        tmp_art = Path(td) / 'artifacts'
        shutil.copytree(artifacts, tmp_art)
        py = sys.executable
        # Run full phase5 path into temp artifacts
        subprocess.run([py, '-m', 'onyx_scribe.cli', 'phase5', '--artifacts', str(tmp_art), '--root', str(repo_root / 'Library')], check=True, cwd=repo_root)
        cat = tmp_art / 'phase5' / 'ui_catalog.jsonl'
        assert cat.exists(), 'ui_catalog.jsonl missing'
        rows = read_jsonl(cat)
        assert rows, 'ui_catalog.jsonl is empty'
        # Support legacy rows or kit-centric
        kit_ids = set()
        for r in rows:
            if isinstance(r, dict):
                if r.get('type') == 'kit' and r.get('kit_id'):
                    kit_ids.add(r['kit_id'])
                elif r.get('kind') == 'kit' and r.get('kit_id'):
                    kit_ids.add(r['kit_id'])
        assert kit_ids, 'No kits found in ui_catalog.jsonl'
        expected = {'gd-lbrp', 'gd-middle-pillar'}
        assert kit_ids & expected, f'Expected at least one of {sorted(expected)}, found {sorted(kit_ids)}'

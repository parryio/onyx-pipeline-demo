import json, tempfile, shutil, os, subprocess, sys
from pathlib import Path


def read_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def test_ui_catalog_contains_known_kit():
    """Smoke test: run Phase 5 generation against existing artifacts and assert at least one expected kit appears.

    This test assumes artifacts/phase4/kits already built in repo working dir.
    If not present, it will be skipped gracefully.
    """
    repo_root = Path(__file__).resolve().parent.parent
    artifacts_dir = repo_root / 'artifacts'
    kits_dir = artifacts_dir / 'phase4' / 'kits'
    if not kits_dir.exists():
        import pytest
        pytest.skip('No kits directory present; skip smoke test.')

    # Run ui catalog builder directly (Phase 5 partial) into a temp copy to avoid mutating canonical artifacts
    with tempfile.TemporaryDirectory() as tmp:
        tmp_art = Path(tmp) / 'artifacts'
        shutil.copytree(artifacts_dir, tmp_art)
        py = sys.executable
        subprocess.run([py, 'ritual_player/ui_data_generator.py', '--artifacts', str(tmp_art)], check=True, cwd=repo_root)
        catalog_path = tmp_art / 'phase5' / 'ui_catalog.jsonl'
        rows = read_jsonl(catalog_path)
        assert rows, 'ui_catalog.jsonl should not be empty'
        kit_ids = set()
        for r in rows:
            if isinstance(r, dict):
                if r.get('type') == 'kit' and r.get('kit_id'):
                    kit_ids.add(r['kit_id'])
                elif r.get('kind') == 'kit' and r.get('kit_id'):
                    kit_ids.add(r['kit_id'])
        # Accept either LBRP or Middle Pillar to allow varying presence
        expected = {'gd-lbrp','gd-middle-pillar'}
        assert kit_ids & expected, f'Expected at least one of {expected}, found {sorted(kit_ids)}'
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip('yaml')


def _make_temp_config(repo_root: Path, tmp_path: Path, library: Path, artifacts: Path, cache_path: Path) -> Path:
    base_cfg = yaml.safe_load((repo_root / 'config' / 'onyx.yml').read_text(encoding='utf-8')) or {}
    phase3_cfg = base_cfg.setdefault('phase3', {})
    phase3_cfg['enrichment_cache'] = str(cache_path)
    base_cfg['root'] = str(library)
    base_cfg['artifacts_dir'] = str(artifacts)
    tmp_cfg_path = tmp_path / 'onyx_custom.yml'
    tmp_cfg_path.write_text(yaml.safe_dump(base_cfg), encoding='utf-8')
    return tmp_cfg_path


def test_pipeline_phase3_gate_uses_config_path(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    library = tmp_path / 'Library'
    library.mkdir(parents=True, exist_ok=True)
    (library / 'doc.txt').write_text('Hello Phase3 cache test', encoding='utf-8')

    cache_path = tmp_path / 'cache' / 'phase3_enrichment.jsonl'
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_record = {
        'chunk_hash': 'stub',
        'prompt_hash': 'stub',
        'model': 'offline',
        'temperature': 0.0,
        'seed': 0,
        'raw_response': '{}',
        'system_fingerprint': 'offline-stub'
    }
    cache_path.write_text(json.dumps(cache_record, sort_keys=True) + '\n', encoding='utf-8')

    artifacts = tmp_path / 'artifacts'
    config_path = _make_temp_config(repo_root, tmp_path, library, artifacts, cache_path)

    cmd = [
        sys.executable,
        '-m',
        'onyx_scribe.cli',
        'pipeline',
        'run',
        '--config',
        str(config_path),
        '--root',
        str(library),
        '--artifacts',
        str(artifacts),
    ]
    env = os.environ.copy()
    env.setdefault('ONYX_TEST_STUB_OCR', '1')
    env['ONYX_PHASE1_MAX_DOCS'] = '1'
    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
    )

    assert 'Phase 3 skipped or failed' not in result.stdout

    metrics_path = artifacts / 'phase3' / 'metrics_phase3.json'
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    assert metrics['enrichment_cache_path'] == str(cache_path)
    expected_digest = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    assert metrics['enrichment_cache_digest'] == expected_digest

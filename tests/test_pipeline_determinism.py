import os, subprocess, shutil, json, time, hashlib
from pathlib import Path

def run_pipeline_and_digest(artifacts_dir: Path):
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)
    cache_path = Path('datasets/phase3/enrichment_cache.jsonl')
    if cache_path.exists():
        cache_path.unlink()
    cmd = [
        'onyx', 'pipeline', 'run',
        '--root', 'Library',
        '--artifacts', str(artifacts_dir),
        '--config', 'config/onyx.yml'
    ]
    env = os.environ.copy()
    # Speed lever: limit Phase 1 documents for CI smoke determinism test
    env['ONYX_PHASE1_MAX_DOCS'] = env.get('ONYX_PHASE1_MAX_DOCS','1')
    subprocess.run(cmd, check=True, env=env)
    digest_path = artifacts_dir / 'phase5' / 'pipeline_digest.jsonl'
    lines = []
    with open(digest_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                lines.append(line)
    return ''.join(lines)

def test_pipeline_determinism(tmp_path):
    art1 = tmp_path / 'artifacts_run1'
    art2 = tmp_path / 'artifacts_run2'
    d1 = run_pipeline_and_digest(art1)
    d2 = run_pipeline_and_digest(art2)
    assert d1 == d2, 'Pipeline digest mismatch — nondeterministic artifacts detected'


def test_pipeline_succeeds_without_phase3_cache(tmp_path):
    artifacts_dir = tmp_path / 'artifacts_no_cache'
    cache_path = Path('datasets/phase3/enrichment_cache.jsonl')
    if cache_path.exists():
        cache_path.unlink()
    digest = run_pipeline_and_digest(artifacts_dir)
    assert digest, 'Pipeline run did not produce a phase5 digest'

    expected_paths = [
        artifacts_dir / 'phase3' / 'doc_metadata.jsonl',
        artifacts_dir / 'phase3' / 'entities.jsonl',
        artifacts_dir / 'phase3' / 'metrics_phase3.json',
        artifacts_dir / 'phase3' / 'ritual_steps.jsonl',
        artifacts_dir / 'phase4' / 'kit_index.jsonl',
        artifacts_dir / 'phase5' / 'pipeline_digest.jsonl',
    ]
    missing = [str(p) for p in expected_paths if not p.exists()]
    assert not missing, f"Pipeline run missing expected artifacts: {missing}"

    metrics_path = artifacts_dir / 'phase3' / 'metrics_phase3.json'
    metrics = json.loads(metrics_path.read_text())
    assert metrics.get('enrichment_cache_empty') is True
    assert metrics.get('enrichment_cache_digest') == hashlib.sha256(b'').hexdigest()

import os, subprocess, shutil, json, time
from pathlib import Path

def run_pipeline_and_digest(artifacts_dir: Path):
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)
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
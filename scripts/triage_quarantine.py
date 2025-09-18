import argparse
import json
from pathlib import Path
from typing import Dict, Any, List

CATEGORY_A = 'unrecoverable_corruption'
CATEGORY_B = 'encoding_error'
CATEGORY_C = 'ocr_engine_failed'
CATEGORY_O = 'other'


def categorize_reason(reason: str) -> str:
    r = reason.lower()
    if any(tok in r for tok in [
        'stream has ended unexpectedly',
        'negative seek',
        'corrupt pdf structure',
        'pdf open failed',
        'ocr_rasterize_failed'
    ]):
        return CATEGORY_A
    if 'codec can\'t decode' in r or 'invalid continuation byte' in r or 'utf-8' in r and 'decode' in r:
        return CATEGORY_B
    if 'ocr_engine_failed' in r or 'ocr_full_offline' in r:
        return CATEGORY_C
    return CATEGORY_O


def load_quarantine(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]):
    with path.open('w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + '\n')


def main():
    p = argparse.ArgumentParser(description='Triage Phase1 quarantine into categories and propose actions')
    p.add_argument('artifacts_root', help='Artifacts directory (root containing phase1/)')
    p.add_argument('--move-unrecoverable', action='store_true', help='Move Category A items to Library/.quarantined')
    p.add_argument('--library-root', default='Library', help='Library root (for moving files)')
    args = p.parse_args()

    q_path = Path(args.artifacts_root) / 'phase1' / 'quarantine.jsonl'
    if not q_path.exists():
        print(f'No quarantine file found at {q_path}')
        return

    rows = load_quarantine(q_path)
    summary = {CATEGORY_A: 0, CATEGORY_B: 0, CATEGORY_C: 0, CATEGORY_O: 0}
    categorized: List[Dict[str, Any]] = []
    for r in rows:
        cat = categorize_reason(r.get('reason', ''))
        summary[cat] += 1
        out = dict(r)
        out['category'] = cat
        categorized.append(out)

    triage_path = q_path.with_name('quarantine_triage.jsonl')
    write_jsonl(triage_path, categorized)
    print('Triage summary:')
    for k, v in summary.items():
        print(f'  {k}: {v}')
    print(f'Wrote categorized triage to {triage_path}')

    if args.move_unrecoverable:
        lib = Path(args.library_root)
        dst_root = lib / '.quarantined'
        dst_root.mkdir(parents=True, exist_ok=True)
        moved = 0
        for r in categorized:
            if r['category'] != CATEGORY_A:
                continue
            src = lib / r['path']
            if not src.exists():
                continue
            dst = dst_root / Path(r['path']).name
            try:
                src.replace(dst)
                moved += 1
            except Exception as e:
                print(f'Failed to move {src}: {e}')
        print(f'Moved {moved} unrecoverable files to {dst_root}')


if __name__ == '__main__':
    main()

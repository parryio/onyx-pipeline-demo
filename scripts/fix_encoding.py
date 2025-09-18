import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

FALLBACKS = ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1', 'windows-1252']

def try_decode(data: bytes) -> str | None:
    for enc in FALLBACKS:
        try:
            return data.decode(enc)
        except Exception:
            continue
    return None


def main():
    p = argparse.ArgumentParser(description='Fix encoding for Category B quarantine items by re-saving as UTF-8')
    p.add_argument('artifacts_root', help='Artifacts directory (root containing phase1/)')
    p.add_argument('--library-root', default='Library', help='Library root for file paths')
    p.add_argument('--dry-run', action='store_true', help='Do not write changes, just report')
    args = p.parse_args()

    triage_path = Path(args.artifacts_root) / 'phase1' / 'quarantine_triage.jsonl'
    if not triage_path.exists():
        print(f'Missing triage file: {triage_path}. Run triage_quarantine.py first.')
        return

    items = load_jsonl(triage_path)
    lib = Path(args.library_root)

    fixed = 0
    skipped = 0
    for r in items:
        if r.get('category') != 'encoding_error':
            continue
        rel = r.get('path')
        if not rel:
            skipped += 1
            continue
        path = lib / rel
        if not path.exists():
            print(f'[skip] missing: {path}')
            skipped += 1
            continue
        data = path.read_bytes()
        text = try_decode(data)
        if text is None:
            print(f'[fail] could not decode with fallbacks: {path}')
            skipped += 1
            continue
        if args.dry_run:
            print(f'[dry-run] would re-save UTF-8: {path}')
        else:
            path.write_text(text, encoding='utf-8', newline='\n')
            print(f'[fixed] {path}')
            fixed += 1

    print(f'Done. fixed={fixed} skipped={skipped}')


if __name__ == '__main__':
    main()

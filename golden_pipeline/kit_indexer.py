import json
from pathlib import Path
from typing import Dict, Any, List

def index_kits(config: Dict[str, Any]) -> None:
    """Create kit_index.jsonl summarizing kits.

    Deterministic ordering by kit_id.
    Each record: {kit_id, kit_name, description, step_count}
    """
    artifacts_dir = Path(config.get('artifacts_dir', 'artifacts'))
    phase4_dir = artifacts_dir / 'phase4'
    kits_dir = phase4_dir / 'kits'
    kits = []
    if kits_dir.exists():
        for p in kits_dir.glob('*.kit.json'):
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            kits.append({
                'kit_id': data.get('id'),
                'kit_name': data.get('name'),
                'description': data.get('description',''),
                'step_count': len(data.get('step_ids') or [])
            })
    kits.sort(key=lambda x: x['kit_id'])
    out_path = phase4_dir / 'kit_index.jsonl'
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        for r in kits:
            f.write(json.dumps(r, sort_keys=True) + '\n')
    print(f"[phase4] wrote kit index ({len(kits)} kits) -> {out_path}")

__all__ = ['index_kits']

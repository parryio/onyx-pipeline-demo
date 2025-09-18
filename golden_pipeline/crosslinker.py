import json
from pathlib import Path
from typing import Dict, Any, List

def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out

def create_crosslinks(config: Dict[str, Any]) -> None:
    """Create crosslinks.jsonl mapping kit -> ritual steps & docs.

    Record types (extensible):
      - kit_step: {type, kit_id, ritual_step_id}
      - kit_doc: {type, kit_id, doc_id}
    Deterministic ordering by (type, kit_id, ritual_step_id|doc_id).
    """
    artifacts_dir = Path(config.get('artifacts_dir','artifacts'))
    phase3_dir = artifacts_dir / 'phase3'
    phase4_dir = artifacts_dir / 'phase4'
    kits_dir = phase4_dir / 'kits'
    ritual_steps = _load_jsonl(phase3_dir / 'ritual_steps.jsonl')
    steps_by_id = {r.get('ritual_step_id') or r.get('id'): r for r in ritual_steps if (r.get('ritual_step_id') or r.get('id'))}

    crosslinks: List[Dict[str, Any]] = []
    for kit_file in kits_dir.glob('*.kit.json'):
        data = json.loads(kit_file.read_text(encoding='utf-8'))
        kid = data.get('id')
        for sid in data.get('step_ids') or []:
            if sid in steps_by_id:
                crosslinks.append({'type':'kit_step','kit_id':kid,'ritual_step_id':sid})
        for did in data.get('source_doc_ids') or []:
            crosslinks.append({'type':'kit_doc','kit_id':kid,'doc_id':did})
    crosslinks.sort(key=lambda x: (x['type'], x['kit_id'], x.get('ritual_step_id',''), x.get('doc_id','')))
    out_path = phase4_dir / 'crosslinks.jsonl'
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        for r in crosslinks:
            f.write(json.dumps(r, sort_keys=True) + '\n')
    print(f"[phase4] wrote crosslinks ({len(crosslinks)}) -> {out_path}")

__all__ = ['create_crosslinks']

"""Phase 4 Kit Assembler (Ritual Compiler)

Upgrades:
 - Domain Profiles: lexicons/domain_profiles/<domain>.yaml enumerates allowed_actions
     and prerequisite kits (link_only) whose steps must not be inlined.
 - RAW Kit Artifact: kits/<kit_id>.kit.json contains full ordered ritual step
     records (subset fields), deterministic ordering: (doc_id index in manifest, chunk_seq, char_start).
 - LEAN Kit Artifact: kits/<kit_id>.kit.lean.json collapses adjacent micro steps
     (currently: consecutive identical action labels) to a single lean step.
 - Collapse Derivations: artifacts/phase4/derivations/collapse_map.jsonl maps
     each lean step back to source ritual_step_ids for full traceability.

Determinism Rules:
 - All inputs local deterministic artifacts.
 - No randomness, no network calls.
 - Sorting stable and explicit.
"""
from __future__ import annotations
import json, yaml
from golden_pipeline.util.slugs import canon_domain, canon_action
from pathlib import Path
from typing import List, Dict, Any

KIT_MANIFEST_FILENAME = 'kit_manifest.yaml'
DOMAIN_PROFILES_DIR = 'lexicons/domain_profiles'

def _determine_domain(kit_id: str) -> str:
    if '-' in kit_id:
        base = kit_id.split('-', 1)[0]
    else:
        base = kit_id
    return canon_domain(base) or base

def _load_domain_profile(domain: str) -> Dict[str, Any]:
    path = Path(DOMAIN_PROFILES_DIR) / f"{domain}.yaml"
    if not path.exists():
        return {}
    try:
        return _load_yaml(path) or {}
    except Exception as e:
        raise ValueError(f"Failed loading domain profile {path}: {e}")

from typing import Tuple

def _collapse_steps(ordered_steps: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Collapse adjacent steps with identical action.

    Returns: (lean_steps, collapse_map_entries)
      lean_step: {index, action, step_ids:[...]}
      collapse_map entry: {kit_id, lean_index, action, source_step_ids:[...]}
    """
    lean: List[Dict[str, Any]] = []
    collapse_entries: List[Dict[str, Any]] = []
    if not ordered_steps:
        return lean, collapse_entries
    current_action = None
    buf_ids: List[str] = []
    for s in ordered_steps:
        action = s.get('action')
        sid = s.get('ritual_step_id') or s.get('id')
        if current_action is None:
            current_action = action
            buf_ids = [sid]
            continue
        if action == current_action:
            buf_ids.append(sid)
        else:
            lean.append({'index': len(lean), 'action': current_action, 'step_ids': buf_ids, 'first_step_id': buf_ids[0]})
            collapse_entries.append({'lean_index': len(lean)-1, 'action': current_action, 'source_step_ids': buf_ids})
            current_action = action
            buf_ids = [sid]
    # flush
    if buf_ids:
        lean.append({'index': len(lean), 'action': current_action, 'step_ids': buf_ids, 'first_step_id': buf_ids[0]})
        collapse_entries.append({'lean_index': len(lean)-1, 'action': current_action, 'source_step_ids': buf_ids})
    return lean, collapse_entries

def _load_yaml(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8') as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {path} line {ln}: {e}")
    return out

def assemble_kits(config: Dict[str, Any]) -> None:
    artifacts_dir = Path(config.get('artifacts_dir', 'artifacts'))
    phase3_dir = artifacts_dir / 'phase3'
    phase4_dir = artifacts_dir / 'phase4'
    kits_dir = phase4_dir / 'kits'
    kits_dir.mkdir(parents=True, exist_ok=True)

    # Inputs
    ritual_steps_path = phase3_dir / 'ritual_steps.jsonl'
    if not ritual_steps_path.exists():
        print(f"[phase4] ritual_steps.jsonl not found at {ritual_steps_path}; no kits assembled.")
        return
    doc_meta_path = phase3_dir / 'doc_metadata.jsonl'
    if not doc_meta_path.exists():
        raise FileNotFoundError(doc_meta_path)
    # Locate manifest (co-located with lexicons for now)
    lex_dir = Path((config.get('paths') or {}).get('lexicons', 'lexicons'))
    kit_manifest_path = lex_dir / KIT_MANIFEST_FILENAME
    if not kit_manifest_path.exists():
        raise FileNotFoundError(f"Missing kit manifest: {kit_manifest_path}")

    kit_manifest: List[Dict[str, Any]] = _load_yaml(kit_manifest_path) or []
    ritual_steps = _load_jsonl(ritual_steps_path)
    doc_meta = _load_jsonl(doc_meta_path)
    doc_title_by_id = {d['doc_id']: d.get('title') for d in doc_meta}

    # Index ritual steps by source_doc_id
    steps_by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for rs in ritual_steps:
        sd = rs.get('source_doc_id') or rs.get('doc_id')  # fallback if schema evolves
        if not sd:
            continue
        steps_by_doc.setdefault(sd, []).append(rs)

    # Build quick reverse index for prerequisite doc_id lists (kit_id->doc_ids)
    kit_docs_map = {k['kit_id']: (k.get('source_doc_ids') or []) for k in kit_manifest}

    derivations_dir = phase4_dir / 'derivations'
    derivations_dir.mkdir(parents=True, exist_ok=True)
    collapse_map_path = derivations_dir / 'collapse_map.jsonl'
    with open(collapse_map_path, 'w', encoding='utf-8', newline='\n') as collapse_f:
        for kit in kit_manifest:
            kit_id = kit['kit_id']
            kit_name = kit.get('kit_name', kit_id)
            source_doc_ids: List[str] = kit.get('source_doc_ids') or []
            keywords: List[str] = kit.get('keywords') or []
            description: str = kit.get('description', '')
            domain = kit.get('domain') or _determine_domain(kit_id)
            domain_profile = _load_domain_profile(domain)
            allowed_actions = set(domain_profile.get('allowed_actions') or [])
            prerequisites = domain_profile.get('prerequisites') or []
            # Collect doc ids to exclude due to link_only prerequisites
            exclude_doc_ids: set[str] = set()
            prereq_kit_ids = []
            for pr in prerequisites:
                if pr.get('action') == 'link_only':
                    pid = pr.get('kit_id')
                    # Do not self-exclude: a kit listed as a prerequisite should only be excluded
                    # from OTHER kits' inlining, not from its own assembly.
                    if pid and pid in kit_docs_map and pid != kit_id:
                        exclude_doc_ids.update(kit_docs_map[pid])
                        prereq_kit_ids.append(pid)

            ordered_steps: List[Dict[str, Any]] = []
            # Deterministic doc ordering: as provided in manifest (defines doc priority)
            for doc_id in source_doc_ids:
                if doc_id in exclude_doc_ids:
                    continue  # Do not inline prerequisites
                doc_steps = steps_by_doc.get(doc_id, [])
                # Filter by allowed actions if profile present
                if allowed_actions:
                    doc_steps = [s for s in doc_steps if (canon_action(s.get('action')) in allowed_actions)]
                # Deterministic ordering: (chunk_seq, char_start)
                def _sort_key(s):
                    # chunk_seq may be None; treat None as large sentinel to keep numbered first
                    seq = s.get('chunk_seq')
                    return (seq if isinstance(seq, int) else 10**9, s.get('char_start', 0))
                doc_steps.sort(key=_sort_key)
                ordered_steps.extend(doc_steps)

            # Canonicalize action labels before serialization & collapse
            for s in ordered_steps:
                s['action'] = canon_action(s.get('action'))
            step_ids = [s.get('ritual_step_id') or s.get('id') for s in ordered_steps if (s.get('ritual_step_id') or s.get('id'))]
            if not step_ids:
                print(f"[WARNING] Kit {kit_id} has zero ritual steps after filtering; skipping generation.")
                continue

            # RAW kit with embedded minimal step info (traceability & schema stability)
            raw_steps_min = [
                {
                    'ritual_step_id': s.get('ritual_step_id') or s.get('id'),
                    'action': s.get('action'),
                    'source_doc_id': s.get('source_doc_id'),
                    'source_chunk_id': s.get('source_chunk_id'),
                    'char_start': s.get('char_start'),
                    'char_end': s.get('char_end')
                } for s in ordered_steps
            ]

            lean_steps, collapse_entries = _collapse_steps(ordered_steps)
            # Annotate collapse entries with kit id for derivations file
            for ce in collapse_entries:
                ce['kit_id'] = kit_id
            for ce in collapse_entries:
                collapse_f.write(json.dumps(ce, sort_keys=True) + '\n')

            kit_raw_obj = {
                'id': kit_id,
                'name': kit_name,
                'domain': domain,
                'source_doc_ids': source_doc_ids,
                'keywords': keywords,
                'description': description,
                'step_ids': step_ids,
                'steps': raw_steps_min,
                'prerequisite_kit_ids': prereq_kit_ids,
                'source_doc_titles': [doc_title_by_id.get(d) for d in source_doc_ids],
                'schema': 'kit.raw.v1'
            }
            raw_path = kits_dir / f"{kit_id}.kit.json"
            with open(raw_path, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(kit_raw_obj, f, sort_keys=True, indent=2)

            kit_lean_obj = {
                'id': kit_id,
                'name': kit_name,
                'domain': domain,
                'source_doc_ids': source_doc_ids,
                'steps_raw_count': len(raw_steps_min),
                'steps_lean_count': len(lean_steps),
                'lean_steps': lean_steps,
                'schema': 'kit.lean.v1'
            }
            lean_path = kits_dir / f"{kit_id}.kit.lean.json"
            with open(lean_path, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(kit_lean_obj, f, sort_keys=True, indent=2)

            print(f"[phase4] wrote kit {kit_id} RAW={len(raw_steps_min)} LEAN={len(lean_steps)} -> {raw_path.name}, {lean_path.name}")
    print(f"[phase4] wrote collapse derivations -> {collapse_map_path}")

__all__ = ['assemble_kits']

if __name__ == '__main__':
    # Minimal manual invocation (debugging)
    import yaml, sys
    cfg_path = Path('config/onyx.yml')
    if len(sys.argv) > 1:
        cfg_path = Path(sys.argv[1])
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    assemble_kits(cfg)

"""Phase 4 Gate (Hardened Ritual Compiler Verifier)

Adds objective fidelity guardrails:
 - Manifest parity (all kits present: RAW & LEAN)
 - Referential integrity for RAW step_ids & doc_ids
 - Span Fidelity: every RAW step's matched_text must equal source chunk substring (hallucination rate = 0)
 - Prerequisite Isolation: domain profile link_only kits' doc_ids must not appear in RAW steps of dependent kits
 - Step Count Bands: enforce config/step_count_bands.yaml inclusive ranges (raw & lean)
 - Crosslinks consistency (existing)
"""
from __future__ import annotations
from pathlib import Path
import json, yaml
from typing import Dict, Any, List, Set, Tuple
import yaml
from golden_pipeline.util.slugs import canon_domain, canon_action

DOMAIN_PROFILES_DIR = 'lexicons/domain_profiles'

def _load_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def _determine_domain(kit_id: str) -> str:
    return kit_id.split('-',1)[0] if '-' in kit_id else kit_id

def _load_domain_profile(domain: str) -> Dict[str, Any]:
    path = Path(DOMAIN_PROFILES_DIR) / f"{domain}.yaml"
    if not path.exists():
        return {}
    try:
        return _load_yaml(path) or {}
    except Exception as e:
        raise GateError(f"Failed to load domain profile {path}: {e}")

class GateError(Exception):
    pass

def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, 'r', encoding='utf-8') as f:
        for ln, line in enumerate(f,1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise GateError(f"Invalid JSON in {path} line {ln}: {e}")
    return rows

def verify_phase4_artifacts(config: Dict[str, Any]) -> None:
    artifacts_dir = Path(config.get('artifacts_dir','artifacts'))
    phase4_dir = artifacts_dir / 'phase4'
    phase3_dir = artifacts_dir / 'phase3'
    phase1_dir = artifacts_dir / 'phase1'
    kits_dir = phase4_dir / 'kits'
    lex_dir = Path((config.get('paths') or {}).get('lexicons','lexicons'))
    kit_manifest_path = lex_dir / 'kit_manifest.yaml'
    if not kit_manifest_path.exists():
        raise GateError(f"Missing kit_manifest.yaml at {kit_manifest_path}")
    kit_manifest = yaml.safe_load(kit_manifest_path.read_text(encoding='utf-8')) or []
    kit_files = {p.stem.replace('.kit',''): p for p in kits_dir.glob('*.kit.json')}
    lean_files = {p.stem.replace('.kit.lean','').replace('.kit',''): p for p in kits_dir.glob('*.kit.lean.json')}

    ritual_steps = _load_jsonl(phase3_dir / 'ritual_steps.jsonl')
    step_ids: Set[str] = set()
    for s in ritual_steps:
        sid = s.get('ritual_step_id') or s.get('id')
        if sid:
            step_ids.add(sid)
    ritual_steps_by_id = { (s.get('ritual_step_id') or s.get('id')): s for s in ritual_steps if (s.get('ritual_step_id') or s.get('id')) }
    # Load chunks for span fidelity
    chunk_text_by_id: Dict[str, str] = {}
    chunks_path = phase1_dir / 'chunks.jsonl'
    if chunks_path.exists():
        with open(chunks_path, 'r', encoding='utf-8') as f:
            for ln, line in enumerate(f,1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    raise GateError(f"Invalid JSON in chunks.jsonl line {ln}: {e}")
                cid = row.get('chunk_id')
                if cid:
                    chunk_text_by_id[cid] = row.get('text','')
    manifest_docs = _load_jsonl(phase1_dir / 'manifest.jsonl')
    doc_ids = {d['doc_id'] for d in manifest_docs}

    errors: List[str] = []

    # Parity
    # Build quick map doc_id -> has any ritual steps
    doc_has_steps: Set[str] = {s.get('source_doc_id') for s in ritual_steps}
    for kit in kit_manifest:
        kid = kit['kit_id']
        src_docs = set(kit.get('source_doc_ids') or [])
        # If none of the source docs have steps yet, treat absence as WARN not error (data gap)
        if not (src_docs & doc_has_steps):
            if f"{kid}" not in kit_files and f"{kid}.kit" not in kit_files:
                print(f"  [WARN] Skipping parity for {kid} (no ritual steps exist for its source docs yet)")
            continue
        if f"{kid}" not in kit_files and f"{kid}.kit" not in kit_files:
            errors.append(f"Missing RAW kit file for kit_id {kid}")
        if kid not in lean_files:
            errors.append(f"Missing LEAN kit file for kit_id {kid}")

    # Validate each kit file
    # Load step count policy
    step_bands = _load_yaml(Path('config/step_count_bands.yaml')) or {}
    bands = (step_bands or {}).get('kits', {})

    for p in kits_dir.glob('*.kit.json'):
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            errors.append(f"Invalid JSON in kit file {p.name}: {e}")
            continue
        kid = data.get('id') or p.stem
        # step_ids integrity
        for sid in data.get('step_ids') or []:
            if sid not in step_ids:
                errors.append(f"Kit {kid} references unknown ritual_step_id {sid}")
        for did in data.get('source_doc_ids') or []:
            if did not in doc_ids:
                errors.append(f"Kit {kid} references unknown source_doc_id {did}")
        # Span fidelity (RAW steps)
        for rs in data.get('steps') or []:
            sid = rs.get('ritual_step_id')
            ref = ritual_steps_by_id.get(sid)
            if not ref:
                errors.append(f"Kit {kid} RAW step {sid} missing in ritual_steps.jsonl")
                continue
            chunk_id = ref.get('source_chunk_id')
            text = chunk_text_by_id.get(chunk_id)
            if text is None:
                errors.append(f"Kit {kid} RAW step {sid} references missing chunk {chunk_id}")
                continue
            cs, ce = ref.get('char_start'), ref.get('char_end')
            if not isinstance(cs, int) or not isinstance(ce, int) or cs < 0 or ce > len(text):
                errors.append(f"Kit {kid} RAW step {sid} has invalid span {cs}:{ce}")
                continue
            span_txt = text[cs:ce]
            if span_txt != ref.get('matched_text'):
                errors.append(f"Span mismatch kit {kid} step {sid}: '{span_txt}' != '{ref.get('matched_text')}'")
        # Step count bands (raw)
        if kid in bands:
            b = bands.get(kid) or {}
            raw_ct = len(data.get('steps') or [])
            mn = b.get('raw_min'); mx = b.get('raw_max')
            if (mn is not None and raw_ct < mn) or (mx is not None and raw_ct > mx):
                errors.append(f"Kit {kid} raw step_count {raw_ct} outside [{mn},{mx}]")

        # Prerequisite isolation
        domain = canon_domain(data.get('domain') or _determine_domain(kid))
        profile = _load_domain_profile(domain)
        prereqs = [pr for pr in (profile.get('prerequisites') or []) if pr.get('action') == 'link_only']
        # Build doc ids of prerequisites via manifest lookup
        prereq_doc_ids: Set[str] = set()
        manifest_map = {m['kit_id']: (m.get('source_doc_ids') or []) for m in kit_manifest}
        for pr in prereqs:
            pid = pr.get('kit_id')
            if pid and pid != kid and pid in manifest_map:
                prereq_doc_ids.update(manifest_map[pid])
        if prereq_doc_ids:
            for rs in data.get('steps') or []:
                if rs.get('source_doc_id') in prereq_doc_ids:
                    errors.append(f"Kit {kid} illegally inlines prerequisite kit doc step from doc {rs.get('source_doc_id')}")

    # Validate LEAN files (step count bands lean)
    for lp in kits_dir.glob('*.kit.lean.json'):
        try:
            ld = json.loads(lp.read_text(encoding='utf-8'))
        except Exception as e:
            errors.append(f"Invalid JSON in lean kit file {lp.name}: {e}")
            continue
        kid = ld.get('id') or lp.stem.replace('.kit.lean','')
        # Normalize lean step actions in-place
        for ls in (ld.get('lean_steps') or []):
            ls['action'] = canon_action(ls.get('action'))
        if kid in bands:
            b = bands.get(kid) or {}
            lean_ct = len(ld.get('lean_steps') or [])
            mn = b.get('lean_min'); mx = b.get('lean_max')
            if (mn is not None and lean_ct < mn) or (mx is not None and lean_ct > mx):
                errors.append(f"Kit {kid} lean step_count {lean_ct} outside [{mn},{mx}]")

    # Crosslinks consistency
    crosslinks_path = phase4_dir / 'crosslinks.jsonl'
    crosslinks = _load_jsonl(crosslinks_path)
    if kit_files and not crosslinks:
        errors.append("crosslinks.jsonl missing or empty despite kit files present")
    kit_ids_present = {k['kit_id'] for k in crosslinks if 'kit_id' in k}
    for kid in kit_ids_present:
        if f"{kid}.kit" not in kit_files and kid not in kit_files:
            errors.append(f"Crosslink references non-existent kit {kid}")
    for cl in crosslinks:
        t = cl.get('type')
        if t == 'kit_step':
            sid = cl.get('ritual_step_id')
            if sid not in step_ids:
                errors.append(f"Crosslink kit_step unknown ritual_step_id {sid}")
        if t == 'kit_doc':
            did = cl.get('doc_id')
            if did not in doc_ids:
                errors.append(f"Crosslink kit_doc unknown doc_id {did}")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}")
        raise GateError("Phase 4 gate failed")
    print("  [PASS] Phase 4 verification successful (hallucination rate = 0, prerequisites isolated).")

__all__ = ['verify_phase4_artifacts','GateError']

if __name__ == '__main__':
    import sys, yaml
    cfg_path = 'config/onyx.yml'
    if len(sys.argv) > 1:
        cfg_path = sys.argv[1]
    with open(cfg_path,'r',encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    try:
        verify_phase4_artifacts(cfg)
    except GateError as e:
        print(str(e))
        raise SystemExit(1)

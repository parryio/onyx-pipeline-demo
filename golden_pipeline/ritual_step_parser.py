"""Deterministic Ritual Step Parser (Phase 3)

Reads phase1/chunks.jsonl and a lexicon of ritual action regex patterns
(`lexicons/ritual_actions.yaml`) to extract candidate ritual steps.

Output: artifacts/phase3/ritual_steps.jsonl
Each record (schema v1):
  ritual_step_id: rit_<12hex> (sha256 hash prefix of doc_id|chunk_id|start|end|label)
  action: canonical action label from lexicon
  matched_text: the exact substring matched
  source_doc_id: doc owning the chunk
  source_chunk_id: chunk identifier
  char_start: start offset within chunk text
  char_end: end offset within chunk text (exclusive)
  chunk_seq: optional original sequence if present on the chunk

Determinism rules:
  - Streaming single-pass read of chunks.jsonl (order already canonical from Phase 1)
  - Patterns applied in lexicon order; matches recorded in ascending char_start
  - ritual_step_id derived from stable hash of identifying features
  - Final list sorted by (source_doc_id, source_chunk_id, char_start, action, matched_text)

Lexicon format (ritual_actions.yaml):
  patterns:
    - label: vibrate
      regex: "\\bvibrate(?:\\s+the)?\\b"
    - label: qabalistic-cross
      regex: "qabalistic cross"

Safety: No network calls. Purely deterministic local parsing.
"""
from __future__ import annotations
import json, re, hashlib
from pathlib import Path
from typing import List, Dict, Any, Iterable, Tuple
import yaml

def _load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def _iter_chunks(chunks_path: Path) -> Iterable[Dict[str, Any]]:
    with open(chunks_path, 'r', encoding='utf-8') as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {chunks_path} line {ln}: {e}")
            # Minimal required keys
            if 'chunk_id' not in row or 'doc_id' not in row:
                continue
            yield row

def _compile_patterns(lexicon: Dict[str, Any]) -> List[Tuple[str, re.Pattern]]:
    pats: List[Tuple[str, re.Pattern]] = []
    for entry in lexicon.get('patterns', []):
        label = entry.get('label')
        regex = entry.get('regex')
        if not label or not regex:
            continue
        pats.append((label, re.compile(regex, re.IGNORECASE)))
    return pats

def extract_ritual_steps(chunks_path: Path, lexicon_path: Path) -> List[Dict[str, Any]]:
    lexicon = _load_yaml(lexicon_path)
    patterns = _compile_patterns(lexicon)
    if not patterns:
        return []
    steps: List[Dict[str, Any]] = []
    for chunk in _iter_chunks(chunks_path):
        text = chunk.get('text') or ''
        if not text:
            continue
        doc_id = chunk['doc_id']
        chunk_id = chunk['chunk_id']
        seq = chunk.get('seq')
        for label, pat in patterns:
            for m in pat.finditer(text):
                cs, ce = m.start(), m.end()
                # Stable hash id
                h = hashlib.sha256(f"{doc_id}|{chunk_id}|{cs}|{ce}|{label}".encode('utf-8')).hexdigest()[:12]
                rid = f"rit_{h}"
                steps.append({
                    'ritual_step_id': rid,
                    'action': label,
                    'matched_text': m.group(0),
                    'source_doc_id': doc_id,
                    'source_chunk_id': chunk_id,
                    'char_start': cs,
                    'char_end': ce,
                    'chunk_seq': seq
                })
    # Deterministic ordering
    steps.sort(key=lambda s: (s['source_doc_id'], s['source_chunk_id'], s['char_start'], s['action'], s['matched_text']))
    return steps

def write_ritual_steps(out_path: Path, steps: List[Dict[str, Any]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        for s in steps:
            f.write(json.dumps(s, sort_keys=True) + '\n')

__all__ = ['extract_ritual_steps', 'write_ritual_steps']

if __name__ == '__main__':  # Manual debug helper
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--chunks', default='artifacts/phase1/chunks.jsonl')
    ap.add_argument('--lexicon', default='lexicons/ritual_actions.yaml')
    ap.add_argument('--out', default='artifacts/phase3/ritual_steps.jsonl')
    args = ap.parse_args()
    steps = extract_ritual_steps(Path(args.chunks), Path(args.lexicon))
    write_ritual_steps(Path(args.out), steps)
    print(f"Wrote {len(steps)} ritual steps -> {args.out}")

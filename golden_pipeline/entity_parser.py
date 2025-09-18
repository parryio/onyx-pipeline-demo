"""Offline Entity Parser (Lexicon-Driven)

Deterministically parses entities from Phase 1 chunks using curated lexicon YAMLs.
Optionally enriches / augments with cache-derived semantic entities when cache items
are supplied, but lexicon extraction is primary and required for Phase 3.

Entity Record Schema (target for entities.jsonl):
    {
        "entity_id": str,            # ent_<sha256[:16]> of type|norm_value
        "raw_value": str,            # Exact surface form matched in chunk text
        "norm_value": str,           # Canonical form from lexicon
        "type": str,                 # Category/type from lexicon file
        "source_chunk_id": str,      # chunk_id from phase1/chunks.jsonl
        "char_start": int,           # Inclusive character offset in chunk text
        "char_end": int              # Exclusive character offset in chunk text
    }

Determinism Principles:
    - Lexicon files are loaded in sorted path order; each term expanded into pattern list.
    - Case-insensitive matching but original surface form is preserved as raw_value.
    - Overlapping matches are resolved by longest-span-first then left-to-right.
    - entity_id computed from (type + norm_value) ONLY (not raw surface) to collapse variants.
    - Multiple raw surface occurrences of the same canonical entity in different chunks will
        repeat the entity_id (traceability preserved via source_chunk_id + spans).
"""
from __future__ import annotations
import json, hashlib, re, yaml
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass


@dataclass(frozen=True)
class LexTerm:
    type: str
    canonical: str
    patterns: List[str]  # ordered list of regex-safe literal patterns (variants + canonical)


LEXICON_CACHE: Dict[Path, List[LexTerm]] = {}


def build_entities_from_lexicons(chunks_path: Path, lexicon_dir: Path) -> List[Dict[str, Any]]:
    """Primary deterministic lexicon-driven extraction."""
    lex_terms = _load_lexicons(lexicon_dir)
    entities: List[Dict[str, Any]] = []
    with open(chunks_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            ch = json.loads(line)
            text = ch.get('text', '')
            matches = _match_terms(text, lex_terms)
            for mt in matches:
                entity_id = _entity_id(mt.type, mt.canonical)
                entities.append({
                    'entity_id': entity_id,
                    'raw_value': text[mt.char_start:mt.char_end],
                    'norm_value': mt.canonical,
                    'type': mt.type,
                    'source_chunk_id': ch['chunk_id'],
                    'char_start': mt.char_start,
                    'char_end': mt.char_end
                })
    entities.sort(key=lambda e: (e['entity_id'], e['source_chunk_id'], e['char_start']))
    return entities


def build_entities(chunks_path: Path, cache_items: List[Dict[str, Any]], lexicon_dir: Path | None = None) -> List[Dict[str, Any]]:
    """Composite builder: lexicon extraction + (optional) cache semantic entities.

    cache_items currently ignored for semantic augmentation until schema extended.
    The function preserves signature compatibility with existing orchestrator calls.
    """
    entities = []
    if lexicon_dir and lexicon_dir.exists():
        entities.extend(build_entities_from_lexicons(chunks_path, lexicon_dir))
    # Placeholder: possible future merge of cache-derived entities.
    # Deterministic ordering ensured by lexicon builder already.
    return entities


def _entity_id(etype: str, norm_value: str) -> str:
    slug = _slugify(etype)
    base = f"{slug}|{norm_value}".lower()
    h = hashlib.sha256(base.encode('utf-8')).hexdigest()[:12]
    return f'ent_{slug}_{h}'


def _sha256(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _prompt_template() -> str:
    return "EXTRACT_ENTITIES_V1"


# --- Lexicon support -------------------------------------------------------

@dataclass
class _SpanMatch:
    type: str
    canonical: str
    char_start: int
    char_end: int


def _load_lexicons(directory: Path) -> List[LexTerm]:
    if directory in LEXICON_CACHE:
        return LEXICON_CACHE[directory]
    terms: List[LexTerm] = []
    if not directory.exists():
        return []
    for path in sorted(directory.glob('*.yaml')):
        try:
            data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        except Exception:
            continue
        # Only process dicts that contain a 'terms' key; skip other lexicon-like files
        if not isinstance(data, dict) or 'terms' not in data:
            continue
        for term in (data.get('terms') or []):
            canonical = str(term.get('canonical','')).strip()
            if not canonical:
                continue
            variants = term.get('variants') or []
            pats = [canonical] + [v for v in variants if v]
            # Deduplicate preserving order
            seen = set()
            dedup: List[str] = []
            for p in pats:
                pl = p.lower()
                if pl in seen:
                    continue
                seen.add(pl)
                dedup.append(p)
            terms.append(LexTerm(type=str(term.get('category','unknown')).strip(), canonical=canonical, patterns=dedup))
    LEXICON_CACHE[directory] = terms
    return terms


def _slugify(s: str) -> str:
    out = re.sub(r'[^a-zA-Z0-9]+', '-', s.lower()).strip('-')
    return out or 'x'


def _match_terms(text: str, terms: List[LexTerm]) -> List[_SpanMatch]:
    lowered = text.lower()
    raw_matches: List[Tuple[int,int,LexTerm,str]] = []
    for t in terms:
        for pat in t.patterns:
            # Simple literal search (case-insensitive) - could upgrade to regex if wildcards added.
            pl = pat.lower()
            start = 0
            while True:
                idx = lowered.find(pl, start)
                if idx == -1:
                    break
                raw_matches.append((idx, idx+len(pl), t, t.canonical))
                start = idx + len(pl)
    # Resolve overlaps: longest span first then left-to-right
    raw_matches.sort(key=lambda m: (-(m[1]-m[0]), m[0]))
    accepted: List[_SpanMatch] = []
    occupied = []  # list of (start,end)
    for s,e,t,_canon in raw_matches:
        if any(not (e <= os or s >= oe) for os,oe in occupied):
            continue
        occupied.append((s,e))
        accepted.append(_SpanMatch(type=t.type, canonical=t.canonical, char_start=s, char_end=e))
    # Return in document order
    accepted.sort(key=lambda m: m.char_start)
    return accepted

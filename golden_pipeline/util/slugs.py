"""Canonical slug utilities for domains & ritual actions.

Single source of truth for normalization so Phase 3, Phase 4 assembler, gates
and evaluation all reason over identical identifiers.
"""
from __future__ import annotations
from typing import Dict

DOMAIN_ALIASES: Dict[str, str] = {
    'gd': 'golden_dawn',
    'golden-dawn': 'golden_dawn',
    'golden_dawn': 'golden_dawn',
}

ACTION_ALIASES: Dict[str, str] = {
    # Core Golden Dawn actions
    'qabalistic cross': 'qabalistic_cross',
    'qabalistic-cross': 'qabalistic_cross',
    'qabalistic_cross': 'qabalistic_cross',  # already canonical form
    'qabalisticcross': 'qabalistic_cross',   # safety alias without space
    'kaballistic cross': 'qabalistic_cross',
    'vibrate': 'vibrate',
    'vibrate the': 'vibrate',
    'intone': 'intone',
    'intones': 'intone',
    'intoned': 'intone',
    'assume-godform': 'assume_godform',
    'assumes the godform': 'assume_godform',
    'assume the godform': 'assume_godform',
    'assume godform': 'assume_godform',
    'banish': 'banish',
    'banishing': 'banish',
    'banished': 'banish',
    'invoking ritual': 'invoking_ritual',
    'invoking-ritual': 'invoking_ritual',
    # Middle Pillar vocabulary
    'relax': 'relax',
    'relaxation': 'relax',
    'visualize': 'visualize',
    'visualise': 'visualize',
    'formulate pillar': 'formulate_pillar',
    'formulate the pillar': 'formulate_pillar',
    'formulate a pillar': 'formulate_pillar',
    'circulate light': 'circulate_light',
    'circulation of light': 'circulate_light',
    'circulation of the light': 'circulate_light',
    'ground': 'ground',
    'grounding': 'ground',
}

def canon_domain(raw: str | None) -> str | None:
    if not raw:
        return raw
    key = raw.strip().lower().replace(' ', '_')
    return DOMAIN_ALIASES.get(key, key)

def canon_action(raw: str | None) -> str | None:
    if not raw:
        return raw
    key = raw.strip().lower().replace('-', ' ')
    if key in ACTION_ALIASES:
        return ACTION_ALIASES[key]
    key2 = key.replace(' ', '_')
    return ACTION_ALIASES.get(key2, key2)

__all__ = ['canon_domain', 'canon_action']

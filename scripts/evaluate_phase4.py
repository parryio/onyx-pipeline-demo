"""Phase 4 Evaluation Harness

Computes fidelity scores of generated LEAN kits against checked-in gold standards.
Metrics:
  - Coverage@Gold: proportion of gold step actions appearing in generated
    sequence in correct relative order (greedy subsequence match).
  - Order τ (tau-like): pairwise ordering agreement ratio for actions present
    in both sequences (values in [0,1]).

Exit code non-zero if any evaluated kit scores < threshold (default 0.95).
"""
from __future__ import annotations
import json, sys, os
from pathlib import Path
from typing import List, Tuple
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from golden_pipeline.util.slugs import canon_action

THRESHOLD = 0.95

def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def _extract_actions(lean_obj: dict) -> List[str]:
    steps = lean_obj.get('lean_steps') or []
    return [canon_action(s.get('action')) for s in steps if s.get('action')]

def coverage_at_gold(gold: List[str], generated: List[str]) -> float:
    if not gold:
        return 1.0  # vacuous
    gi = 0
    matched = 0
    for a in gold:
        while gi < len(generated) and generated[gi] != a:
            gi += 1
        if gi < len(generated) and generated[gi] == a:
            matched += 1
            gi += 1
    return matched / len(gold)

def order_tau(gold: List[str], generated: List[str]) -> float:
    # Consider only actions appearing in both sequences at least once.
    gold_positions = {}
    for idx, a in enumerate(gold):
        if a not in gold_positions:
            gold_positions[a] = idx
    gen_positions = {}
    for idx, a in enumerate(generated):
        if a not in gen_positions:
            gen_positions[a] = idx
    common = [a for a in gold_positions if a in gen_positions]
    n = len(common)
    if n == 0:
        return 0.0
    if n < 2:
        return 1.0
    concordant = 0
    discordant = 0
    for i in range(n):
        for j in range(i+1, n):
            a, b = common[i], common[j]
            gold_order = gold_positions[a] < gold_positions[b]
            gen_order = gen_positions[a] < gen_positions[b]
            if gold_order == gen_order:
                concordant += 1
            else:
                discordant += 1
    denom = concordant + discordant
    return concordant / denom if denom else 1.0

def evaluate(artifacts_dir: str = 'artifacts') -> int:
    phase4_dir = Path(artifacts_dir) / 'phase4'
    gold_dir = phase4_dir / 'gold'
    kits_dir = phase4_dir / 'kits'
    if not gold_dir.exists():
        print("No gold directory present; skipping evaluation (PASS by default).")
        return 0
    failures = 0
    for gold_file in gold_dir.glob('*.kit.lean.json'):
        kit_id = gold_file.stem.replace('.kit.lean','')
        generated_file = kits_dir / f"{kit_id}.kit.lean.json"
        if not generated_file.exists():
            print(f"[FAIL] Generated lean kit missing for gold {kit_id}")
            failures += 1
            continue
        gold_obj = _load_json(gold_file)
        gen_obj = _load_json(generated_file)
        gold_actions = _extract_actions(gold_obj)
        gen_actions = _extract_actions(gen_obj)
        cov = coverage_at_gold(gold_actions, gen_actions)
        tau = order_tau(gold_actions, gen_actions)
        print(f"Kit {kit_id} Coverage@Gold={cov:.3f} OrderTau={tau:.3f}")
        if cov < THRESHOLD or tau < THRESHOLD:
            print(f"  [FAIL] Fidelity below threshold ({THRESHOLD}) for kit {kit_id}")
            failures += 1
    return 1 if failures else 0

if __name__ == '__main__':
    artifacts_dir = 'artifacts'
    if len(sys.argv) > 1:
        artifacts_dir = sys.argv[1]
    rc = evaluate(artifacts_dir)
    sys.exit(rc)

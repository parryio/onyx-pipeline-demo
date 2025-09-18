"""Thin wrapper for invoking the canonical Phase 1 gate.

Retained for compatibility with existing CI workflow commands.
"""

import sys
from onyx_scribe.phase1_gate import verify_phase1_artifacts, GateError

if __name__ == "__main__":
    artifacts_root = "artifacts"
    if len(sys.argv) > 1:
        artifacts_root = sys.argv[1]
    try:
        verify_phase1_artifacts(artifacts_root)
    except GateError as e:
        print(f"Phase 1 gate failed: {e}", file=sys.stderr)
        sys.exit(1)

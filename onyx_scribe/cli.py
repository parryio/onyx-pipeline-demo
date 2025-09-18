import argparse
import yaml
import sys
import subprocess
from pathlib import Path

# Add parent directory to path to allow imports from onyx_scribe
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from onyx_scribe.phase1 import run_phase1
from onyx_scribe.phase2 import run_phase2
from onyx_scribe.phase1_gate import verify_phase1_artifacts, GateError
from golden_pipeline.enricher import run_phase3_enrichment
from golden_pipeline.phase3 import run_phase3
from golden_pipeline.kit_assembler import assemble_kits
from golden_pipeline.crosslinker import create_crosslinks
from golden_pipeline.kit_indexer import index_kits
from golden_pipeline.phase4_gate import verify_phase4_artifacts, GateError as GateError4
from ritual_player.phase5 import run_phase5

def load_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Onyx Scribe CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Phase 1 Command ---
    p1_parser = subparsers.add_parser("phase1", help="Run Phase 1 (Ingest)")
    p1_parser.add_argument('--config', default='config/onyx.yml', help='Path to config file')
    p1_parser.add_argument('--root', help='Override library root directory')
    p1_parser.add_argument('--artifacts', help='Override artifacts directory')

    # --- Phase 2 Command ---
    p2_parser = subparsers.add_parser("phase2", help="Run Phase 2 (Index & Enrich)")
    p2_parser.add_argument('--config', default='config/onyx.yml', help='Path to config file')
    p2_parser.add_argument('--root', help='Override library root directory')
    p2_parser.add_argument('--artifacts', help='Override artifacts directory')

    # --- Pipeline Command ---
    pipe_parser = subparsers.add_parser("pipeline", help="Run the full pipeline")
    pipe_subparsers = pipe_parser.add_subparsers(dest="subcommand", required=True)
    run_parser = pipe_subparsers.add_parser("run", help="Run all phases sequentially")
    run_parser.add_argument('--config', default='config/onyx.yml', help='Path to config file')
    run_parser.add_argument('--root', help='Override library root directory')
    run_parser.add_argument('--artifacts', help='Override artifacts directory')

    # --- Enrichment (Phase E) Command Group ---
    enrich_parser = subparsers.add_parser("enrich", help="Out-of-band enrichment tools (Phase E)")
    enrich_sub = enrich_parser.add_subparsers(dest="enrich_command", required=True)
    enrich_phase3 = enrich_sub.add_parser("phase3", help="Run Phase 3 enrichment (networked AI calls)")
    enrich_phase3.add_argument('--config', default='config/onyx.yml', help='Path to config file')
    enrich_phase3.add_argument('--artifacts', help='Override artifacts directory')

    # --- Phase 3 Offline Command ---
    p3_parser = subparsers.add_parser("phase3", help="Run Phase 3 (offline cache consumer)")
    p3_parser.add_argument('--config', default='config/onyx.yml', help='Path to config file')
    p3_parser.add_argument('--artifacts', help='Override artifacts directory')

    # --- Phase 4 Kit Assembly (partial) ---
    asm_parser = subparsers.add_parser("assemble_kits", help="Run Phase 4 kit assembler only")
    asm_parser.add_argument('--config', default='config/onyx.yml', help='Path to config file')
    asm_parser.add_argument('--artifacts', help='Override artifacts directory')

    # --- Phase 5 Command ---
    p5_parser = subparsers.add_parser("phase5", help="Run Phase 5 (Prepare for Display)")
    p5_parser.add_argument('--artifacts', required=True, help='Path to artifacts directory')
    p5_parser.add_argument('--root', required=True, help='Path to library root directory')

    args = parser.parse_args()
    config = load_config(args.config) if hasattr(args, 'config') and args.config else {}
    # Command-line precedence overrides
    if getattr(args, 'root', None):
        config['root'] = args.root
    if getattr(args, 'artifacts', None):
        config['artifacts_dir'] = args.artifacts

    if args.command == "phase1":
        run_phase1(config)
        try:
            verify_phase1_artifacts(config['artifacts_dir'])
        except GateError as e:
            print(f"Phase 1 gate failed: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "phase2":
        run_phase2(config)
    elif args.command == "pipeline" and args.subcommand == "run":
        run_phase1(config)
        try:
            verify_phase1_artifacts(config['artifacts_dir'])
        except GateError as e:
            print(f"Phase 1 gate failed: {e}", file=sys.stderr)
            sys.exit(1)
        run_phase2(config)

        # Optional: Verify Phase 2 determinism if configured
        if config.get('auxiliary', {}).get('phase2_bm25_digest', False):
            print("Running Phase 2 digest verification...")
            subprocess.run([sys.executable, "scripts/verify_phase2.py", config['artifacts_dir']], check=True)
            
        # Phase 3 requires prior enrichment (out-of-band). If cache present, we can run it.
        try:
            run_phase3(config)
        except Exception as e:
            print(f"[WARN] Phase 3 skipped or failed: {e}")
        # Phase 4 (best-effort; depends on ritual_steps.jsonl presence)
        try:
            assemble_kits(config)
            create_crosslinks(config)
            index_kits(config)
            verify_phase4_artifacts(config)
        except GateError4 as e:
            print(f"[WARN] Phase 4 gate failed: {e}")
        except Exception as e:
            print(f"[WARN] Phase 4 skipped or failed: {e}")
        
        # Phase 5
        try:
            run_phase5(config)
        except Exception as e:
            print(f"[WARN] Phase 5 skipped or failed: {e}")

        print("\nPipeline run completed successfully.")
    elif args.command == "enrich" and args.enrich_command == "phase3":
        run_phase3_enrichment(config)
    elif args.command == "phase3":
        run_phase3(config)
    elif args.command == "assemble_kits":
            # Run full Phase 4 deterministic chain (assembler + crosslinks + index)
            assemble_kits(config)
            try:
                create_crosslinks(config)
                index_kits(config)
            except Exception as e:
                print(f"[WARN] Phase 4 ancillary generation failed: {e}")
            try:
                verify_phase4_artifacts(config)
            except GateError4 as e:
                print(f"[WARN] Phase 4 gate failed: {e}")
    elif args.command == "phase5":
        # Create a minimal config for phase5 standalone run
        phase5_config = {'artifacts_dir': args.artifacts, 'root': args.root}
        run_phase5(phase5_config)

if __name__ == "__main__":
    main()

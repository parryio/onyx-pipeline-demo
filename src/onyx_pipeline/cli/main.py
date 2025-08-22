from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import PipelineConfig
from ..orchestrator import Orchestrator
from ..validate.validator import validate
from .inspect import inspect_doc


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--lib", required=True, help="Library root of source documents")
    p.add_argument("--out", required=True, help="Output root directory")
    p.add_argument("--ocr-lang", default="eng")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="onyx-pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_manifest = sub.add_parser("build", help="Build manifest (alias: onyx-manifest build)")
    _add_common(p_manifest)

    p_run = sub.add_parser("run", help="Run full safe pipeline")
    _add_common(p_run)
    p_run.add_argument("--include-images", action="store_true", help="Harvest PDF images (stub)")

    p_val = sub.add_parser("validate", help="Validate outputs")
    p_val.add_argument("--out", required=True)

    p_inspect = sub.add_parser("inspect-doc", help="Inspect a document by id")
    p_inspect.add_argument("--out", required=True)
    p_inspect.add_argument("--doc-id", required=True)
    p_inspect.add_argument("--max-chunks", type=int, default=5)

    args = parser.parse_args(argv)

    if args.cmd == "build":
        cfg = PipelineConfig(lib_root=Path(args.lib), out_root=Path(args.out))
        orch = Orchestrator(cfg)
        orch.build_manifest()
        return 0
    if args.cmd == "run":
        summary = Orchestrator.run(Path(args.lib), Path(args.out), ocr_lang=args.ocr_lang, include_images=args.include_images)
        if summary["stats"].get("error_count", 0) > 0:
            return 2
        return 0
    if args.cmd == "validate":
        rep = validate(Path(args.out))
        print(rep)
        if rep.get("error_count", 0) > 0:
            return 3
        return 0
    if args.cmd == "inspect-doc":
        rep = inspect_doc(Path(args.out), args.doc_id, max_chunks=args.max_chunks)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 1

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

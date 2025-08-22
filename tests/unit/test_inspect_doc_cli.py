from __future__ import annotations
from pathlib import Path
import json
from onyx_pipeline.orchestrator import Orchestrator
from onyx_pipeline.cli.main import main as cli_main
from onyx_pipeline.storage import paths

def test_inspect_doc_cli(tmp_path: Path):
    lib = tmp_path / "lib"; out = tmp_path / "out"
    lib.mkdir()
    sample = lib / "doc.txt"
    sample.write_text("hello world", encoding="utf-8")
    summary = Orchestrator.run(lib, out)
    # find doc id from metas index
    metas = paths.metas_index_path(out)
    first_line = metas.read_text(encoding="utf-8").splitlines()[0]
    doc_id = json.loads(first_line)["doc_id"]
    # invoke inspect CLI
    rc = cli_main(["inspect-doc", "--out", str(out), "--doc-id", doc_id])
    assert rc == 0

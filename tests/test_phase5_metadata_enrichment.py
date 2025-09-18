import json
import subprocess
import sys
from pathlib import Path


def read_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            data = line.strip()
            if data:
                rows.append(json.loads(data))
    return rows


def test_ui_generator_and_search_exporter_enrich_metadata(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    artifacts = tmp_path / "artifacts"
    kits_dir = artifacts / "phase4" / "kits"
    kits_dir.mkdir(parents=True)

    kit_payload = {
        "id": "demo-kit",
        "name": "Demo Kit",
        "keywords": ["banishing", "light"],
        "tags": ["banishing", "light"],
        "source_doc_ids": ["doc_aaaaaaaaaaaa"],
        "step_ids": ["rit_step1", "rit_step2"],
        "steps": [
            {
                "step_id": "demo-kit_00001",
                "ritual_step_id": "rit_step1",
                "matched_text": "Perform the cross",
                "keywords": ["cross"],
                "source_doc_id": "doc_aaaaaaaaaaaa",
                "source_chunk_id": "doc_aaaaaaaaaaaa_00001",
                "char_start": 0,
                "char_end": 18,
            },
            {
                "ritual_step_id": "rit_step2",
                "matched_text": "Invoke the light",
                "keywords": ["banishing", "light"],
                "source_doc_id": "doc_aaaaaaaaaaaa",
                "source_chunk_id": "doc_aaaaaaaaaaaa_00002",
                "char_start": 19,
                "char_end": 35,
            },
        ],
    }
    (kits_dir / "demo-kit.kit.json").write_text(json.dumps(kit_payload), encoding="utf-8")

    py = sys.executable
    subprocess.run(
        [py, "ritual_player/ui_data_generator.py", "--artifacts", str(artifacts)],
        check=True,
        cwd=repo_root,
    )

    catalog_rows = read_jsonl(artifacts / "phase5" / "ui_catalog.jsonl")
    assert len(catalog_rows) == 1
    catalog_row = catalog_rows[0]

    assert catalog_row["kit_id"] == "demo-kit"
    assert catalog_row["tags"] == ["banishing", "light"]
    assert catalog_row["n_steps"] == 2

    step_one, step_two = catalog_row["steps"]
    assert step_one["text"] == "Perform the cross"
    assert step_one["tags"] == ["cross"]
    assert step_one["step_id"] == "demo-kit_00001"
    assert step_one["ritual_step_id"] == "rit_step1"

    assert step_two["text"] == "Invoke the light"
    assert step_two["tags"] == ["banishing", "light"]
    assert step_two["step_id"] == "rit_step2"
    assert step_two["ritual_step_id"] == "rit_step2"

    subprocess.run(
        [py, "ritual_player/search_exporter.py", "--artifacts", str(artifacts)],
        check=True,
        cwd=repo_root,
    )

    search_bundle_path = artifacts / "phase5" / "ui_search.minisearch.json"
    bundle = json.loads(search_bundle_path.read_text(encoding="utf-8"))
    assert bundle["docs"], "search exporter should emit docs"
    doc = bundle["docs"][0]
    assert doc["id"] == "demo-kit"
    assert doc["tags"] == ["banishing", "cross", "light"]
    assert doc["n_steps"] == 2
    assert "Perform the cross" in doc["text"]
    assert "Invoke the light" in doc["text"]

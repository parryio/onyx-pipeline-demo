import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_yaml_stub():
    if 'yaml' in sys.modules:
        return

    def _safe_load(stream):
        data = stream.read() if hasattr(stream, 'read') else stream
        if not data:
            return None
        text = data.strip()
        if not text:
            return None
        return json.loads(text)

    yaml_stub = types.ModuleType('yaml')
    yaml_stub.safe_load = _safe_load
    sys.modules['yaml'] = yaml_stub


_ensure_yaml_stub()

from golden_pipeline.kit_assembler import assemble_kits


def _write_jsonl(path: Path, rows):
    with open(path, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')


def test_source_doc_titles_populated_from_metadata(tmp_path):
    artifacts = tmp_path / 'artifacts'
    phase3 = artifacts / 'phase3'
    phase3.mkdir(parents=True)

    ritual_steps = [
        {
            'ritual_step_id': 'step_001',
            'source_doc_id': 'doc_aaaaaaaaaaaa',
            'action': 'banish',
            'chunk_seq': 1,
            'char_start': 0,
            'char_end': 10,
            'source_chunk_id': 'chunk-1',
        }
    ]
    _write_jsonl(phase3 / 'ritual_steps.jsonl', ritual_steps)

    doc_metadata = [
        {
            'doc_id': 'doc_aaaaaaaaaaaa',
            'path': 'Library/Collection/DocTitle.txt',
            'metadata': {
                'collection': 'Collection',
                'title': 'Doc Title',
            },
        }
    ]
    _write_jsonl(phase3 / 'doc_metadata.jsonl', doc_metadata)

    lexicons_dir = tmp_path / 'lexicons'
    lexicons_dir.mkdir()
    kit_manifest = [
        {
            'kit_id': 'collection-ritual',
            'kit_name': 'Collection Ritual',
            'source_doc_ids': ['doc_aaaaaaaaaaaa'],
        }
    ]
    with open(lexicons_dir / 'kit_manifest.yaml', 'w', encoding='utf-8') as f:
        json.dump(kit_manifest, f)

    config = {
        'artifacts_dir': str(artifacts),
        'paths': {
            'lexicons': str(lexicons_dir),
        },
    }

    assemble_kits(config)

    raw_kit_path = artifacts / 'phase4' / 'kits' / 'collection-ritual.kit.json'
    with open(raw_kit_path, 'r', encoding='utf-8') as f:
        kit = json.load(f)

    assert kit['source_doc_ids'] == ['doc_aaaaaaaaaaaa']
    assert kit['source_doc_titles'] == ['Doc Title']

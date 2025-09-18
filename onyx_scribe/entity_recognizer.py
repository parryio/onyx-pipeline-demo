import json
import re
from pathlib import Path

def recognize_entities(config):
    """
    Creates a raw entity index using deterministic, rule-based methods.
    """
    print("Recognizing entities...")
    phase1_dir = Path(config['paths']['artifacts_phase1'])
    phase2_dir = Path(config['paths']['artifacts_phase2'])
    phase2_dir.mkdir(exist_ok=True)

    chunks_path = phase1_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"{chunks_path} not found. Run Phase 1 first.")

    with open(chunks_path, 'r', encoding='utf-8') as f:
        chunks = [json.loads(line) for line in f]

    entity_index = []
    # Simple rule: find all-caps words between 3 and 30 chars long, not purely numeric
    entity_regex = re.compile(r'\b[A-Z][A-Z0-9]{2,29}\b')

    for chunk in chunks:
        text = chunk['text']
        found_entities = entity_regex.findall(text)
        for entity_text in found_entities:
            if not entity_text.isnumeric():
                entity_index.append({
                    "entity_text": entity_text,
                    "source_chunk_id": chunk['chunk_id'],
                    "doc_id": chunk['doc_id']
                })

    # Sort for deterministic output
    entity_index.sort(key=lambda x: (x['source_chunk_id'], x['entity_text']))

    entity_index_path = phase2_dir / "entity_index.jsonl"
    with open(entity_index_path, 'w', encoding='utf-8', newline='\n') as f:
        for item in entity_index:
            f.write(json.dumps(item, sort_keys=True) + '\n')

    print(f"Entity index written to {entity_index_path}")

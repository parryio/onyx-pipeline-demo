import json
from pathlib import Path
import re

def build_search_index(config):
    """
    Builds a deterministic, JSON-based search index from chunks.
    """
    print("Building search index...")
    phase1_dir = Path(config['paths']['artifacts_phase1'])
    phase2_dir = Path(config['paths']['artifacts_phase2'])
    search_dir = phase2_dir / "search"
    search_dir.mkdir(exist_ok=True, parents=True)

    chunks_path = phase1_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"{chunks_path} not found. Run Phase 1 first.")

    with open(chunks_path, 'r', encoding='utf-8') as f:
        chunks = [json.loads(line) for line in f]

    # Simple inverted index
    index = {}
    for chunk in chunks:
        chunk_id = chunk['chunk_id']
        text = chunk['text']
        # Simple tokenizer: lowercase and split on non-alphanumeric characters
        tokens = set(re.split(r'\W+', text.lower()))
        for token in tokens:
            if token:
                if token not in index:
                    index[token] = []
                index[token].append(chunk_id)
    
    # Sort for determinism
    for token in index:
        index[token].sort()

    # Per PDR, the file is named bm25.index, but we are creating a JSON index.
    index_path = search_dir / "bm25.index"
    with open(index_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(index, f, sort_keys=True)

    print(f"Search index written to {index_path}")

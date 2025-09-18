import json
import hashlib
from pathlib import Path

class CacheManager:
    def __init__(self, cache_path):
        self.cache_path = Path(cache_path)
        self._cache = self._load_cache()

    def _load_cache(self):
        if not self.cache_path.exists():
            return {}
        with open(self.cache_path, 'r', encoding='utf-8') as f:
            return {item['request_hash']: item for item in (json.loads(line) for line in f)}

    def get(self, chunk_hash, parser_type):
        request_hash = self._get_request_hash(chunk_hash, parser_type)
        return self._cache.get(request_hash)

    def set(self, chunk_hash, parser_type, result):
        request_hash = self._get_request_hash(chunk_hash, parser_type)
        item = {
            "request_hash": request_hash,
            "parser_type": parser_type,
            "chunk_hash": chunk_hash,
            "result": result
        }
        self._cache[request_hash] = item
        with open(self.cache_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(item, sort_keys=True) + '\n')

    def _get_request_hash(self, chunk_hash, parser_type):
        return hashlib.sha256(f"{chunk_hash}:{parser_type}".encode('utf-8')).hexdigest()

# --- New Phase 3 cache helpers (deterministic, composite key sorted) ---

def write_cache(results, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # deterministic sort before writing
    results_sorted = sorted(results, key=lambda r: (r['chunk_hash'], r['prompt_hash']))
    with open(path, 'w', encoding='utf-8') as f:
        for item in results_sorted:
            f.write(json.dumps(item, sort_keys=True) + '\n')


def read_cache(path: Path):
    items = []
    if not path.exists():
        return items
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items

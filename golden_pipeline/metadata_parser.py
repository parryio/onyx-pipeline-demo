"""
Phase 3: Metadata Parser

This script is the first step in Phase 3 of the OnyxHall pipeline.
It reads the canonical manifest from Phase 1 and parses the file paths
to extract structured metadata based on configurable rules.

Input: artifacts/phase1/manifest.jsonl
Output: artifacts/phase3/doc_metadata.jsonl

The output is a JSONL file where each line is a dictionary containing:
- doc_id: The document ID from the manifest.
- path: The original file path.
- metadata: A dictionary of extracted tags (e.g., author, collection).

The script is designed to be deterministic and idempotent.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Configuration ---

# This configuration would ideally be loaded from a YAML file (e.g., onyx.yml)
# For this implementation, it's defined directly in the script.
# Updated rule set: we expand to cover patterns observed in corpus.
# Order: most specific -> least specific.
METADATA_EXTRACTION_RULES = [
    {
        "name": "Year-Author-Title (top-level collection as tradition)",
        "pattern": re.compile(r"^(?P<tradition>[^/]+)/(?P<year>\d{4})-(?P<author>[A-Za-z .']+?)-(?P<title>[^/]+?)\.(?P<ext>[^.]+)$"),
        "defaults": {"topic": "Uncategorized"}
    },
    {
        "name": "Author-Title dash (top-level collection as tradition)",
        "pattern": re.compile(r"^(?P<tradition>[^/]+)/(?P<author>[^/]+?) - (?P<title>[^/]+?)\.(?P<ext>[^.]+)$"),
        "defaults": {"topic": "Uncategorized"}
    },
    {
        "name": "Author-Title plain (top-level collection as tradition)",
        "pattern": re.compile(r"^(?P<tradition>[^/]+)/(?P<author>[^/]+?) (?P<title>[^/]+?)\.(?P<ext>[^.]+)$"),
        "defaults": {"topic": "Uncategorized"}
    },
    {
        "name": "Collection + Title only (treat collection as tradition)",
        "pattern": re.compile(r"^(?P<tradition>[^/]+)/(?P<title>[^/]+?)\.(?P<ext>[^.]+)$"),
        "defaults": {"author": "Unknown", "topic": "Uncategorized"}
    }
]

# --- Helper Functions ---

def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Loads a JSONL file into a list of dictionaries."""
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def _write_jsonl(path: Path, data: List[Dict[str, Any]]):
    """Writes a list of dictionaries to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, sort_keys=True) + '\n')

def parse_metadata(path_str: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse a file path into structured metadata using heuristics.

    Enhancements:
    - Detect year prefix and drop from user-facing title.
    - Normalize author capitalization.
    - Treat top-level directory as tradition when no explicit tradition segment.
    - Produce authors/traditions arrays for downstream phases.
    """
    for rule in rules:
        m = rule["pattern"].match(path_str)
        if not m:
            continue
        md = rule.get("defaults", {}).copy()
        md.update(m.groupdict())
        # Title cleaning: drop extension marker if present
        ext = md.pop("ext", None)
        title = md.get("title") or Path(path_str).stem
        # Remove leading year+dash again defensively
        title = re.sub(r"^\d{4}[-_ ]+", "", title).strip()
        # Normalize multiple dashes/underscores to single space
        title = re.sub(r"[-_]+", " ", title).strip()
        md["title"] = title
        # Author normalization
        author = md.get("author")
        if author:
            author_clean = re.sub(r"[_-]+", " ", author).strip()
            # Title case except known uppercase sequences
            author_clean = " ".join(w if w.isupper() and len(w) <= 4 else w.capitalize() for w in author_clean.split())
            md["author"] = author_clean
        # Tradition normalization
        tradition = md.get("tradition") or md.get("collection") or md.get("tradition")
        if tradition:
            trad_clean = re.sub(r"[_-]+", " ", tradition).strip()
            trad_clean = trad_clean.title()
            md["tradition"] = trad_clean
        # Derive arrays for downstream convenience
        if author:
            md["authors"] = [md["author"]]
        else:
            md["authors"] = []
        if md.get("tradition"):
            md["traditions"] = [md["tradition"]]
        else:
            md["traditions"] = []
        return md
    # Fallback
    stem = Path(path_str).stem
    return {"title": stem, "authors": [], "traditions": [], "topic": "Uncategorized"}

# --- Main Execution ---

def main():
    """
    Main function to execute the metadata parsing process.
    """
    artifacts_dir = Path("artifacts")
    phase1_dir = artifacts_dir / "phase1"
    phase3_dir = artifacts_dir / "phase3"

    # 1. Read artifacts/phase1/manifest.jsonl
    manifest_path = phase1_dir / "manifest.jsonl"
    if not manifest_path.exists():
        print(f"Error: Manifest file not found at {manifest_path}")
        return

    manifest_data = _load_jsonl(manifest_path)

    doc_metadata_list = []

    # 2. For each document entry, parse the path string
    for entry in manifest_data:
        doc_id = entry["doc_id"]
        path_str = entry["path"]
        # 3. Parse path into metadata
        metadata = parse_metadata(path_str, METADATA_EXTRACTION_RULES)
        doc_metadata_list.append({
            "doc_id": doc_id,
            "path": path_str,
            "metadata": metadata,
            # Promote commonly used fields for Phase 5 convenience (duplicate values are acceptable)
            "title": metadata.get("title"),
            "authors": metadata.get("authors", []),
            "traditions": metadata.get("traditions", [])
        })

    # 5. Ensure the output artifact is deterministically sorted by doc_id
    doc_metadata_list.sort(key=lambda x: x["doc_id"])

    # 4. Produce a new canonical artifact: artifacts/phase3/doc_metadata.jsonl
    output_path = phase3_dir / "doc_metadata.jsonl"
    _write_jsonl(output_path, doc_metadata_list)

    print(f"Successfully created {output_path}")
    print(f"Processed {len(doc_metadata_list)} documents.")

if __name__ == "__main__":
    main()

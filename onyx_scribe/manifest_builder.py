import hashlib
from pathlib import Path
from typing import List, Dict, Any

def build_manifest(library_root: Path, patterns: List[str]) -> List[Dict[str, Any]]:
    """Discover files and build initial manifest entries with content de-duplication.

    Behavior:
      - Walks library using provided glob patterns (relative to library_root)
      - Computes SHA-256 for each candidate file
      - First occurrence of a content hash becomes the canonical manifest entry
      - Subsequent files whose content hash matches a prior file are SKIPPED and a
        console warning is emitted so the operator can optionally clean the library.

    Each manifest entry contains: doc_id (content-hash based), path (relative, posix), sha256, ext.
    The final manifest is sorted deterministically by path.
    """
    files = []
    for pat in patterns:
        files.extend(library_root.glob(pat))
    # Path-level de-dupe while preserving deterministic ordering
    uniq = sorted({f.resolve(): f for f in files}.values(), key=lambda p: str(p))

    manifest: List[Dict[str, Any]] = []
    seen_sha: Dict[str, str] = {}  # sha256 -> canonical path (posix relative)
    for f in uniq:
        if not f.is_file():
            continue
        # Skip any files inside hidden/dot directories (e.g., .quarantined)
        rel_parts = f.relative_to(library_root).parts
        if any(part.startswith('.') for part in rel_parts[:-1]):
            # Operator-facing note for transparency
            print(f"[INFO] skipped hidden-dir file: {f.relative_to(library_root).as_posix()}")
            continue
        with open(f, 'rb') as fh:
            data = fh.read()
        sha = hashlib.sha256(data).hexdigest()
        rel_path = f.relative_to(library_root).as_posix()
        if sha in seen_sha:
            # Duplicate content detected; emit explicit operator-facing warning.
            print(f"[WARNING] duplicate content skipped: {rel_path} (matches {seen_sha[sha]})")
            continue
        seen_sha[sha] = rel_path
        doc_id = f"doc_{sha[:12]}"
        manifest.append({
            "doc_id": doc_id,
            "path": rel_path,
            "sha256": sha,
            "ext": f.suffix.lower()
        })
    manifest.sort(key=lambda x: x["path"])
    return manifest

__all__ = ["build_manifest"]

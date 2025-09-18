#!/usr/bin/env python3
"""
Kit‑centric Phase 5 UI generator.

Reads Phase 4 kits only and emits deterministic Phase 5 artifacts:
- artifacts/phase5/ui_catalog.jsonl (one row per kit with normalized steps)
    Note: assets manifest is built separately by asset_manifest_builder.py

Determinism: explicit sorting and LF newlines; no randomness or clocks.
"""
from __future__ import annotations
import argparse, json, os, pathlib, hashlib
from typing import Dict, Any, List, Iterable


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_jsonl(p: pathlib.Path):
    if not p.exists():
        return
    with p.open("r", encoding="utf-8", newline="\n") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(p: pathlib.Path, rows: List[Dict[str, Any]]):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def _collect_tags(*sources: Iterable[Any]) -> List[str]:
    tags = set()
    for src in sources:
        if not src:
            continue
        iterable = [src] if isinstance(src, str) else src
        for item in iterable:
            if isinstance(item, str):
                normalized = item.strip()
                if normalized:
                    tags.add(normalized)
    return sorted(tags)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts", help="artifacts root (contains phase1..phase5)")
    args = ap.parse_args()

    ARTIFACTS = pathlib.Path(args.artifacts)
    P4 = ARTIFACTS / "phase4"
    P5 = ARTIFACTS / "phase5"
    P5.mkdir(parents=True, exist_ok=True)

    kit_index_path = P4 / "kit_index.jsonl"
    kits_dir = P4 / "kits"
    # Phase 1 media is no longer read here; assets manifest is generated
    # by ritual_player/asset_manifest_builder.py to match gate schema.

    # load kits
    kit_paths = sorted(kits_dir.glob("*.kit.json"))
    kits: List[Dict[str, Any]] = []
    for kp in kit_paths:
        try:
            kit = json.loads(kp.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Normalize kit_id from fields or filename stem; strip optional .kit suffix
        kid = kit.get("kit_id") or kit.get("id") or kp.stem
        if isinstance(kid, str) and kid.endswith(".kit"):
            kid = kid[:-4]
        kit["kit_id"] = kid
        kits.append(kit)

    # build UI catalog rows
    ui_rows: List[Dict[str, Any]] = []
    for kit in sorted(kits, key=lambda k: k.get("kit_id", "")):
        kit_id = kit["kit_id"]
        title = kit.get("title") or kit.get("name") or kit_id
        tags = _collect_tags(kit.get("tags"), kit.get("keywords"))
        source_docs = sorted(set(kit.get("source_doc_ids", [])))

        # preserve original step ordering from kit; synthesize order if missing
        steps = kit.get("steps", [])
        ui_steps = []
        for idx, s in enumerate(steps):
            media_refs = s.get("media_refs", [])
            ritual_step_id = s.get("ritual_step_id")
            step_id = s.get("step_id") or ritual_step_id or f"{kit_id}_{idx:05d}"
            step_tags = _collect_tags(s.get("tags"), s.get("keywords"))
            text_value = s.get("text") or s.get("matched_text") or ""

            ui_steps.append({
                "step_id": step_id,
                "ritual_step_id": ritual_step_id,
                "order": int(s.get("order", idx)),
                "text": text_value.strip(),
                "materials": s.get("materials", []),
                "notes": s.get("notes", ""),
                "overlay": s.get("overlay", {}),  # optional UI hints
                "duration_s": int(s.get("duration_s", 0)),  # 0 if unknown
                "media_refs": media_refs,
                "tags": step_tags,
            })

        ui_row = {
            "kind": "kit",
            "kit_id": kit_id,
            "title": title,
            "subtitle": kit.get("subtitle", ""),
            "tags": tags,
            "source_doc_ids": source_docs,
            "n_steps": len(ui_steps),
            "steps": ui_steps,
        }
        ui_rows.append(ui_row)

    # write outputs (sorted, deterministic)
    ui_rows.sort(key=lambda r: r["kit_id"])  # stable order for UI

    write_jsonl(P5 / "ui_catalog.jsonl", ui_rows)
    print(f"[phase5] wrote {len(ui_rows)} kits -> {P5.as_posix()}")


if __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = "0"
    main()


from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

def quarantine_path(out_root: Path) -> Path:
    reports = out_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports / "quarantine.jsonl"

def write_quarantine_record(out_root: Path, record: dict[str, Any]) -> None:
    rec = {"version": SCHEMA_VERSION, **record, "timestamp": time.time()}
    qp = quarantine_path(out_root)
    with qp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

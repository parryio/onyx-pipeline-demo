from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

from .events import Event


def _append_jsonl(path: Path, line: str) -> None:
    # naive append (not atomic per line, acceptable for single-process); could be optimized
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_event(ev: Event, *, events_file: Path | None = None) -> None:
    payload = ev.to_dict()
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    if events_file is not None:
        _append_jsonl(events_file, json.dumps(payload, ensure_ascii=False))


def log_events(events: Iterable[Event], *, events_file: Path | None = None) -> None:
    for ev in events:
        log_event(ev, events_file=events_file)

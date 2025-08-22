from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..chunking.schema import VERSION as CHUNK_VERSION
from ..manifest.schema import VERSION as MANIFEST_VERSION
from ..metas.schema import VERSION as META_VERSION
from .events import Event


@dataclass
class RunSummary:
    events: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    stats: dict[str, Any]
    run_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        base = asdict(self)
        return base


class SummaryBuilder:
    def __init__(self) -> None:
        self.stage_times: dict[str, float] = {}
        self._stage_start: dict[str, float] = {}
        self.warnings: list[dict[str, Any]] = []
        self.started_at = time.time()

    def stage_start(self, name: str) -> None:
        self._stage_start[name] = time.time()

    def stage_end(self, name: str) -> None:
        start = self._stage_start.get(name)
        if start is not None:
            self.stage_times[name] = time.time() - start

    def add_warning(self, kind: str, **kw) -> None:
        self.warnings.append({"kind": kind, **kw})

    def finalize(self, *, docs: int, chunks: int, validation: dict[str, Any]) -> dict[str, Any]:
        finished = time.time()
        counts = {"docs": docs, "chunks": chunks, "metas": validation.get("metas", 0)}
        q = validation.get("quarantine")
        if isinstance(q, dict) and "count" in q:
            counts["quarantine"] = q["count"]
        return {
            "version": 1,
            "schema_versions": {
                "manifest": MANIFEST_VERSION,
                "chunk": CHUNK_VERSION,
                "meta": META_VERSION,
            },
            "counts": counts,
            "timings": self.stage_times,
            "warnings": self.warnings,
            "started_at": self.started_at,
            "finished_at": finished,
            "duration_s": finished - self.started_at,
        }


def persist_run_summary(out_root: Path, summary: dict[str, Any]) -> Path:
    reports_dir = out_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    p = reports_dir / "run_summary.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return p


def build_summary(events: list[Event], *, extra_stats: dict[str, Any] | None = None, run_summary: dict[str, Any] | None = None) -> RunSummary:
    errors = [e.to_dict() for e in events if e.type.startswith("error")]
    stats: dict[str, Any] = {"event_count": len(events), "error_count": len(errors)}
    if extra_stats:
        stats.update(extra_stats)
    return RunSummary(events=[e.to_dict() for e in events], errors=errors, stats=stats, run_summary=run_summary)

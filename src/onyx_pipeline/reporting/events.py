from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Event:
    time: float
    stage: str
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def make_event(stage: str, type_: str, **payload: Any) -> Event:
    return Event(time=time.time(), stage=stage, type=type_, payload=payload)

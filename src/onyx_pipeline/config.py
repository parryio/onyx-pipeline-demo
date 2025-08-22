from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    lib_root: Path
    out_root: Path
    ocr_lang: str = "eng"
    include_images: bool = False
    seed: int = 13

    def ensure(self) -> None:
        self.out_root.mkdir(parents=True, exist_ok=True)

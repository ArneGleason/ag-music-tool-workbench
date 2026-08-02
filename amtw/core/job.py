"""Job = one run of the pipeline on one input stem.

Creates output/<name>_<timestamp>/ with numbered stage dirs so every
intermediate is kept and comparable in the report:

    00_input/    decoded 44.1k wav
    10_cleanup/  de-reverb (+ optional denoise)
    20_superres/ Apollo vocal enhancer
    30_resynth/  seed-vc self-conversion (+ chosen reference segment)
    40_final/    loudness-matched deliverable
    report/      spectrograms + report.html
    manifest.json
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .paths import OUTPUT_DIR

STAGE_DIRS = {
    "input": "00_input",
    "cleanup": "10_cleanup",
    "superres": "20_superres",
    "resynth": "30_resynth",
    "final": "40_final",
    "report": "report",
}


@dataclass
class Job:
    source: Path
    root: Path
    manifest: dict = field(default_factory=dict)

    @classmethod
    def create(cls, source: Path, name: str | None = None) -> "Job":
        stamp = time.strftime("%Y%m%d-%H%M%S")
        jobname = name or f"{source.stem}_{stamp}"
        root = OUTPUT_DIR / jobname
        root.mkdir(parents=True, exist_ok=False)
        for d in STAGE_DIRS.values():
            (root / d).mkdir()
        job = cls(source=source, root=root)
        job.manifest = {
            "source": str(source),
            "created": stamp,
            "stages": {},
        }
        job.save_manifest()
        return job

    def dir(self, stage: str) -> Path:
        return self.root / STAGE_DIRS[stage]

    def record(self, stage: str, **info) -> None:
        self.manifest["stages"][stage] = info
        self.save_manifest()

    def save_manifest(self) -> None:
        (self.root / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2), encoding="utf-8"
        )

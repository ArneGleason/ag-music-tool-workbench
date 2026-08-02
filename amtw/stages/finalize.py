"""Stage 4 — finalize: loudness-match the result to the original stem so it
drops back into the mix at the same level, and give it a stable name."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from .. import audio_utils
from ..config import PipelineCfg
from ..job import Job


def run(cfg: PipelineCfg, job: Job, in_wav: Path, original_wav: Path) -> Path:
    stage_dir = job.dir("final")
    t0 = time.time()
    suffix = "regen" if "resynth" in job.manifest["stages"] else "restored"
    final = stage_dir / f"{job.source.stem}_{suffix}.wav"
    target_sr = cfg.finalize.output_sr or None

    if cfg.finalize.match_input_loudness:
        target = audio_utils.measure_lufs(original_wav)
        audio_utils.match_lufs(in_wav, final, target, target_sr=target_sr)
    elif target_sr:
        audio_utils.resample_file(in_wav, final, target_sr)
    else:
        shutil.copy2(in_wav, final)

    job.record(
        "final",
        matched_lufs=cfg.finalize.match_input_loudness,
        output_sr=target_sr or "pipeline(44100)",
        out=str(final),
        seconds=round(time.time() - t0, 1),
    )
    return final

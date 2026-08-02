"""Stage 1 — cleanup: de-reverb (and optional denoise) via UVR VR-arch models.

Runs in-process (the orchestrator lives in the main venv, which has
audio-separator installed). VR-arch models run on torch/CUDA directly.
Model weights auto-download to the runtime model dir on first use.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..config import PipelineCfg
from ..job import Job
from ..paths import UVR_MODEL_DIR
from .common import StageError

# Output naming across UVR/roformer models: the removed component in parens
# ("(Reverb)", "(Echo)", "(No Dry)") vs the kept one ("(No Reverb)", "(Dry)").
# Exclusions first: "dry" would otherwise match inside "no dry".
_EXCLUDE_MARKERS = ("(reverb)", "(echo)", "(noise)", "(no dry)")
_KEEP_MARKERS = ("no reverb", "noreverb", "no echo", "no noise", "dry")


def _pick_kept(outputs: list[str], out_dir: Path) -> Path:
    for name in outputs:
        low = name.lower()
        if any(x in low for x in _EXCLUDE_MARKERS):
            continue
        if any(m in low for m in _KEEP_MARKERS):
            p = out_dir / Path(name).name
            if p.exists():
                return p
    raise StageError(
        f"could not identify the cleaned output among {outputs} — "
        "check stage dir and adjust _KEEP_MARKERS"
    )


def run(cfg: PipelineCfg, job: Job, in_wav: Path) -> Path:
    from audio_separator.separator import Separator

    stage_dir = job.dir("cleanup")
    t0 = time.time()

    sep = Separator(
        model_file_dir=str(UVR_MODEL_DIR),
        output_dir=str(stage_dir),
        output_format="WAV",
    )

    sep.load_model(model_filename=cfg.cleanup.dereverb_model)
    outputs = sep.separate(str(in_wav))
    current = _pick_kept(outputs, stage_dir)

    if cfg.cleanup.deecho:
        # kills short slap/early reflections the DeEcho-DeReverb pass leaves
        # behind — those can get re-rendered as literal vocal doubling by the
        # resynth stage
        sep.load_model(model_filename=cfg.cleanup.deecho_model)
        outputs = sep.separate(str(current))
        current = _pick_kept(outputs, stage_dir)

    if cfg.cleanup.denoise:
        sep.load_model(model_filename=cfg.cleanup.denoise_model)
        outputs = sep.separate(str(current))
        current = _pick_kept(outputs, stage_dir)

    job.record(
        "cleanup",
        model=cfg.cleanup.dereverb_model,
        deecho=cfg.cleanup.deecho,
        denoise=cfg.cleanup.denoise,
        out=str(current),
        seconds=round(time.time() - t0, 1),
    )
    return current

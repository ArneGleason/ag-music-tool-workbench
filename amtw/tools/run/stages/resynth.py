"""Stage 3 — neural re-synthesis: seed-vc zero-shot voice conversion in
self-conversion mode.

The performance (pitch contour, timing, phrasing) is extracted from the
cleaned stem; the timbre is cloned from a reference window of the *same*
stem (or an explicit reference file, e.g. a cleaner section of another song
by the same Suno persona). The decoder then regenerates the waveform from
scratch — separation artifacts don't survive because the output is
synthesized, not filtered.

Uses seed-vc's f0-conditioned singing model (44.1kHz, BigVGAN vocoder).
Runs as a subprocess in the seedvc venv; model weights auto-download from
HuggingFace into the runtime cache on first run (~several GB).
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from ....core.config import PipelineCfg
from ....core.job import Job
from ....core.paths import SEEDVC_DIR, YM_CKPT, YMSVC_DIR, venv_python
from ....core.reference import pick_reference
from .common import StageError, newest_wav, run_logged


def _run_seedvc(cfg: PipelineCfg, stage_dir: Path, in_wav: Path, ref: Path) -> Path:
    out_dir = stage_dir / "out"
    out_dir.mkdir(exist_ok=True)
    run_logged(
        [
            venv_python("seedvc"),
            SEEDVC_DIR / "inference.py",
            "--source", in_wav,
            "--target", ref,
            "--output", out_dir,
            "--diffusion-steps", str(cfg.resynth.diffusion_steps),
            "--length-adjust", str(cfg.resynth.length_adjust),
            "--inference-cfg-rate", str(cfg.resynth.inference_cfg_rate),
            "--f0-condition", "True",
            "--auto-f0-adjust", "False",
            "--semi-tone-shift", str(cfg.resynth.semitone_shift),
            "--fp16", "True" if cfg.resynth.fp16 else "False",
        ],
        log_path=stage_dir / "stage.log",
        cwd=SEEDVC_DIR,
    )
    return newest_wav(out_dir)


def _run_yingmusic(cfg: PipelineCfg, job: Job, stage_dir: Path, in_wav: Path, ref: Path) -> Path:
    # my_inference.py writes to ./outputs/<expname>/ relative to its repo cwd
    # (no --output arg); f0 conditioning and adaptive pitch are hardcoded on.
    if not YM_CKPT.exists():
        raise StageError(f"YingMusic checkpoint missing: {YM_CKPT}")
    expname = f"amtw_{job.root.name}"
    run_logged(
        [
            venv_python("ymsvc"),
            YMSVC_DIR / "my_inference.py",
            "--source", in_wav,
            "--target", ref,
            "--diffusion-steps", str(cfg.resynth.diffusion_steps),
            "--checkpoint", YM_CKPT,
            "--expname", expname,
            "--cuda", "0",
            "--fp16", "True" if cfg.resynth.fp16 else "False",
            "--config", YMSVC_DIR / "configs" / "YingMusic-SVC.yml",
        ],
        log_path=stage_dir / "stage.log",
        cwd=YMSVC_DIR,
    )
    produced = newest_wav(YMSVC_DIR / "outputs" / expname)
    out_dir = stage_dir / "out"
    out_dir.mkdir(exist_ok=True)
    final = out_dir / produced.name
    shutil.move(str(produced), final)
    return final


def run(cfg: PipelineCfg, job: Job, in_wav: Path) -> Path:
    stage_dir = job.dir("resynth")
    t0 = time.time()

    if cfg.resynth.reference_wav:
        ref = Path(cfg.resynth.reference_wav)
        ref_start = -1.0
    else:
        ref, ref_start = pick_reference(
            in_wav, stage_dir / "reference.wav", seconds=cfg.resynth.ref_seconds
        )

    if cfg.resynth.engine == "yingmusic":
        result = _run_yingmusic(cfg, job, stage_dir, in_wav, ref)
        engine_desc = "YingMusic-SVC full (self-conversion)"
    else:
        result = _run_seedvc(cfg, stage_dir, in_wav, ref)
        engine_desc = "seed-vc f0-conditioned (self-conversion)"

    job.record(
        "resynth",
        engine=engine_desc,
        reference=str(ref),
        reference_start_sec=round(ref_start, 2),
        diffusion_steps=cfg.resynth.diffusion_steps,
        out=str(result),
        seconds=round(time.time() - t0, 1),
    )
    return result

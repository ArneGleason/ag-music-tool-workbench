"""Stage 2 — spectral restoration: Apollo (Lew's checkpoints) via the MSST
framework (chunked inference with overlap built in). Runs as a subprocess in
the msst venv.

Two checkpoints: `vocal` (ep54, the one every vocal verdict was made on) and
`universal` (any instrument — the model MVSEP runs as "Universal Super
Resolution"). Same architecture, same plumbing; only the ckpt/config pair and
the layer count differ.

Skip-silence mode exists because sparse stems (backing vocals, sound effects)
are mostly air: processing only the active spans saves most of the GPU time,
and — more important than the time — the quiet stretches stay the *literal
original samples*, the same untouched-samples guarantee the fry tools make.
Apollo re-rendering 60 seconds of near-silence is 60 seconds of opportunity
to change the noise floor for no benefit.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import numpy as np

from ....core import audio_utils
from ....core.config import PipelineCfg
from ....core.job import Job
from ....core.paths import (APOLLO_CKPT, APOLLO_CONFIG, APOLLO_UNIVERSAL_CKPT,
                            APOLLO_UNIVERSAL_CONFIG, MSST_DIR, venv_python)
from .common import StageError, newest_wav, run_logged

# Span shaping. PAD keeps a decay that dips under the threshold attached to
# its note; MERGE_GAP stops a breath between phrases from becoming two spans
# with a splice in the middle; XFADE is where original and processed cross,
# always inside padded (sub-threshold) audio so the seam sits in near-silence.
_PAD_S = 1.0
_MERGE_GAP_S = 3.0
_XFADE_S = 0.1
# Below this fraction of skippable audio, whole-file processing wins: no
# seams at all beats a few percent of GPU time.
_MIN_SKIP_FRAC = 0.15


def _model_pair(name: str) -> tuple[Path, Path, str]:
    if name == "universal":
        if not APOLLO_UNIVERSAL_CKPT.exists() or not APOLLO_UNIVERSAL_CONFIG.exists():
            raise StageError(
                f"universal Apollo missing under {APOLLO_UNIVERSAL_CKPT.parent} — "
                "download ckpt + config_apollo.yaml from "
                "huggingface.co/ASesYusuf1/Apollo_universal_model"
            )
        return APOLLO_UNIVERSAL_CKPT, APOLLO_UNIVERSAL_CONFIG, "apollo_universal (Lew)"
    if not APOLLO_CKPT.exists() or not APOLLO_CONFIG.exists():
        raise StageError(
            f"Apollo checkpoint/config missing under {APOLLO_CKPT.parent} — "
            "run: python -m amtw doctor"
        )
    return APOLLO_CKPT, APOLLO_CONFIG, "apollo_vocals_ep54 (Lew)"


def _active_spans(x: np.ndarray, sr: int, thresh_db: float) -> list[tuple[int, int]]:
    """Sample ranges worth processing: 50 ms RMS above thresh_db, padded and
    merged. Returns [] when the whole file is below the threshold."""
    mono = x if x.ndim == 1 else x.mean(axis=1)
    hop = int(sr * 0.05)
    n = max(1, len(mono) // hop)
    frames = mono[: n * hop].reshape(n, hop)
    db = 10 * np.log10((frames ** 2).mean(axis=1) + 1e-20)
    active = db > thresh_db
    if not active.any():
        return []

    pad = int(round(_PAD_S / 0.05))
    merge = int(round(_MERGE_GAP_S / 0.05))
    idx = np.flatnonzero(active)
    spans: list[list[int]] = []
    for i in idx:
        lo, hi = max(0, int(i) - pad), min(n, int(i) + pad + 1)
        if spans and lo - spans[-1][1] < merge:
            spans[-1][1] = hi
        else:
            spans.append([lo, hi])
    return [(a * hop, min(b * hop, len(mono))) for a, b in spans]


def _run_msst(ckpt: Path, config: Path, in_dir: Path, out_dir: Path,
              log_path: Path) -> None:
    run_logged(
        [
            venv_python("msst"),
            MSST_DIR / "inference.py",
            "--model_type", "apollo",
            "--config_path", config,
            "--start_check_point", ckpt,
            "--input_folder", in_dir,
            "--store_dir", out_dir,
        ],
        log_path=log_path,
        cwd=MSST_DIR,
    )


def _seg_output(out_dir: Path, seg_stem: str) -> Path:
    # MSST nests one directory per input file: out/<stem>/restored.wav
    seg_dir = out_dir / seg_stem
    hits = sorted(seg_dir.rglob("*.wav")) if seg_dir.exists() else []
    if not hits:
        hits = [p for p in out_dir.rglob("*.wav") if seg_stem in p.stem]
    if not hits:
        raise StageError(f"no output for segment {seg_stem} in {out_dir}")
    return hits[0]


def run(cfg: PipelineCfg, job: Job, in_wav: Path) -> Path:
    stage_dir = job.dir("superres")
    t0 = time.time()

    ckpt, config, model_label = _model_pair(cfg.superres.model)

    in_dir = stage_dir / "in"
    in_dir.mkdir(exist_ok=True)
    out_dir = stage_dir / "out"
    out_dir.mkdir(exist_ok=True)
    final = stage_dir / f"{in_wav.stem}_apollo.wav"

    x, sr = audio_utils.load(in_wav)
    total = len(x)

    spans = (_active_spans(x, sr, cfg.superres.silence_db)
             if cfg.superres.skip_silence else None)

    if spans is not None and not spans:
        # nothing above the threshold at all — the honest output is the input
        shutil.copy2(in_wav, final)
        job.record("superres", model=model_label,
                   skipped="whole file below threshold",
                   out=str(final), seconds=round(time.time() - t0, 1))
        return final

    covered = sum(b - a for a, b in spans) if spans else total
    if spans is None or covered > (1 - _MIN_SKIP_FRAC) * total:
        # dense file (or skip disabled): process whole, as before
        staged = in_dir / in_wav.name
        shutil.copy2(in_wav, staged)
        _run_msst(ckpt, config, in_dir, out_dir, stage_dir / "stage.log")
        shutil.move(str(newest_wav(out_dir)), final)
        job.record("superres", model=model_label, out=str(final),
                   seconds=round(time.time() - t0, 1))
        return final

    # sparse file: each active span becomes its own input, one MSST call
    for k, (a, b) in enumerate(spans):
        audio_utils.save(in_dir / f"seg_{k:03d}.wav", x[a:b], sr)
    _run_msst(ckpt, config, in_dir, out_dir, stage_dir / "stage.log")

    out = x.copy()
    fade = int(_XFADE_S * sr)
    for k, (a, b) in enumerate(spans):
        seg, seg_sr = audio_utils.load(_seg_output(out_dir, f"seg_{k:03d}"))
        if seg_sr != sr:
            raise StageError(f"segment {k} came back at {seg_sr} Hz, expected {sr}")
        want = b - a
        if len(seg) < want:          # length drift would slip every later splice
            pad_shape = (want - len(seg),) + seg.shape[1:]
            seg = np.concatenate([seg, np.zeros(pad_shape, dtype=seg.dtype)])
        out[a:b] = seg[:want]
        # crossfade inside the padded ends, where both signals are sub-threshold
        ramp = np.arange(fade, dtype=np.float32) / fade
        if out.ndim > 1:
            ramp = ramp[:, None]
        if a > 0 and fade < want:
            out[a:a + fade] = x[a:a + fade] * (1 - ramp) + out[a:a + fade] * ramp
        if b < total and fade < want:
            out[b - fade:b] = out[b - fade:b] * (1 - ramp) + x[b - fade:b] * ramp

    audio_utils.save(final, out, sr)
    job.record(
        "superres",
        model=model_label,
        spans=len(spans),
        processed_fraction=round(covered / total, 3),
        out=str(final),
        seconds=round(time.time() - t0, 1),
    )
    return final

"""Pick the best reference window for timbre self-conversion.

seed-vc clones the target timbre from a short reference clip. For
self-conversion (same voice, cleaned) we want the window of the stem where
the vocal is most continuously present and dynamically stable — dense
singing, no long gaps, no whispered tails — so the timbre embedding is
computed from signal, not from artifacts and silence.

Scoring per sliding window:  active_fraction (how much of the window has
vocal energy) weighted with RMS stability (low variance of active-frame
levels). Deterministic, no ML, fast.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import audio_utils

FRAME = 2048
HOP = 512


def pick_reference(src: Path, out_path: Path, seconds: float = 25.0) -> tuple[Path, float]:
    """Extract the best `seconds` window of `src` to `out_path`.

    Returns (out_path, start_time_seconds).
    """
    data, sr = audio_utils.load(src)
    mono = audio_utils.to_mono(data)

    if len(mono) / sr <= seconds + 1.0:
        # Whole file is shorter than the window: use it all.
        audio_utils.save(out_path, data, sr)
        return out_path, 0.0

    # Frame RMS in dB
    n_frames = 1 + (len(mono) - FRAME) // HOP
    frames = np.lib.stride_tricks.as_strided(
        mono,
        shape=(n_frames, FRAME),
        strides=(mono.strides[0] * HOP, mono.strides[0]),
        writeable=False,
    )
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1) + 1e-12)
    rms_db = 20.0 * np.log10(rms + 1e-12)

    # "Active" = within 35 dB of the loudest frame
    active = rms_db > (rms_db.max() - 35.0)

    win_frames = max(1, int(round(seconds * sr / HOP)))
    if win_frames >= n_frames:
        audio_utils.save(out_path, data, sr)
        return out_path, 0.0

    kernel = np.ones(win_frames)
    active_frac = np.convolve(active.astype(np.float64), kernel, mode="valid") / win_frames

    # RMS stability over active parts: use rolling std of rms_db (silences clamped)
    clamped = np.where(active, rms_db, np.nan)
    stability = np.empty(n_frames - win_frames + 1)
    for i in range(0, n_frames - win_frames + 1, 16):  # stride 16 frames for speed
        w = clamped[i : i + win_frames]
        s = np.nanstd(w) if np.any(~np.isnan(w)) else 99.0
        stability[i : i + 16] = s
    stability = stability[: len(active_frac)]
    stab_score = 1.0 / (1.0 + stability / 6.0)  # ~1 when tight, ->0 when wild

    score = 0.7 * active_frac + 0.3 * stab_score
    best = int(np.argmax(score))
    start_sample = best * HOP
    end_sample = start_sample + int(seconds * sr)

    segment = data[start_sample:end_sample] if data.ndim == 1 else data[start_sample:end_sample, :]
    audio_utils.save(out_path, segment, sr)
    return out_path, start_sample / sr

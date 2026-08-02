"""Shared STFT / gating primitives.

These used to live in `defizz.py`, which meant `harmonic`, `detect` and
`remod` all imported private helpers out of a sibling *tool*. They are not
de-fizz's; they are the common vocabulary every fry tool speaks — one frame
grid, one window, one periodicity estimate — so that a gate measured by the
detector means the same thing as a gate applied by the repair.

Keep `N_FFT`/`HOP` fixed here. Two tools disagreeing about the frame grid is
the kind of bug that shows up as "the detector says fry but the repair does
nothing".
"""
from __future__ import annotations

import numpy as np

N_FFT = 2048
HOP = 512
ENV_HOP = 256


def _frames(x: np.ndarray, n: int, hop: int) -> np.ndarray:
    count = 1 + max(0, (len(x) - n) // hop)
    idx = np.arange(n)[None, :] + hop * np.arange(count)[:, None]
    return x[idx]


def _win() -> np.ndarray:
    return np.hanning(N_FFT + 1)[:N_FFT]


def _stft(x: np.ndarray) -> np.ndarray:
    return np.fft.rfft(_frames(x, N_FFT, HOP) * _win(), axis=1)


def _istft(S: np.ndarray, length: int) -> np.ndarray:
    win = _win()
    fr = np.fft.irfft(S, n=N_FFT, axis=1) * win
    out = np.zeros(length + 2 * N_FFT)
    norm = np.zeros(length + 2 * N_FFT)
    w2 = win ** 2
    for i in range(len(fr)):
        s = i * HOP
        out[s:s + N_FFT] += fr[i]
        norm[s:s + N_FFT] += w2
    return (out / np.maximum(norm, 1e-8))[:length]


def _smoothstep(x, lo, hi):
    t = np.clip((x - lo) / max(1e-9, hi - lo), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def periodicity(mono: np.ndarray, sr: int, n_frames: int) -> np.ndarray:
    """Per-frame normalised autocorrelation peak over the vocal pitch range.

    ~1 for a clean sustained note, low for fry/creak. Measured on a
    low-passed copy so the HF fizz itself cannot skew the estimate.

    Calibration that cost a round of wasted experiments: raspy *singing*
    measures ~0.70 and clean singing ~0.93 — not near zero. A gate ramping
    0.45-0.75 is therefore only ~18% open exactly where the artifact is, so
    every tool here ramps 0.60-0.92 instead. See docs/findings.md.
    """
    a = np.exp(-2.0 * np.pi * 4000.0 / sr)
    lp = mono.copy()
    for _ in range(2):
        for i in range(1, len(lp)):
            lp[i] = lp[i] * (1 - a) + lp[i - 1] * a
        lp = lp[::-1].copy()

    fr = _frames(lp, N_FFT, HOP)
    if len(fr) < n_frames:
        fr = np.pad(fr, ((0, n_frames - len(fr)), (0, 0)), mode="edge")
    fr = fr[:n_frames] - fr[:n_frames].mean(axis=1, keepdims=True)

    lag_lo, lag_hi = int(sr / 800), min(int(sr / 70), N_FFT - 1)
    nfft = 1 << int(np.ceil(np.log2(2 * N_FFT)))
    F = np.fft.rfft(fr, n=nfft, axis=1)
    ac = np.fft.irfft(F * np.conj(F), n=nfft, axis=1)[:, :lag_hi + 1]
    ac = ac / (ac[:, :1] + 1e-12)
    return ac[:, lag_lo:lag_hi].max(axis=1).clip(0.0, 1.0)


def _envelope(x: np.ndarray, n: int) -> np.ndarray:
    """Short-time RMS on a fixed grid, one value per ENV_HOP samples."""
    pad = np.concatenate([x, np.zeros(ENV_HOP * 2)])
    fr = _frames(pad, ENV_HOP * 2, ENV_HOP)
    env = np.sqrt((fr ** 2).mean(axis=1) + 1e-20)
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)), mode="edge")
    return env[:n]

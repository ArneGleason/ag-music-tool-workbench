"""Fry-gated HF de-fizz.

Target: the "fixed-resonance scrape + fizz" Suno bakes into vocal fry — a
narrowband prominence around 10.7-10.9 kHz measuring ~3.2 dB above the
surrounding band during fry vs ~1.5 dB in normal singing. It is in the
source; nothing else in the pipeline touches it.

Why not EQ: the artifact is not a level problem, it is a *staticness*
problem — a fixed tone sitting inside a moving voice. Cutting it dulls the
voice without fixing the character. (Confirmed by the user: subtractive EQ
made things worse, not better.)

What works is destroying the tonality. An ensemble chorus on the isolated
band does that, but pitch-modulates, which reads as artificial. So instead:
decorrelate the phase in the band, which converts "static scrape" into
"breath" with no pitch modulation at all. Above ~7 kHz the ear barely uses
phase for pitch but is very sensitive to tonal-vs-noise character.

The catch, learned the hard way: randomising phase and overlap-adding makes
neighbouring frames sum INCOHERENTLY, which silently cost ~5 dB of top end
and turned this into the very EQ cut it was meant to replace. So the band is
split out, randomised, then ENERGY-MATCHED back to the original short-time
envelope before mixing. Level is preserved by construction; only the
character changes.
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


def process_channel(x: np.ndarray, sr: int, *, f_lo: float, strength: float,
                    per_lo: float, per_hi: float, smear_hz: float,
                    gate_out: list | None = None) -> np.ndarray:
    n = len(x)
    S = _stft(x)
    n_frames = S.shape[0]
    mag, ph = np.abs(S), np.angle(S)

    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    band = _smoothstep(freqs, f_lo * 0.7, f_lo)          # 0 below, 1 above

    # gate: fry-like frames only, smoothed ~45ms so it can't switch mid-syllable
    per = periodicity(x, sr, n_frames)
    gate = 1.0 - _smoothstep(per, per_lo, per_hi)
    k = max(1, int(round(0.045 * sr / HOP)))
    gate = np.convolve(gate, np.ones(k) / k, mode="same")
    if gate_out is not None:
        gate_out.append(gate)

    amount = np.clip(gate, 0, 1)[:, None] * band[None, :] * strength

    # Smear the magnitude along FREQUENCY. This is the operation that
    # actually dissolves a fixed resonance: it flattens the standing spectral
    # bump while leaving the broad tonal balance alone. Phase is untouched,
    # so overlap-add stays coherent and no level is lost.
    from scipy.ndimage import uniform_filter1d

    bins = max(3, int(round(smear_hz / (sr / N_FFT))) | 1)
    mag_sm = uniform_filter1d(mag, size=bins, axis=1, mode="nearest")

    # renormalise so the smeared band carries exactly the original energy —
    # smoothing must redistribute, never subtract (subtractive EQ is what
    # already failed on this artifact).
    w = band[None, :]
    num = (mag ** 2 * w).sum(axis=1, keepdims=True)
    den = (mag_sm ** 2 * w).sum(axis=1, keepdims=True) + 1e-20
    mag_sm = mag_sm * np.sqrt(num / den)

    mag_new = mag * (1.0 - amount) + mag_sm * amount
    return _istft(mag_new * np.exp(1j * ph), n).astype(np.float32)


def process(data: np.ndarray, sr: int, *, f_lo: float = 7000.0,
            strength: float = 0.6, per_lo: float = 0.60, per_hi: float = 0.92,
            smear_hz: float = 400.0) -> tuple[np.ndarray, float]:
    """Returns (processed, fraction of frames gated as fry)."""
    gates: list = []
    if data.ndim == 1:
        out = process_channel(data, sr, f_lo=f_lo, strength=strength, per_lo=per_lo,
                              per_hi=per_hi, smear_hz=smear_hz, gate_out=gates)
    else:
        out = np.stack([
            process_channel(data[:, c], sr, f_lo=f_lo, strength=strength,
                            per_lo=per_lo, per_hi=per_hi, smear_hz=smear_hz,
                            gate_out=gates if c == 0 else None)
            for c in range(data.shape[1])
        ], axis=1)
    return out.astype(np.float32), (float(np.mean(gates[0] > 0.25)) if gates else 0.0)

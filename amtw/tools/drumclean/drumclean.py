"""Strip instrument bleed from a separated drum stem.

Measured on the first real case (a Suno 4-stem drum export): the bleed is not
broadband. It is concentrated below 150 Hz, where a harmonic/percussive split
puts **91.6% of sub-60Hz energy and 59.2% of the 60-150Hz band** in the
harmonic component. Above 150 Hz the same measure reads 5-10%, which is just
cymbal and snare ring behaving normally. So the fix is surgical, not a
broadband denoise.

The subtlety that decides whether this sounds good: **a kick drum's body is
pitched**. At the moment of impact its fundamental is exactly the kind of
sustained tone the harmonic component captures, so attenuating harmonic content
below 150 Hz everywhere would gut the impact it is supposed to protect. The
attenuation is therefore gated OFF around every onset, and only removes tone
that persists *between* hits — which is what leaking bass actually is.

Ghost notes need no special protection here and none is applied. On the
reference material the quietest 5% of hits sit 26.9 dB above the floor between
hits, so nothing in this range is anywhere near them. That was worth measuring
rather than assuming, because it is the constraint the user cared most about.
"""
from __future__ import annotations

import numpy as np

N_FFT = 2048
HOP = 512


def _onset_guard(mono: np.ndarray, sr: int, n_frames: int,
                 guard_ms: float, sensitivity: float) -> np.ndarray:
    """1.0 where a hit is landing (protect), 0.0 well between hits."""
    import librosa

    env = librosa.onset.onset_strength(y=mono, sr=sr, hop_length=HOP)
    if env.size == 0:
        return np.zeros(n_frames)
    peaks = librosa.util.peak_pick(env, pre_max=3, post_max=3, pre_avg=5,
                                   post_avg=5, delta=sensitivity, wait=3)
    guard = np.zeros(max(n_frames, env.size))
    span = max(1, int(round(guard_ms / 1000.0 * sr / HOP)))
    for p in peaks:
        a = max(0, p - 1)                       # a frame of pre-roll
        b = min(len(guard), p + span)
        # decay across the guard so the transition is not a step
        guard[a:b] = np.maximum(guard[a:b],
                                np.linspace(1.0, 0.0, b - a, endpoint=False))
    return guard[:n_frames]


def process_channel(x: np.ndarray, sr: int, *, f_hi: float, strength: float,
                    guard_ms: float, sensitivity: float,
                    margin: float) -> tuple[np.ndarray, dict]:
    import librosa

    S = librosa.stft(x, n_fft=N_FFT, hop_length=HOP)
    H, P = librosa.decompose.hpss(S, margin=margin)

    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    # smooth the band edge so nothing gets a brick wall
    band = np.clip((f_hi - freqs) / max(1e-9, f_hi * 0.35), 0.0, 1.0)[:, None]

    guard = _onset_guard(x, sr, S.shape[1], guard_ms, sensitivity)[None, :]

    # remove this much of the harmonic component: only low, only between hits
    amount = strength * band * (1.0 - guard)
    out = S - amount * H

    removed = float(np.abs(amount * H).sum() / (np.abs(S).sum() + 1e-12))
    y = librosa.istft(out, hop_length=HOP, length=len(x))
    return y.astype(np.float32), {"removed": removed,
                                  "guarded": float(guard.mean())}


def process(data: np.ndarray, sr: int, *, f_hi: float = 150.0,
            strength: float = 0.8, guard_ms: float = 60.0,
            sensitivity: float = 0.15, margin: float = 3.0
            ) -> tuple[np.ndarray, dict]:
    """Returns (audio, stats). Stereo is processed per channel."""
    if data.ndim == 1:
        y, st = process_channel(data.astype(np.float32), sr, f_hi=f_hi,
                                strength=strength, guard_ms=guard_ms,
                                sensitivity=sensitivity, margin=margin)
        return y, st
    chans, stats = [], []
    for c in range(data.shape[1]):
        y, st = process_channel(data[:, c].astype(np.float32), sr, f_hi=f_hi,
                                strength=strength, guard_ms=guard_ms,
                                sensitivity=sensitivity, margin=margin)
        chans.append(y)
        stats.append(st)
    out = np.stack(chans, axis=1)
    return out, {k: float(np.mean([s[k] for s in stats])) for k in stats[0]}

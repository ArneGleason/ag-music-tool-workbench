"""HF re-modulation for the Suno fry artifact.

Measured problem (see pulse_look analysis): in fry passages the 5-12 kHz
band becomes a dense noise wash that sits at near-constant level. Envelope
modulation depth there is 0.159 vs 0.245 in normal singing — it does not
breathe. That flat, dense, unchanging band is what reads as "sharp and stiff
scraped on dry open-grain wood", and as "compressed".

Three earlier mechanisms failed because they treated it as a spectral
problem: a narrowband notch (200 Hz surgery on a 7 kHz-wide wash), phase
decorrelation (the band was already noise-like, coherence 0.55), and
subtractive EQ (dulls everything, per the user's own prior attempts).

This treats it as what it measures as: a DYNAMICS problem. Two levers, both
gated to fry frames and both energy-preserving:

  expand — deepen the band's own envelope modulation around its local mean,
           restoring peak-to-valley motion (attacks the 0.159 directly)
  track  — make the band follow the modulation of the voice's low band,
           which still has proper glottal pulse-to-pulse motion, so the
           wash moves WITH the voice instead of sitting under it

Nothing is subtracted; the band's slow level is renormalised back after
modulation, so this changes how the band moves, not how loud it is.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import hilbert

from .defizz import HOP, N_FFT, _istft, _smoothstep, _stft, periodicity

FINE_MS = 0.8      # envelope detail: fast enough to see glottal pulses
SLOW_MS = 35.0     # "local average" the modulation rides on
NORM_MS = 120.0    # window over which level is held constant


def _smooth(x: np.ndarray, sr: int, ms: float) -> np.ndarray:
    n = max(1, int(round(ms * 1e-3 * sr)))
    return uniform_filter1d(x, size=n, mode="nearest")


def _env(x: np.ndarray, sr: int, ms: float) -> np.ndarray:
    return _smooth(np.abs(hilbert(x)), sr, ms) + 1e-9


def process_channel(x: np.ndarray, sr: int, *, f_lo: float, expand: float,
                    track: float, strength: float, per_lo: float, per_hi: float,
                    max_gain_db: float, gate_out: list | None = None) -> np.ndarray:
    n = len(x)
    S = _stft(x)
    n_frames = S.shape[0]
    mag, ph = np.abs(S), np.angle(S)
    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    band = _smoothstep(freqs, f_lo * 0.8, f_lo)

    # split with original phase so lf + hf == x exactly
    hf = _istft(mag * band * np.exp(1j * ph), n)
    lf = _istft(mag * (1 - band) * np.exp(1j * ph), n)

    # normalised fast modulation of each band (mean ~1, rides on local level)
    e_hf, e_lf = _env(hf, sr, FINE_MS), _env(lf, sr, FINE_MS)
    mod_hf = e_hf / _smooth(e_hf, sr, SLOW_MS)
    mod_lf = e_lf / _smooth(e_lf, sr, SLOW_MS)

    # work in log domain: blend the band's own motion with the voice's, then
    # deepen the result. expand=1,track=0 is a no-op by construction.
    log_target = expand * ((1.0 - track) * np.log(mod_hf) + track * np.log(mod_lf))
    log_gain = log_target - np.log(mod_hf)

    lim = max_gain_db / 20.0 * np.log(10.0)
    log_gain = np.clip(log_gain, -lim, lim)

    # Fry gate. Thresholds matter enormously: raspy singing still has clear
    # pitch, so its periodicity sits around 0.70 (vs ~0.93 for clean singing).
    # The original 0.45/0.75 window left the gate only 18% open on actual fry
    # passages, which silently reduced every experiment to a near no-op.
    per = periodicity(x, sr, n_frames)
    gate = 1.0 - _smoothstep(per, per_lo, per_hi)
    k = max(1, int(round(0.045 * sr / HOP)))
    gate = np.convolve(gate, np.ones(k) / k, mode="same")
    if gate_out is not None:
        gate_out.append(gate)
    g = np.clip(np.interp(np.arange(n), np.arange(n_frames) * HOP + N_FFT / 2, gate), 0, 1)

    hf_new = hf * np.exp(log_gain * g * strength)

    # hold the band's slow level: this must change motion, not loudness.
    # clamp before sqrt — uniform_filter1d runs a moving sum whose rounding
    # error can go slightly negative over near-silent stretches, and the
    # resulting NaNs survive all the way into a 16-bit file as a constant
    # DC offset rather than as anything obviously broken.
    p_old = np.maximum(_smooth(hf ** 2, sr, NORM_MS), 0.0)
    p_new = np.maximum(_smooth(hf_new ** 2, sr, NORM_MS), 0.0)
    hf_new *= np.clip(np.sqrt((p_old + 1e-20) / (p_new + 1e-20)), 0.25, 4.0)

    return np.nan_to_num(lf + hf_new, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def process(data: np.ndarray, sr: int, *, f_lo: float = 4500.0, expand: float = 1.8,
            track: float = 0.5, strength: float = 1.0, per_lo: float = 0.60,
            per_hi: float = 0.92, max_gain_db: float = 12.0) -> tuple[np.ndarray, float]:
    """Returns (processed, fraction of frames gated as fry)."""
    gates: list = []
    kw = dict(f_lo=f_lo, expand=expand, track=track, strength=strength,
              per_lo=per_lo, per_hi=per_hi, max_gain_db=max_gain_db)
    if data.ndim == 1:
        out = process_channel(data, sr, gate_out=gates, **kw)
    else:
        out = np.stack([
            process_channel(data[:, c], sr, gate_out=gates if c == 0 else None, **kw)
            for c in range(data.shape[1])
        ], axis=1)
    return out.astype(np.float32), (float(np.mean(gates[0] > 0.25)) if gates else 0.0)

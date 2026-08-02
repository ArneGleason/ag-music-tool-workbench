"""Harmonic enhancement for the scratchy-fry artifact.

Derived from the labelled data rather than from guesswork: across 14 of the
user's marked segments the one feature that separates the artifact both from
clean singing (d = -1.02) AND from the saturation he called acceptable
(d = -1.23) is harmonic-to-noise ratio — 4.6 dB in scratchy passages vs
9.0 dB in clean ones. The artifact is harmonics buried in noise.

So: split each frame into a harmonic and a noise/transient part using the
standard median-filter trick (median along TIME keeps steady harmonics,
median along FREQUENCY keeps broadband transients), and in fry-gated frames
push the mix toward the harmonic part. That raises HNR directly, which is
the measured deficit.

Deliberately NOT subtractive in the EQ sense: the harmonic component keeps
its level, so the voice does not dull — only the noise riding on it is
reduced, and only where the gate says the artifact is.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter

from .defizz import HOP, N_FFT, _istft, _smoothstep, _stft, periodicity


def process_channel(x: np.ndarray, sr: int, *, f_lo: float, strength: float,
                    per_lo: float, per_hi: float, t_bins: int, f_bins: int,
                    power: float, mask_floor: float, voice_lo_db: float,
                    voice_hi_db: float, gate_floor: float,
                    adapt: tuple[float, float] | None = None,
                    spans: list | None = None,
                    gate_out: list | None = None) -> np.ndarray:
    n = len(x)
    S = _stft(x)
    n_frames = S.shape[0]
    mag, ph = np.abs(S), np.angle(S)

    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    harm = median_filter(mag, size=(t_bins, 1), mode="nearest")
    perc = median_filter(mag, size=(1, f_bins), mode="nearest")
    eps = 1e-12
    hp, pp = harm ** power, perc ** power
    mask_h = hp / (hp + pp + eps)          # 1 where steady/harmonic
    # Floor the mask: without this the noise component can be annihilated,
    # and since sibilance and air ARE noise components that reads as a dull,
    # de-essed vocal. Floor 0.35 caps the reduction at about 9 dB.
    mask_h = mask_floor + (1.0 - mask_floor) * mask_h

    band = _smoothstep(freqs, f_lo * 0.6, f_lo)   # leave the fundamental alone

    if spans is not None:
        # Marked-span mode. The automatic detector tops out around AUC 0.755,
        # which means ~17% precision at any threshold — far too blunt for
        # "leave clean material completely alone". When the user has marked
        # the spots, trust the marks: they give perfect precision, and every
        # sample outside a span is returned untouched.
        gate = np.zeros(n_frames)
        ft = (np.arange(n_frames) * HOP + N_FFT / 2) / sr
        for a, b in spans:
            gate[(ft >= a) & (ft <= b)] = 1.0
        k_f = max(1, int(round(0.030 * sr / HOP)))      # ~30 ms edge fades
        gate = np.convolve(gate, np.ones(k_f) / k_f, mode="same")
        gate = np.clip(gate, 0.0, 1.0)
        g = gate
        if adapt is None:
            eff = np.full_like(g, strength)
        else:
            # Severity comes from the DETECTOR, not from span length. Keying
            # it to duration meant a short-but-loud scrape got treated
            # gently, which is exactly why the user found auto-detect better
            # on loud parts and marked-span better on quiet ones. Marks decide
            # WHERE; the detector decides HOW MUCH.
            lo, hi = adapt
            per_s = periodicity(x, sr, n_frames)
            det = 1.0 - _smoothstep(per_s, per_lo, per_hi)
            low_s = freqs < 1000.0
            e_lo_s = (mag[:, low_s] ** 2).sum(axis=1) + eps
            e_all_s = (mag ** 2).sum(axis=1) + eps
            det = det * _smoothstep(10 * np.log10(e_lo_s / e_all_s),
                                    voice_lo_db, voice_hi_db)
            k_d = max(1, int(round(0.045 * sr / HOP)))
            det = np.convolve(det, np.ones(k_d) / k_d, mode="same")
            # normalise within the marked spans so the worst moment reaches
            # full strength regardless of the track's absolute detector level
            inside = gate > 0.5
            top = np.percentile(det[inside], 90) if inside.any() else 1.0
            sev = np.clip(det / max(top, 1e-6), 0.0, 1.0)
            eff = lo + (hi - lo) * sev
        amount = band[None, :] * eff[:, None]
        mag_new = mag * (1.0 - amount) + mag * mask_h * amount
        proc = np.nan_to_num(_istft(mag_new * np.exp(1j * ph), n))
        g_time = np.clip(np.interp(np.arange(n),
                                   np.arange(n_frames) * HOP + N_FFT / 2, g), 0, 1)
        if gate_out is not None:
            gate_out.append(g_time)
        return (x * (1.0 - g_time) + proc * g_time).astype(np.float32)

    per = periodicity(x, sr, n_frames)
    gate = 1.0 - _smoothstep(per, per_lo, per_hi)

    # VOICING REQUIREMENT. The gate keys on aperiodicity, but ordinary
    # sibilants ("s", "sh", "t") and breath are aperiodic too — so without
    # this the gate opens on every consonant and the harmonic mask strips
    # their noise, costing ~6 dB of air across the whole track. Scratchy fry
    # is VOICED (it has a fundamental; measured F0 261 Hz in the marked
    # region) whereas sibilants have almost no low-frequency energy, so the
    # low-band energy share separates them cleanly.
    low = freqs < 1000.0
    e_low = (mag[:, low] ** 2).sum(axis=1) + eps
    e_all = (mag ** 2).sum(axis=1) + eps
    low_share_db = 10 * np.log10(e_low / e_all)
    voiced = _smoothstep(low_share_db, voice_lo_db, voice_hi_db)
    gate = gate * voiced

    k = max(1, int(round(0.045 * sr / HOP)))
    gate = np.convolve(gate, np.ones(k) / k, mode="same")

    # HARD FLOOR. A smoothstep ramp is slightly open almost everywhere, so
    # "unaffected" material was still being touched a little. Below the floor
    # the gate becomes exactly zero; above it, rescale so the full range is
    # still reachable. Then a short smoothing pass only softens the edges of
    # real detections — far from any detection the gate stays exactly 0.
    gate = np.clip((gate - gate_floor) / max(1e-6, 1.0 - gate_floor), 0.0, 1.0)
    k2 = max(1, int(round(0.020 * sr / HOP)))
    gate = np.convolve(gate, np.ones(k2) / k2, mode="same")

    g = np.clip(gate, 0, 1)
    if adapt is None:
        eff = np.full_like(g, strength)
    else:
        # The user's verdict was that 0.5 suited subtle scrape, 1.0 suited
        # prolonged/pronounced scrape. So scale strength by severity, where
        # severity combines how deep the detection is right now with how
        # SUSTAINED it has been (~600 ms) — a long scrape earns full
        # strength, a passing one stays gentle.
        lo, hi = adapt
        k_slow = max(1, int(round(0.600 * sr / HOP)))
        g_slow = np.convolve(g, np.ones(k_slow) / k_slow, mode="same")
        severity = np.clip(0.45 * g + 0.55 * g_slow, 0.0, 1.0)
        eff = lo + (hi - lo) * severity

    # Frequency-dependent part only; the time gate is applied afterwards in
    # the sample domain so that untouched regions are the ORIGINAL samples,
    # not an STFT round-trip of them (that round-trip alone costs ~38 dB of
    # reconstruction error, which is not "completely unaffected").
    amount = band[None, :] * eff[:, None]
    mag_new = mag * (1.0 - amount) + mag * mask_h * amount
    proc = _istft(mag_new * np.exp(1j * ph), n)
    proc = np.nan_to_num(proc, nan=0.0, posinf=0.0, neginf=0.0)

    g_time = np.interp(np.arange(n), np.arange(n_frames) * HOP + N_FFT / 2, g)
    g_time = np.clip(g_time, 0.0, 1.0)
    out = x * (1.0 - g_time) + proc * g_time
    if gate_out is not None:
        gate_out.append(g_time)
    return out.astype(np.float32)


def process(data: np.ndarray, sr: int, *, f_lo: float = 1500.0, strength: float = 0.8,
            per_lo: float = 0.60, per_hi: float = 0.92, t_bins: int = 17,
            f_bins: int = 17, power: float = 2.0, mask_floor: float = 0.35,
            voice_lo_db: float = -15.0, voice_hi_db: float = -6.0,
            gate_floor: float = 0.30, spans: list | None = None,
            adapt: tuple[float, float] | None = None) -> tuple[np.ndarray, float]:
    """Returns (processed, fraction of frames gated as fry).

    adapt=(lo, hi) scales strength with artifact severity instead of using a
    fixed value — gentle on passing scrape, full on sustained scrape.
    """
    gates: list = []
    kw = dict(f_lo=f_lo, strength=strength, per_lo=per_lo, per_hi=per_hi,
              t_bins=t_bins, f_bins=f_bins, power=power, mask_floor=mask_floor,
              voice_lo_db=voice_lo_db, voice_hi_db=voice_hi_db,
              gate_floor=gate_floor, spans=spans, adapt=adapt)
    if data.ndim == 1:
        out = process_channel(data, sr, gate_out=gates, **kw)
    else:
        out = np.stack([
            process_channel(data[:, c], sr, gate_out=gates if c == 0 else None, **kw)
            for c in range(data.shape[1])
        ], axis=1)
    return out.astype(np.float32), (float(np.mean(gates[0] > 0.25)) if gates else 0.0)

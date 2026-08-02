"""Detector profile for the Suno "scrape" fry artifact.

The previous gate was a single periodicity threshold, and measurement showed
it was only 18% open on the passage the user actually complains about —
which silently reduced every processing experiment to a near no-op.

It also cannot work in principle: the artifact appears both on quiet breathy
fry and on loud screamed fry, so anything keyed to level is wrong, and raspy
singing keeps a clear pitch, so periodicity alone barely separates it.

So: a profile of several features, each deliberately amplitude-invariant,
each scored as a percentile rank within the file so the detector adapts to
material instead of relying on absolute thresholds.

  imp   HF envelope coefficient of variation — how spiky/impulsive the
        5-12 kHz band is. Measured 1.02 on the scrape vs 0.46 on clean
        singing. This is the strongest known discriminator.
  flat  spectral flatness of 5-12 kHz — the artifact is a dense noise wash,
        which is flat; clean vocal HF is more structured.
  hfr   HF energy share — brightness relative to the whole frame, not level.
  aper  1 - low-band periodicity — weak alone, useful as support.

Nothing here is a final answer: run `amtw detect` and check the plot against
where the artifact is actually audible before trusting the score.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import hilbert

from ...core.dsp import HOP, N_FFT, _stft, periodicity

HF_LO, HF_HI = 5000.0, 12000.0
FEATURES = ("imp", "flat", "hfr", "aper", "rough", "cpp", "flux", "hnr")
DEFAULT_WEIGHTS = {"imp": 0.20, "flat": 0.05, "hfr": 0.05, "aper": 0.10,
                   "rough": 0.25, "cpp": 0.20, "flux": 0.05, "hnr": 0.10}

# Psychoacoustic roughness lives in amplitude modulation around 30-150 Hz —
# that IS the sensation described as "scratchy"/"scrape", so it is the most
# directly motivated feature here. CPP (cepstral peak prominence) is the
# standard clinical measure of how noisy/dysphonic a voice is: low CPP means
# the harmonic structure is buried in noise.
ROUGH_LO, ROUGH_HI = 30.0, 150.0


def _rank(v: np.ndarray) -> np.ndarray:
    """Percentile rank in [0,1] — adapts to the material, no fixed thresholds."""
    v = np.nan_to_num(v, nan=float(np.nanmedian(v)) if np.isfinite(v).any() else 0.0)
    order = v.argsort().argsort().astype(np.float64)
    return order / max(1.0, len(v) - 1.0)


def features(x: np.ndarray, sr: int) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Per-frame raw features plus the frame time axis."""
    S = _stft(x)
    mag = np.abs(S)
    n_frames = S.shape[0]
    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    hf = (freqs >= HF_LO) & (freqs <= HF_HI)

    eps = 1e-12
    e_hf = (mag[:, hf] ** 2).sum(axis=1) + eps
    e_all = (mag ** 2).sum(axis=1) + eps
    hfr = 10 * np.log10(e_hf / e_all)

    band = mag[:, hf] + eps
    flat = np.exp(np.log(band).mean(axis=1)) / band.mean(axis=1)

    # impulsiveness of the HF band envelope, measured per frame window
    from scipy.signal import butter, sosfiltfilt

    sos = butter(6, [HF_LO / (sr / 2), min(0.99, HF_HI / (sr / 2))],
                 btype="band", output="sos")
    bp = sosfiltfilt(sos, x)
    env = uniform_filter1d(np.abs(hilbert(bp)), size=max(1, int(0.0007 * sr)))
    w = max(8, int(0.050 * sr))                      # 50 ms analysis window
    m1 = uniform_filter1d(env, size=w)
    m2 = uniform_filter1d(env ** 2, size=w)
    var = np.maximum(m2 - m1 ** 2, 0.0)
    imp_s = np.sqrt(var) / (m1 + eps)
    centers = np.clip((np.arange(n_frames) * HOP + N_FFT // 2), 0, len(imp_s) - 1)
    imp = imp_s[centers]

    aper = 1.0 - periodicity(x, sr, n_frames)

    # --- roughness: energy of the amplitude envelope's own spectrum in the
    # 30-150 Hz band, i.e. how much the signal flutters at rates the ear
    # hears as "rough" rather than as pitch or as tremolo.
    full_env = uniform_filter1d(np.abs(hilbert(x)), size=max(1, int(0.0005 * sr)))
    win = N_FFT
    rough = np.zeros(n_frames)
    ef = np.fft.rfftfreq(win, 1 / sr)
    rsel = (ef >= ROUGH_LO) & (ef <= ROUGH_HI)
    tsel = (ef >= 2.0) & (ef <= 400.0)
    hann = np.hanning(win)
    for i in range(n_frames):
        s0 = i * HOP
        seg = full_env[s0:s0 + win]
        if len(seg) < win:
            rough[i] = rough[i - 1] if i else 0.0
            continue
        E = np.abs(np.fft.rfft((seg - seg.mean()) * hann)) ** 2
        rough[i] = E[rsel].sum() / (E[tsel].sum() + eps)

    # --- cepstral peak prominence: height of the cepstral peak at the pitch
    # quefrency above the overall cepstral trend. Low CPP = harmonics buried
    # in noise, which is what a scratchy/dysphonic voice measures as.
    logmag = np.log(mag + eps)
    ceps = np.fft.irfft(logmag, axis=1)
    q = np.arange(ceps.shape[1]) / sr
    qsel = (q >= 1 / 400.0) & (q <= 1 / 70.0)
    cpp = np.zeros(n_frames)
    if qsel.any():
        qi = np.where(qsel)[0]
        cq = np.abs(ceps[:, qi])
        xq = q[qi]
        for i in range(n_frames):
            yv = cq[i]
            A = np.vstack([xq, np.ones_like(xq)]).T
            coef, *_ = np.linalg.lstsq(A, yv, rcond=None)
            cpp[i] = float((yv - A @ coef).max())

    # --- spectral flux: how fast the spectrum is changing, normalised
    nm = mag / (mag.sum(axis=1, keepdims=True) + eps)
    d = np.diff(nm, axis=0, prepend=nm[:1])
    flux = np.maximum(d, 0).sum(axis=1)

    # --- band-limited harmonic-to-noise ratio, where scratchiness lives
    per_b = periodicity(x, sr, n_frames)
    hnr = 10 * np.log10(np.clip(per_b, 1e-6, 0.999999) /
                        (1 - np.clip(per_b, 1e-6, 0.999999)))

    t = (np.arange(n_frames) * HOP + N_FFT / 2) / sr
    return {"imp": imp, "flat": flat, "hfr": hfr, "aper": aper,
            "rough": rough, "cpp": cpp, "flux": flux, "hnr": hnr}, t


def score(x: np.ndarray, sr: int, weights: dict | None = None,
          smooth_ms: float = 60.0) -> tuple[np.ndarray, dict, np.ndarray]:
    """Combined 0-1 detector score, the raw features, and the time axis."""
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    feats, t = features(x, sr)
    ranked = {k: _rank(v) for k, v in feats.items()}
    total = sum(w.values()) or 1.0
    s = sum(w[k] * ranked[k] for k in FEATURES) / total
    k = max(1, int(round(smooth_ms * 1e-3 * sr / HOP)))
    s = uniform_filter1d(s, size=k, mode="nearest")
    return s, feats, t

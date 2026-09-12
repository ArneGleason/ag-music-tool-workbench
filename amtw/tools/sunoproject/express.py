"""Expression from the audio stem, because the MIDI export has none.

Measured over 200 Suno per-stem exports: zero pitch-bend events, and one
velocity value per file. Everything expressive therefore has to be read off
the wav that came in the same folder. Two things are read here, and one is
deliberately not:

velocity — per note, the energy in a narrow band around the note's own
    fundamental and second harmonic, peak over the first 80 ms after onset.
    Band energy rather than broadband RMS so that the inner voice of a chord
    is measured as itself, not as the chord. Mapped through the stem's own
    loudness range (10th→90th percentile) onto a velocity range with a floor,
    because stem separation leaves some notes much softer than they were
    played and a head start that still sounds the note beats a faithful one
    that drops it. Drums: broadband onset strength at the hit.

pitch — monophonic stems only (lead vocal, bass). pyin contour inside each
    note, expressed in semitones relative to the note's key, thinned to a
    few linear points. Delivered as a DAWproject per-note `transpose` curve,
    which Bitwig reads as note pitch expression — the format the user's own
    exports use, so no MPE channel games.

NOT read: per-note gain envelopes. The user asked to stay away from those
for now; the hook is here (the band energy over time is already computed)
but nothing is emitted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# profile -> pyin range; absent = no pitch contour for that instrument
# backing vocals are deliberately absent: a stacked chorus is not mono, and a
# contour tracked on the loudest voice would hand every harmony note a
# constant wrong "bend"
PITCH_RANGE = {
    "lead": (80.0, 1000.0),
    "bass": (30.0, 400.0),
}


@dataclass
class NoteExpr:
    velocity: int
    bend: list[tuple[float, float]] = field(default_factory=list)   # (seconds from note start, semitones)


# --------------------------------------------------------------------------- #
# velocity
# --------------------------------------------------------------------------- #


def _band_peak_db(S_db: np.ndarray, freqs: np.ndarray, frame_t: np.ndarray,
                  f0: float, t0: float, t1: float) -> float:
    a = np.searchsorted(frame_t, t0)
    b = max(a + 1, np.searchsorted(frame_t, t1))
    if a >= len(frame_t):
        return -120.0
    best = -120.0
    for h in (1, 2):
        lo, hi = f0 * h * 2 ** (-0.6 / 12), f0 * h * 2 ** (0.6 / 12)
        sel = (freqs >= lo) & (freqs <= hi)
        if not sel.any():
            continue
        best = max(best, float(S_db[sel, a:b].max()))
    return best


def velocities(y: np.ndarray, sr: int, onsets_s: np.ndarray, keys: np.ndarray,
               drums: bool, vel_lo: int = 30, vel_hi: int = 120,
               range_db: float = 24.0, attack_s: float = 0.08) -> np.ndarray:
    """vel_hi at the stem's loud reference (90th percentile of note energy),
    falling linearly in dB to vel_lo `range_db` below it, floored there. A
    fixed dB range rather than percentiles, so an evenly played part stays
    even -- percentile mapping forced the quietest tenth of every stem to the
    floor whether it was 3 dB quieter or 30."""
    import librosa
    if len(onsets_s) == 0:
        return np.array([], dtype=int)

    if drums:
        hop = 256
        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        fr = np.clip((onsets_s * sr / hop).astype(int), 0, len(env) - 1)
        e = np.array([env[max(0, i - 1): i + 3].max() for i in fr])
        e = 20 * np.log10(e + 1e-6)
    else:
        n_fft, hop = 4096, 512
        S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop)) ** 2
        S_db = 10 * np.log10(S + 1e-12)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
        frame_t = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=hop)
        e = np.array([
            _band_peak_db(S_db, freqs, frame_t, 440.0 * 2 ** ((k - 69) / 12), t, t + attack_s)
            for t, k in zip(onsets_s, keys)
        ])

    # drums: each piece against its own loud reference -- a hat is quieter
    # than a kick in onset strength, but a drummer's loud hat is loud for a
    # hat, and that is what the velocity on that key means
    hi = np.full(len(e), np.percentile(e, 90))
    if drums:
        for k in np.unique(keys):
            sel = keys == k
            if sel.sum() >= 4:
                hi[sel] = np.percentile(e[sel], 90)
    x = np.clip((e - (hi - range_db)) / range_db, 0, 1)
    return np.round(vel_lo + (vel_hi - vel_lo) * x).astype(int)


# --------------------------------------------------------------------------- #
# pitch
# --------------------------------------------------------------------------- #


def pitch_track(y: np.ndarray, sr: int, fmin: float, fmax: float):
    import librosa
    hop = 256
    f0, _, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=hop, frame_length=4096)
    t = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop)
    return t, librosa.hz_to_midi(f0)


def _thin(t: np.ndarray, v: np.ndarray, tol: float, max_points: int) -> list[tuple[float, float]]:
    """Douglas–Peucker on a contour."""
    if len(t) <= 2:
        return list(zip(t.tolist(), v.tolist()))
    keep = np.zeros(len(t), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(t) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        line = v[a] + (v[b] - v[a]) * (t[a + 1:b] - t[a]) / max(1e-9, t[b] - t[a])
        d = np.abs(v[a + 1:b] - line)
        i = int(np.argmax(d))
        if d[i] > tol:
            m = a + 1 + i
            keep[m] = True
            stack.append((a, m))
            stack.append((m, b))
    idx = np.flatnonzero(keep)
    if len(idx) > max_points:
        idx = idx[np.linspace(0, len(idx) - 1, max_points).astype(int)]
    return [(float(t[i]), float(v[i])) for i in idx]


def bend_curve(track_t: np.ndarray, track_midi: np.ndarray, t0: float, t1: float, key: int,
               clamp: float = 2.0, belong: float = 2.5, tol: float = 0.08,
               max_points: int = 24) -> list[tuple[float, float]]:
    """Semitone offset from `key` across [t0, t1], as (seconds from t0, st).

    Measured on a lead vocal (353 notes): the transcribed key is right for
    86% of notes (median offset 0.19 st) and the note *core* moves ~0.8 st,
    but the whole-note range is 1.8 st median / 5.7 st at the 90th
    percentile — Suno's note boundaries include the glide into the
    neighbouring pitch. So frames further than `belong` from the key are
    treated as not this note, the curve is clamped at ±`clamp`, and a note
    whose contour mostly disagrees with its key (median off by more than
    1 st, or over 30% of frames elsewhere) gets no curve: it sounds at its
    key, which beats a confident wrong bend."""
    a, b = np.searchsorted(track_t, t0), np.searchsorted(track_t, t1)
    seg_t, seg_v = track_t[a:b], track_midi[a:b] - key
    voiced = np.isfinite(seg_v)
    if voiced.sum() < 3:
        return []
    far = voiced & (np.abs(seg_v) > belong)
    if far.sum() > 0.3 * voiced.sum() or abs(float(np.median(seg_v[voiced]))) > 1.0:
        return []
    ok = voiced & ~far
    if ok.sum() < 3:
        return []
    seg_t, seg_v = seg_t[ok] - t0, seg_v[ok]
    # light median smoothing: pyin jitters a few cents frame to frame
    if len(seg_v) >= 5:
        from scipy.ndimage import median_filter
        seg_v = median_filter(seg_v, size=5, mode="nearest")
    seg_v = np.clip(seg_v, -clamp, clamp)
    pts = _thin(seg_t, seg_v, tol, max_points)
    if pts and pts[0][0] > 1e-6:
        pts.insert(0, (0.0, pts[0][1]))
    # a contour that is flat within tolerance is not a bend — but a steady
    # offset is intonation worth keeping as a single point (the singer sat
    # 30 cents sharp of the transcribed key); below 15 cents it is noise
    if max(v for _, v in pts) - min(v for _, v in pts) < tol:
        med = float(np.median(seg_v))
        return [(0.0, med)] if abs(med) > 0.15 else []
    return pts

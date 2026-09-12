"""Performance-following tempo map: drum onsets → anchored 16ths → linear
tempo ramps that land every anchored 16th on its hit.

The shape this has to reproduce is the user's hand-made map (read from a
Bitwig export, see docs/stem-toolset-roadmap.md): points on a 16th grid,
linear ramps, an S-curve inside a beat — slow down to meet a late hat, speed
up so the next downbeat still lands — all within a few percent of the song
tempo. The judgment in that work is *which 16th a hit means*; the arithmetic
is making the ramps hit the times. This module does the arithmetic and makes
the judgment by a bounded rule, then reports where the rule strained.

Why a least-squares solve and not a sequential one: with one tempo point per
anchor and every segment forced to exact length, a single early hit makes the
next segment over-correct and the solution rings forever (T, 2B-T, T, ...).
Solving every point at once with a weak pull toward the baseline tempo gives
the S-curve instead — the excursion happens and returns.

Time across a linear ramp from T1 to T2 over Δb beats is
    60·Δb·ln(T2/T1) / (T2 − T1)
(60·Δb/T when T1 == T2). Bitwig integrates its linear tempo lane the same
way, which is what makes the written points land where the solve says.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# --------------------------------------------------------------------------- #
# tempo-lane arithmetic
# --------------------------------------------------------------------------- #


def seg_seconds(db: np.ndarray, t1: np.ndarray, t2: np.ndarray) -> np.ndarray:
    d = t2 - t1
    flat = np.abs(d) < 1e-7 * t1
    out = np.empty_like(t1)
    out[flat] = 60.0 * db[flat] / t1[flat]
    nf = ~flat
    out[nf] = 60.0 * db[nf] * np.log(t2[nf] / t1[nf]) / d[nf]
    return out


def seg_grad(db, t1, t2):
    """d seg / d t1, d seg / d t2."""
    d = t2 - t1
    flat = np.abs(d) < 1e-7 * t1
    g1 = np.empty_like(t1)
    g2 = np.empty_like(t1)
    g1[flat] = g2[flat] = -30.0 * db[flat] / t1[flat] ** 2
    nf = ~flat
    L = np.log(t2[nf] / t1[nf])
    D = d[nf]
    g1[nf] = 60.0 * db[nf] * (L - D / t1[nf]) / D ** 2
    g2[nf] = 60.0 * db[nf] * (D / t2[nf] - L) / D ** 2
    return g1, g2


def lane_seconds(points: list[tuple[float, float]], b_from: float, b_to: float) -> float:
    """Seconds between two beat positions under a linear-interpolated lane."""
    if not points:
        raise ValueError("empty tempo lane")
    bs = np.array([p[0] for p in points])
    ts = np.array([p[1] for p in points])

    def tempo_at(b):
        return float(np.interp(b, bs, ts))          # flat beyond the ends, like the DAW

    knots = [b_from] + [float(b) for b in bs if b_from < b < b_to] + [b_to]
    k = np.array(knots)
    t = np.array([tempo_at(b) for b in knots])
    return float(seg_seconds(np.diff(k), t[:-1], t[1:]).sum())


# --------------------------------------------------------------------------- #
# anchors
# --------------------------------------------------------------------------- #


@dataclass
class Anchor:
    beat: float          # arrangement beat (a 16th grid position)
    seconds: float       # audio time of the hit, relative to clip start
    weight: float        # onset strength, normalised
    predicted: float     # where the prior grid put that 16th (seconds)


def onsets(y: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """(times, strengths) of drum hits."""
    import librosa
    hop = 256
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop,
                                        backtrack=False, units="frames")
    times = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
    strength = env[np.clip(frames, 0, len(env) - 1)]
    return times, strength / (np.percentile(strength, 90) + 1e-9)


def assign_anchors(prior: list[tuple[float, float]], clip_beat: float, first_beat: float,
                   last_beat: float, hit_t: np.ndarray, hit_w: np.ndarray,
                   sub: int = 4, tolerance: float = 0.4, min_weight: float = 0.15) -> list[Anchor]:
    """Each 16th from first_beat to last_beat looks for a hit within
    ±tolerance of a 16th's length around where the prior lane predicts it.
    Every hit can anchor only its nearest grid position, so a pushed 16th
    cannot be claimed by two slots."""
    step = 1.0 / sub
    grid = np.arange(first_beat, last_beat + 1e-9, step)
    pred = np.array([lane_seconds(prior, clip_beat, b) for b in grid])
    # nearest grid slot for every hit
    slot = np.searchsorted(pred, hit_t)
    slot = np.clip(slot, 1, len(pred) - 1)
    left_closer = (hit_t - pred[slot - 1]) < (pred[slot] - hit_t)
    slot = np.where(left_closer, slot - 1, slot)

    out: list[Anchor] = []
    for i, b in enumerate(grid):
        local = pred[min(i + 1, len(pred) - 1)] - pred[max(i - 1, 0)]
        local /= (2 if 0 < i < len(pred) - 1 else 1)
        tol = tolerance * local
        cands = np.flatnonzero((slot == i) & (np.abs(hit_t - pred[i]) <= tol) & (hit_w >= min_weight))
        if len(cands) == 0:
            continue
        k = cands[np.argmax(hit_w[cands])]
        out.append(Anchor(float(b), float(hit_t[k]), float(min(hit_w[k], 1.0)), float(pred[i])))
    return out


# --------------------------------------------------------------------------- #
# solve
# --------------------------------------------------------------------------- #


@dataclass
class Solution:
    grid: np.ndarray               # beat positions of tempo points
    tempo: np.ndarray              # bpm at each
    baseline: np.ndarray           # prior bpm at each
    anchors: list[Anchor]
    residual_ms: np.ndarray        # per anchor, after the solve
    clip_beat: float


def solve(prior: list[tuple[float, float]], clip_beat: float, anchors: list[Anchor],
          last_beat: float, first_beat: float | None = None, sub: int = 4,
          max_dev: float = 0.12, timing_sigma_s: float = 0.004,
          prior_sigma: float = 0.03) -> Solution:
    """timing_sigma 4 ms: tight enough to land a pushed 16th (20–45 ms), loose
    enough not to draw tempo wiggles for a drum machine's 2 ms jitter."""
    from scipy.optimize import least_squares

    step = 1.0 / sub
    grid = np.arange(clip_beat, last_beat + 1e-9, step)
    if abs(grid[-1] - last_beat) > 1e-6:
        grid = np.append(grid, last_beat)
    bs = np.array([p[0] for p in prior]); ts = np.array([p[1] for p in prior])
    base = np.interp(grid, bs, ts)
    if first_beat is not None:
        # the count-in is flat at the song's tempo: whatever the prior lane
        # does before the downbeat (the user's own lead-in tweak, typically)
        # must not become the baseline there
        song = base[grid >= first_beat]
        base[grid < first_beat] = float(np.median(song)) if len(song) else base[0]
    db = np.diff(grid)

    # anchor k lives at grid index idx[k]; its time is the sum of segments before it
    idx = np.array([int(round((a.beat - clip_beat) / step)) for a in anchors])
    target = np.array([a.seconds for a in anchors])
    w = np.array([a.weight for a in anchors])
    n = len(grid)

    def times(T):
        return np.concatenate([[0.0], np.cumsum(seg_seconds(db, T[:-1], T[1:]))])

    def fun(T):
        r_t = (times(T)[idx] - target) * w / timing_sigma_s
        r_p = (T / base - 1.0) / prior_sigma
        return np.concatenate([r_t, r_p])

    def jac(T):
        g1, g2 = seg_grad(db, T[:-1], T[1:])
        # d time_i / d T_j  for i = grid index: contributions from seg j (as t1, if j < i)
        # and seg j-1 (as t2, if j-1 < i)  -> build for anchor rows only
        J = np.zeros((len(idx) + n, n))
        for r, i in enumerate(idx):
            if i == 0:
                continue
            J[r, :i] += g1[:i]            # T_j as t1 of seg j, j < i
            J[r, 1:i + 1] += g2[:i]       # T_j as t2 of seg j-1, j-1 < i
            J[r, :] *= w[r] / timing_sigma_s
        J[len(idx):, :] = np.diag(1.0 / (base * prior_sigma))
        return J

    lo, hi = base * (1 - max_dev), base * (1 + max_dev)
    # pin the clip-start point so the count-in joins the song at a flat tempo
    lo[0], hi[0] = base[0] * (1 - 1e-3), base[0] * (1 + 1e-3)
    res = least_squares(fun, base.copy(), jac=jac, bounds=(lo, hi), method="trf",
                        x_scale=base, max_nfev=200)
    T = res.x
    resid = (times(T)[idx] - target) * 1000.0
    return Solution(grid, T, base, anchors, resid, clip_beat)


def thin(grid: np.ndarray, tempo: np.ndarray, tol_bpm: float = 0.1) -> list[tuple[float, float]]:
    """Drop points that sit on the line between their kept neighbours, so a
    steady passage is two points, not sixty."""
    keep = [0]
    for i in range(1, len(grid) - 1):
        a = keep[-1]
        # would dropping i keep i on the a->(i+1) line?  check every dropped
        # point since a against the a->(i+1) line
        b = i + 1
        ok = True
        for j in range(a + 1, b):
            interp = tempo[a] + (tempo[b] - tempo[a]) * (grid[j] - grid[a]) / (grid[b] - grid[a])
            if abs(interp - tempo[j]) > tol_bpm:
                ok = False
                break
        if not ok:
            keep.append(i)
    keep.append(len(grid) - 1)
    return [(float(grid[i]), float(tempo[i])) for i in keep]

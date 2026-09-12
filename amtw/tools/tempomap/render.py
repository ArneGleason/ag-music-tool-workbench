"""Review artefacts for a tempo map: a click track rendered from the *written*
lane (so it checks thinning and the ramp arithmetic, not just the solve), a
drums+click mix for the A/B tool, and a picture of where the map strained."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .solve import Solution, lane_seconds


def _click(sr: int, hz: float, gain: float, ms: float = 12.0) -> np.ndarray:
    n = int(sr * ms / 1000)
    t = np.arange(n) / sr
    return (gain * np.sin(2 * np.pi * hz * t) * np.exp(-t * 400)).astype(np.float32)


def click_track(points: list[tuple[float, float]], clip_beat: float, first_beat: float,
                last_beat: float, n_samples: int, sr: int, sub: int = 4) -> np.ndarray:
    out = np.zeros(n_samples, dtype=np.float32)
    beat_c, sub_c = _click(sr, 1000.0, 0.8), _click(sr, 2000.0, 0.25, 8.0)
    bar_c = _click(sr, 660.0, 1.0, 16.0)
    step = 1.0 / sub
    b = first_beat
    while b <= last_beat + 1e-9:
        s = int(round(lane_seconds(points, clip_beat, b) * sr))
        on_beat = abs(b - round(b)) < 1e-6
        on_bar = on_beat and int(round(b - first_beat)) % 4 == 0
        c = bar_c if on_bar else beat_c if on_beat else sub_c
        if 0 <= s < n_samples:
            e = min(n_samples, s + len(c))
            out[s:e] += c[: e - s]
        b += step
    return np.clip(out, -1, 1)


def picture(sol: Solution, points: list[tuple[float, float]], hit_t: np.ndarray,
            out_png: Path, title: str) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    ax1.plot(sol.grid, sol.baseline, color="#999", lw=1, label="prior (Suno per-beat)")
    ax1.plot([p[0] for p in points], [p[1] for p in points], color="#d9480f", lw=1.2,
             label=f"solved ramps ({len(points)} points)")
    ax1.set_ylabel("bpm")
    ax1.legend(loc="upper right")
    ax1.set_title(title)

    ab = np.array([a.beat for a in sol.anchors])
    ax2.scatter(ab, sol.residual_ms, s=6, color="#1c7ed6", label="anchor error after solve (ms)")
    shift = np.array([(a.seconds - a.predicted) * 1000 for a in sol.anchors])
    ax2.scatter(ab, shift, s=4, color="#bbb", label="hit vs prior grid (ms)")
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_ylabel("ms")
    ax2.set_xlabel("arrangement beat")
    ax2.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    return out_png

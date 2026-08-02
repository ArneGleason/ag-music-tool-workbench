"""Detector check — plots the fry-detector's features against your marks.

The point is to be able to *see* whether the detector tracks what you hear,
instead of trusting a threshold blind. On the labelled set it maxes at
AUC 0.755, which is why marked-span mode is the settled workflow for repair.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from ...core import audio_utils
from ...core.paths import OUTPUT_DIR
from ...spec import AUDIO, Field, Tool


def run(args: argparse.Namespace) -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from . import frydetect

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    data, sr = audio_utils.load(src)
    x = audio_utils.to_mono(data).astype(np.float64)
    s, feats, t = frydetect.score(x, sr)

    half = args.mark_window / 2.0
    # spans of (start, end); a point mark becomes a window around itself
    spans: list[tuple[float, float]] = []
    clean_spans: list[tuple[float, float]] = []
    for m in (args.marks or []):
        spans.append((float(m) - half, float(m) + half))

    if args.from_notes:
        # markers straight out of the A/B tool. Segments carry their own
        # range; notes starting with "clean" become negative examples.
        import json

        notes = json.loads(Path(args.from_notes).read_text(encoding="utf-8"))
        for mk in notes.get("markers", []):
            t0 = float(mk["t"])
            t1 = float(mk["t_end"]) if isinstance(mk.get("t_end"), (int, float)) \
                and mk["t_end"] > t0 else None
            span = (t0, t1) if t1 else (t0 - half, t0 + half)
            if str(mk.get("text", "")).strip().lower().startswith("clean"):
                clean_spans.append(span)
            else:
                spans.append(span)
        print(f"loaded {len(spans)} artifact spans, {len(clean_spans)} clean spans "
              f"from {Path(args.from_notes).name}")

    def mask(sp):
        m = np.zeros(len(t), dtype=bool)
        for a, b in sp:
            m |= (t >= a) & (t <= b)
        return m

    if spans:
        sel = mask(spans)
        # compare against explicitly-marked clean spans when available — far
        # fairer than "everything else", which lumps in silence, breaths and
        # consonants and swamps any real difference
        ref, ref_name = (mask(clean_spans), "clean marks") if clean_spans else (~sel, "elsewhere")
        span_s = float(np.diff(t[:2])[0]) if len(t) > 1 else 0.0
        print(f"\n{len(spans)} artifact spans ({sel.sum() * span_s:.1f}s), "
              f"reference = {ref_name} ({ref.sum() * span_s:.1f}s)")
        print(f"\n{'feature':<8}{'artifact':>11}{'reference':>12}{'separation':>12}")
        for k in list(frydetect.FEATURES) + ["SCORE"]:
            v = s if k == "SCORE" else feats[k]
            a, b = v[sel], v[ref]
            if not len(a) or not len(b):
                continue
            sd = np.sqrt((a.std() ** 2 + b.std() ** 2) / 2) + 1e-12
            print(f"{k:<8}{a.mean():>11.3f}{b.mean():>12.3f}{(a.mean() - b.mean()) / sd:>12.2f}")
        print("\n(separation is Cohen's d — above ~0.8 is a strong discriminator,\n"
              " negative means the feature points the wrong way)")

    rows = len(frydetect.FEATURES) + 2
    fig, ax = plt.subplots(rows, 1, figsize=(14, 2.0 * rows), sharex=True,
                           constrained_layout=True)
    ax[0].specgram(x, NFFT=1024, Fs=sr, noverlap=768, cmap="magma")
    ax[0].set_ylim(0, min(16000, sr / 2))
    ax[0].set_ylabel("spectrogram", fontsize=8)
    for i, k in enumerate(frydetect.FEATURES, start=1):
        ax[i].plot(t, feats[k], lw=0.7, color="#60a5fa")
        ax[i].set_ylabel(k, fontsize=8)
    ax[-1].plot(t, s, lw=1.0, color="#22c55e")
    ax[-1].axhline(args.threshold, color="#f87171", lw=0.8, ls="--")
    ax[-1].set_ylabel("SCORE", fontsize=8)
    ax[-1].set_xlabel("seconds", fontsize=8)
    for a in ax:
        for x0, x1 in spans:            # artifact spans shaded amber
            a.axvspan(x0, x1, color="#fbbf24", alpha=0.28, lw=0)
        for x0, x1 in clean_spans:      # clean reference spans in green
            a.axvspan(x0, x1, color="#22c55e", alpha=0.20, lw=0)
        a.tick_params(labelsize=7)

    out = Path(args.out).resolve() if args.out else (OUTPUT_DIR / f"detect_{src.stem}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=100)
    plt.close(fig)
    print(f"\nplot -> {out}")
    print("amber = your artifact spans, green = clean spans; check whether any "
          "feature row actually tracks them.")
    return 0


TOOL = Tool(
    name="detect", title="Detector check", group="Fry repair", run=run, order=20,
    help="plot the fry-detector features against your marks",
    blurb="Plots the fry-detector's features against your marks, so you can see "
          "whether it actually tracks what you hear. Writes a PNG.",
    fields=[
        Field("input", "Vocal stem", "file", accept=AUDIO, root="input",
              required=True),
        Field("from_notes", "A/B notes", "file", flag="--from-notes",
              accept=["json"], root="ab_notes",
              help="markers become artifact examples unless the note starts "
                   "with 'clean'"),
        Field("mark_window", "Mark window (s)", "float", flag="--mark-window",
              default=0.4, min=0.1, max=2.0, step=0.1,
              help="seconds around each mark counted as artifact"),
        # was CLI-only before the registry existed, so it never reached the
        # bench — exactly the drift one declaration is meant to prevent
        Field("marks", "Manual marks (seconds)", "floats", flag="--marks",
              advanced=True,
              help="times where you hear the artifact, e.g. '12.4 30.1'"),
        Field("threshold", "Threshold line", "float", flag="--threshold",
              default=0.6, min=0.0, max=1.0, step=0.05, advanced=True),
        Field("out", "Output PNG", "text", flag="--out", advanced=True),
    ],
)

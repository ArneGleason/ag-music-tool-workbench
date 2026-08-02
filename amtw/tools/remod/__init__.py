"""HF re-modulation — expands and voice-tracks the high band's envelope.

Unproven, and for the same reason as de-fizz: every test predates the
periodicity-gate fix, so the processing barely ran.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from ...core import audio_utils
from ...core.paths import OUTPUT_DIR
from ...spec import AUDIO, Field, Tool


def run(args: argparse.Namespace) -> int:
    from . import hfmod

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2
    outdir = Path(args.outdir).resolve() if args.outdir else (OUTPUT_DIR / f"remod_{src.stem}")
    outdir.mkdir(parents=True, exist_ok=True)

    data, sr = audio_utils.load(src)
    made = [audio_utils.save(outdir / "00_ORIGINAL.wav", data, sr)]

    # each variant isolates a mechanism: expansion alone, voice-tracking
    # alone, then both — so the A/B says which one (if either) matters
    variants = [
        ("01_expand_only", dict(expand=args.expand, track=0.0)),
        ("02_track_only", dict(expand=1.0, track=1.0)),
        ("03_both", dict(expand=args.expand, track=args.track)),
        ("04_both_strong", dict(expand=args.expand + 0.8, track=min(1.0, args.track + 0.3))),
    ]
    for name, kw in variants:
        t0 = time.time()
        out, gated = hfmod.process(data, sr, f_lo=args.f_lo, strength=1.0,
                                   per_lo=args.per_lo, per_hi=args.per_hi, **kw)
        # deepening modulation raises peaks; hold the original RMS and keep a
        # -0.5 dBFS ceiling so variants stay level-matched and never clip
        rms_in = float(np.sqrt((data.astype(np.float64) ** 2).mean()))
        rms_out = float(np.sqrt((out.astype(np.float64) ** 2).mean())) + 1e-12
        out = out * (rms_in / rms_out)
        peak = float(np.abs(out).max())
        ceiling = 10 ** (-0.5 / 20)
        if peak > ceiling:
            out = out * (ceiling / peak)
        p = audio_utils.save(outdir / f"{name}.wav", out.astype(np.float32), sr)
        made.append(p)
        print(f"  {name:<16} expand={kw['expand']:.1f} track={kw['track']:.1f}"
              f"  ({gated * 100:.0f}% frames gated, {time.time() - t0:.0f}s)")

    print("\ncompare:\n  .\\amtw.ps1 ab " + " ".join(f'"{p}"' for p in made))
    return 0


TOOL = Tool(
    name="remod", title="HF re-modulation", group="Fry repair", run=run, order=40,
    help="HF re-modulation for the fry scrape artifact",
    blurb="Expands and voice-tracks the high band's envelope, rendering four "
          "variants that isolate each mechanism.",
    note="Also unproven, and also only ever run through the broken gate.",
    fields=[
        Field("input", "Vocal stem", "file", accept=AUDIO, root="input",
              required=True),
        Field("f_lo", "Band bottom Hz", "float", flag="--f-lo", default=4500.0,
              help="the wash sits ~5-12 kHz"),
        Field("expand", "Envelope expansion", "float", flag="--expand", default=1.8,
              min=1.0, max=4.0, step=0.1,
              help="envelope expansion ratio (1.0 = off)"),
        Field("track", "Voice tracking", "float", flag="--track", default=0.5,
              min=0.0, max=1.0, step=0.05,
              help="0-1: how much the band follows the voice's low-band motion"),
        Field("per_lo", "Periodicity ramp low", "float", flag="--per-lo",
              default=0.60, min=0.0, max=1.0, step=0.01, advanced=True,
              help="gate ramp start; raspy singing measures ~0.70, clean ~0.93"),
        Field("per_hi", "Periodicity ramp high", "float", flag="--per-hi",
              default=0.92, min=0.0, max=1.0, step=0.01, advanced=True),
        Field("outdir", "Output folder", "dir", flag="--outdir", root="output",
              advanced=True),
    ],
)

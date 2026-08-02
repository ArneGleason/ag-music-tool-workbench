"""Fry scrape repair — the first mechanism the user approved.

Pushes fry-gated frames toward the harmonic component, targeting the measured
HNR deficit (4.6 dB in marked scratchy segments vs 9.0-9.3 dB in clean voiced
singing). See docs/findings.md before changing any default here.
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
    from . import harmonic

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2
    outdir = Path(args.outdir).resolve() if args.outdir else (OUTPUT_DIR / f"harm_{src.stem}")
    outdir.mkdir(parents=True, exist_ok=True)

    spans = None
    if args.from_notes:
        import json

        notes = json.loads(Path(args.from_notes).read_text(encoding="utf-8"))
        spans = []
        for mk in notes.get("markers", []):
            txt = str(mk.get("text", "")).strip().lower()
            if txt.startswith("clean") or "saturation" in txt or "pop" in txt:
                continue
            t0 = float(mk["t"])
            t1 = float(mk["t_end"]) if isinstance(mk.get("t_end"), (int, float)) \
                and mk["t_end"] > t0 else t0 + 0.3
            spans.append((t0, t1))
        total = sum(b - a for a, b in spans)
        print(f"marked-span mode: {len(spans)} spans, {total:.1f}s "
              f"— everything else is returned untouched")

    data, sr = audio_utils.load(src)
    made = [audio_utils.save(outdir / "00_ORIGINAL.wav", data, sr)]
    jobs = [(f"{int(round(s * 100)):03d}_harmonic", s, None) for s in args.strengths]
    if args.adaptive:
        jobs.append(("adaptive", 1.0, (args.min_strength, args.max_strength)))

    for name, s, adapt in jobs:
        t0 = time.time()
        out, gated = harmonic.process(data, sr, f_lo=args.f_lo, strength=s,
                                      per_lo=args.per_lo, per_hi=args.per_hi,
                                      mask_floor=args.mask_floor,
                                      gate_floor=args.gate_floor, spans=spans,
                                      adapt=adapt)
        # deliberately NO global level normalisation here: it would rescale
        # the untouched regions too, breaking the guarantee that clean
        # material comes through as the original samples. The mask only ever
        # reduces the noise component, so the peak cannot grow.
        peak = float(np.abs(out).max())
        ceiling = 10 ** (-0.5 / 20)
        if peak > ceiling:
            print(f"    (peak {peak:.3f} over ceiling — scaling, which does "
                  f"touch untouched regions)")
            out = out * (ceiling / peak)
        same = float(np.mean(np.isclose(out, data, atol=1e-7)))
        p = audio_utils.save(outdir / f"{name}.wav", out.astype(np.float32), sr)
        made.append(p)
        label = f"adaptive {adapt[0]:.2f}-{adapt[1]:.2f}" if adapt else f"strength {s:.2f}"
        print(f"  {label:<22} -> {p.name}  ({gated * 100:.0f}% gated, "
              f"{same * 100:.0f}% of samples untouched, {time.time() - t0:.0f}s)")
    print("\ncompare:\n  .\\amtw.ps1 ab " + " ".join(f'"{p}"' for p in made))
    return 0


TOOL = Tool(
    name="harmonic", title="Fry scrape repair", group="Fry repair", run=run, order=10,
    help="harmonic enhancement on fry-gated frames",
    blurb="Pushes fry-gated frames toward the harmonic component, targeting the "
          "measured HNR deficit in scratchy passages.",
    note="The settled workflow: mark the scratchy spots in the A/B tool first, "
         "then point this at that notes file with Adaptive on. Marks decide "
         "where, the detector decides how much. Everything outside a mark comes "
         "back bit-identical.",
    fields=[
        Field("input", "Vocal stem", "file", accept=AUDIO, root="input",
              required=True),
        Field("from_notes", "A/B notes (marked spans)", "file", flag="--from-notes",
              accept=["json"], root="ab_notes",
              help="process ONLY these marked segments — 98% precision vs 17% "
                   "for the detector alone"),
        Field("adaptive", "Adaptive strength", "bool", flag="--adaptive",
              default=True,
              help="scale strength with how severe and sustained the scrape is "
                   "— tested best"),
        Field("strengths", "Fixed strengths to also render", "floats",
              flag="--strengths", default=[0.5, 0.8, 1.0]),
        Field("min_strength", "Adaptive min", "float", flag="--min-strength",
              default=0.5, min=0.0, max=1.0, step=0.05, advanced=True),
        Field("max_strength", "Adaptive max", "float", flag="--max-strength",
              default=1.0, min=0.0, max=1.0, step=0.05, advanced=True),
        Field("gate_floor", "Gate floor", "float", flag="--gate-floor", default=0.30,
              min=0.0, max=1.0, step=0.05, advanced=True,
              help="weaker detections become exactly zero, so clean material "
                   "passes through untouched"),
        Field("per_lo", "Periodicity ramp low", "float", flag="--per-lo", default=0.60,
              min=0.0, max=1.0, step=0.01, advanced=True,
              help="raspy singing measures ~0.70, clean ~0.93"),
        Field("per_hi", "Periodicity ramp high", "float", flag="--per-hi", default=0.92,
              min=0.0, max=1.0, step=0.01, advanced=True),
        Field("mask_floor", "Mask floor", "float", flag="--mask-floor", default=0.35,
              min=0.0, max=1.0, step=0.05, advanced=True,
              help="lowest the noise component can be pushed (0.35 caps "
                   "reduction near 9 dB; lower = stronger correction)"),
        Field("f_lo", "Crossover Hz", "float", flag="--f-lo", default=1500.0,
              advanced=True),
        Field("outdir", "Output folder", "dir", flag="--outdir", root="output",
              advanced=True),
    ],
)

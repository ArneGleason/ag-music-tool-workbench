"""HF de-fizz — narrowband spectral smear above a crossover. Unproven."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ...core import audio_utils
from ...core.paths import OUTPUT_DIR
from ...spec import AUDIO, Field, Tool


def run(args: argparse.Namespace) -> int:
    from . import defizz

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    outdir = Path(args.outdir).resolve() if args.outdir else (OUTPUT_DIR / f"defizz_{src.stem}")
    outdir.mkdir(parents=True, exist_ok=True)

    data, sr = audio_utils.load(src)
    made = [audio_utils.save(outdir / f"00_original_{src.stem}.wav", data, sr)]

    for s in args.strengths:
        t0 = time.time()
        out, gated = defizz.process(data, sr, f_lo=args.f_lo, strength=s,
                                    smear_hz=args.smear)
        tag = f"{int(round(s * 100)):03d}"
        p = audio_utils.save(outdir / f"{tag}_defizz_{src.stem}.wav", out, sr)
        made.append(p)
        print(f"  strength {s:.2f} -> {p.name}   ({gated * 100:.0f}% of frames gated as fry,"
              f" {time.time() - t0:.0f}s)")

    print(f"\ncompare them with:\n  .\\amtw.ps1 ab " +
          " ".join(f'"{p}"' for p in made))
    return 0


TOOL = Tool(
    name="defizz", title="HF de-fizz", group="Fry repair", run=run, order=30,
    help="fry-gated HF de-fizz, rendered at several strengths",
    blurb="Narrowband spectral smear above a crossover, rendered at several "
          "strengths for A/B.",
    note="Not yet shown to work — every earlier test ran through the broken "
         "periodicity gate, so it deserves a retest rather than trust.",
    fields=[
        Field("input", "Vocal stem", "file", accept=AUDIO, root="input",
              required=True),
        Field("strengths", "Strengths", "floats", flag="--strengths",
              default=[0.35, 0.6, 0.85],
              help="blend amounts to render for A/B (0=off, 1=full)"),
        Field("f_lo", "Crossover Hz", "float", flag="--f-lo", default=7000.0,
              help="crossover; only content above this is touched"),
        Field("smear", "Smear width Hz", "float", flag="--smear", default=400.0,
              min=100, max=2000, step=50,
              help="400 subtle, 1200 aggressive"),
        Field("outdir", "Output folder", "dir", flag="--outdir", root="output",
              advanced=True),
    ],
)

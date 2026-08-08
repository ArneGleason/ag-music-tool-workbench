"""Drum stem tools: profile what is wrong, then remove instrument bleed.

`drum-profile` exists because the user's brief was right — there is no one
size fits all. It measures where the bleed actually is before anything is
processed, and on the first real case that immediately ruled out the obvious
approach: the contamination was entirely below 150 Hz, so a broadband denoise
would have damaged clean mids for nothing.
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


def run_profile(args: argparse.Namespace) -> int:
    import librosa

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    data, sr = audio_utils.load(src)
    mono = audio_utils.to_mono(data).astype(np.float32)
    dur = len(mono) / sr

    def db(v):
        return 20 * np.log10(max(float(v), 1e-12))

    print(f"{src.name}")
    print(f"  {dur:.1f}s  {sr} Hz  {'stereo' if data.ndim > 1 else 'mono'}  "
          f"peak {np.abs(mono).max():.3f}  rms {db(np.sqrt((mono**2).mean())):.1f} dB")

    S = librosa.stft(mono, n_fft=2048, hop_length=512)
    H, P = librosa.decompose.hpss(S, margin=args.margin)
    eh, ep = float(np.abs(H).sum()), float(np.abs(P).sum())
    print(f"\nharmonic share (bleed) overall: {100*eh/(eh+ep):.1f}%")
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    worst = None
    for name, lo, hi in [("sub <60", 0, 60), ("kick 60-150", 60, 150),
                         ("body .15-500", 150, 500), ("mid .5-2k", 500, 2000),
                         ("snap 2-6k", 2000, 6000), ("cymb 6-16k", 6000, 16000)]:
        m = (freqs >= lo) & (freqs < hi)
        h, p = float(np.abs(H[m]).sum()), float(np.abs(P[m]).sum())
        pct = 100 * h / (h + p + 1e-12)
        print(f"  {name:<14}{pct:>8.1f}% harmonic")
        # the crossover has to clear the HIGHEST contaminated band, not the
        # worst one. Picking the worst suggested 60 Hz while the 60-150 band
        # was still 59% harmonic, which would have left most of the bleed in.
        if hi <= 500 and pct > args.bleed_pct:
            worst = (hi, pct)

    env = librosa.onset.onset_strength(y=mono, sr=sr, hop_length=512)
    peaks = librosa.util.peak_pick(env, pre_max=3, post_max=3, pre_avg=5,
                                   post_avg=5, delta=0.15, wait=4)
    rms = librosa.feature.rms(y=mono, hop_length=512)[0]
    hits = np.array([db(rms[min(p, len(rms) - 1)]) for p in peaks])
    quiet = rms[rms < np.percentile(rms, 20)]
    floor = db(np.median(quiet))
    print(f"\nonsets: {len(peaks)} ({len(peaks)/dur*60:.0f}/min)")
    if len(hits):
        q5, q95 = np.percentile(hits, [5, 95])
        print(f"  quietest 5% of hits : {q5:.1f} dB")
        print(f"  loudest 5%          : {q95:.1f} dB")
        print(f"  floor between hits  : {floor:.1f} dB")
        print(f"  GHOST-NOTE HEADROOM : {q5 - floor:.1f} dB "
              f"({'plenty of margin' if q5 - floor > 12 else 'TIGHT - gate carefully'})")

    if worst:
        print(f"\n-> bleed runs up to {worst[0]} Hz. Use drum-clean with "
              f"--f-hi {worst[0]}; a broadband denoise would damage clean mids "
              f"for nothing.")
    else:
        print("\n-> no strong low-band bleed; drum-clean has little to remove.")
    return 0


def run_clean(args: argparse.Namespace) -> int:
    from . import drumclean

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2
    outdir = Path(args.outdir).resolve() if args.outdir else (
        OUTPUT_DIR / f"drumclean_{src.stem}")
    outdir.mkdir(parents=True, exist_ok=True)

    data, sr = audio_utils.load(src)
    made = [audio_utils.save(outdir / "00_ORIGINAL.wav", data, sr)]

    for s in args.strengths:
        t0 = time.time()
        out, st = drumclean.process(data, sr, f_hi=args.f_hi, strength=s,
                                    guard_ms=args.guard_ms,
                                    sensitivity=args.sensitivity,
                                    margin=args.margin)
        # never let a removal raise the peak; it only ever subtracts, but
        # istft rounding can nudge it
        peak = float(np.abs(out).max())
        ceiling = 10 ** (-0.5 / 20)
        if peak > ceiling:
            out = out * (ceiling / peak)
        tag = f"{int(round(s * 100)):03d}_clean"
        p = audio_utils.save(outdir / f"{tag}.wav", out.astype(np.float32), sr)
        made.append(p)
        print(f"  strength {s:.2f} -> {p.name}   removed {st['removed']*100:.1f}% "
              f"of total energy, {st['guarded']*100:.0f}% of frames guarded "
              f"as transients   ({time.time()-t0:.0f}s)")

    print("\ncompare:\n  .\\amtw.ps1 ab " + " ".join(f'"{p}"' for p in made))
    return 0


PROFILE = Tool(
    name="drum-profile", title="Profile a drum stem", group="Drums",
    run=run_profile, order=10,
    help="measure where the bleed is before processing anything",
    blurb="Reports how much of each band is harmonic rather than percussive — "
          "which on a drum stem means bleed — plus onset density and how much "
          "headroom the ghost notes have.",
    note="Run this first. On the first real case it showed the contamination "
         "was entirely below 150 Hz (91.6% of sub-60, 59.2% of 60-150), so a "
         "broadband denoise would have damaged clean mids for nothing. The "
         "ghost-note headroom line tells you whether any level-based "
         "processing is even safe.",
    fields=[
        Field("input", "Drum stem", "file", accept=AUDIO, root="input",
              required=True),
        Field("margin", "HPSS margin", "float", flag="--margin", default=3.0,
              min=1.0, max=8.0, step=0.5, advanced=True,
              help="higher separates harmonic from percussive more strictly"),
        Field("bleed_pct", "Call a band contaminated above (%)", "float",
              flag="--bleed-pct", default=40.0, min=10, max=90, step=5,
              advanced=True),
    ],
)

CLEAN = Tool(
    name="drum-clean", title="Remove drum-stem bleed", group="Drums",
    run=run_clean, order=20,
    help="remove sustained tonal bleed from a drum stem, between hits only",
    blurb="Subtracts the harmonic component below a crossover, but only where "
          "no hit is landing — so leaking bass goes and kick impact stays. "
          "Renders several strengths for A/B.",
    note="A kick's body is PITCHED, so blanket harmonic removal below 150 Hz "
         "guts the impact it is meant to protect. The onset guard is what "
         "makes this work: attenuation is switched off around every hit and "
         "only removes tone that persists between them, which is what leaking "
         "bass actually is. Run drum-profile first to find the right --f-hi.",
    fields=[
        Field("input", "Drum stem", "file", accept=AUDIO, root="input",
              required=True),
        Field("f_hi", "Bleed band top (Hz)", "float", flag="--f-hi",
              default=150.0, min=40, max=800, step=10,
              help="only below this is touched; drum-profile suggests a value"),
        Field("strengths", "Strengths to render", "floats", flag="--strengths",
              default=[0.5, 0.8, 1.0]),
        Field("guard_ms", "Transient guard (ms)", "float", flag="--guard-ms",
              default=60.0, min=0, max=250, step=5,
              help="how long after each hit to leave completely alone — this "
                   "is what preserves impact"),
        Field("sensitivity", "Onset sensitivity", "float", flag="--sensitivity",
              default=0.15, min=0.02, max=0.6, step=0.01, advanced=True,
              help="lower catches more ghost notes as hits to protect"),
        Field("margin", "HPSS margin", "float", flag="--margin", default=3.0,
              min=1.0, max=8.0, step=0.5, advanced=True),
        Field("outdir", "Output folder", "dir", flag="--outdir", root="output",
              advanced=True),
    ],
)

TOOLS = [PROFILE, CLEAN]

"""Command line interface.

    python -m amtw run input\\my_vocal.wav [options]
    python -m amtw report output\\my_vocal_20260703-101500
    python -m amtw doctor
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from . import audio_utils
from .config import PipelineCfg
from .job import Job
from .paths import OUTPUT_DIR


def cmd_run(args: argparse.Namespace) -> int:
    from .stages import cleanup, finalize, resynth, superres
    from . import report as report_mod

    cfg = PipelineCfg()
    cfg.cleanup.enabled = "cleanup" in args.stages
    cfg.superres.enabled = "superres" in args.stages
    cfg.resynth.enabled = "resynth" in args.stages
    from .config import DEREVERB_MODELS

    cfg.cleanup.denoise = args.denoise
    cfg.cleanup.deecho = args.deecho
    cfg.cleanup.dereverb_model = DEREVERB_MODELS[args.dereverb]
    cfg.resynth.engine = args.engine
    cfg.resynth.diffusion_steps = args.diffusion_steps
    cfg.resynth.inference_cfg_rate = args.cfg_rate
    cfg.resynth.semitone_shift = args.semitone_shift
    cfg.resynth.ref_seconds = args.ref_seconds
    cfg.resynth.reference_wav = args.reference or ""

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    if args.sr:
        cfg.finalize.output_sr = args.sr
    elif args.match_input_sr:
        import soundfile as sf
        cfg.finalize.output_sr = sf.info(str(src)).samplerate

    job = Job.create(src, name=args.name)
    print(f"job: {job.root}")

    t0 = time.time()
    current = audio_utils.ffmpeg_to_wav(src, job.dir("input") / f"{src.stem}.wav")
    original = current
    print(f"[00 input   ] decoded -> {current.name}")

    if cfg.cleanup.enabled:
        current = cleanup.run(cfg, job, current)
        print(f"[10 cleanup ] -> {current.name}")
    if cfg.superres.enabled:
        current = superres.run(cfg, job, current)
        print(f"[20 superres] -> {current.name}")
    if cfg.resynth.enabled:
        current = resynth.run(cfg, job, current)
        print(f"[30 resynth ] -> {current.name}")

    final = finalize.run(cfg, job, current, original)
    print(f"[40 final   ] -> {final.name}")

    rep = report_mod.build(job)
    print(f"[report     ] -> {rep}")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    import json

    from . import report as report_mod

    root = Path(args.jobdir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    job = Job(source=Path(manifest["source"]), root=root, manifest=manifest)
    rep = report_mod.build(job)
    print(rep)
    return 0


def cmd_defizz(args: argparse.Namespace) -> int:
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


def cmd_harmonic(args: argparse.Namespace) -> int:
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


def cmd_detect(args: argparse.Namespace) -> int:
    """Plot the fry-detector features so they can be checked against where the
    artifact is actually audible, instead of trusting a threshold blind."""
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

    marks = [a for a, _ in spans]
    clean_marks = [a for a, _ in clean_spans]

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


def cmd_remod(args: argparse.Namespace) -> int:
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


def cmd_ab(args: argparse.Namespace) -> int:
    from .abtool import serve

    return serve(args.files, port=args.port, notes=args.notes)


def cmd_workbench(args: argparse.Namespace) -> int:
    from .workbench import serve

    return serve(port=args.port, open_browser=not args.no_open)


def cmd_midi_merge(args: argparse.Namespace) -> int:
    from . import midi

    for p in args.inputs:
        if not Path(p).exists():
            print(f"input not found: {p}", file=sys.stderr)
            return 2
    try:
        midi.merge(
            args.inputs, out=args.out, tracks=args.tracks, dup=args.dup, gap=args.gap,
            min_len=args.min_len, velocity=args.velocity, align=args.align,
            bpm=args.bpm, ppq=args.ppq, channel=args.channel, keep_cc=not args.no_cc,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


def cmd_midi_inspect(args: argparse.Namespace) -> int:
    from . import midi

    for p in args.inputs:
        info = midi.describe(p)
        print(f"{info['path']}\n  type={info['type']} ppq={info['ppq']} "
              f"tracks={len(info['tracks'])} length={info['length']:.1f}s")
        for t in info["tracks"]:
            if t["notes"]:
                print(f"  [{t['index']}] {t['name']!r}: {t['notes']} notes, "
                      f"pitch {t['low']}-{t['high']}, "
                      f"ticks {t['first_tick']}-{t['last_tick']}")
            else:
                extra = f", {t['tempo_events']} tempo events" if t["tempo_events"] else ""
                print(f"  [{t['index']}] {t['name']!r}: no notes{extra}")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    import subprocess

    from .paths import (APOLLO_CKPT, APOLLO_CONFIG, MSST_DIR, RUNTIME_ROOT,
                        SEEDVC_DIR, venv_python)

    ok = True

    def check(label: str, cond: bool, extra: str = "") -> None:
        nonlocal ok
        mark = "ok " if cond else "FAIL"
        print(f"  [{mark}] {label}{(' — ' + extra) if extra else ''}")
        ok = ok and cond

    print(f"runtime root: {RUNTIME_ROOT}")
    for env in ("main", "msst", "seedvc"):
        py = venv_python(env)
        if not py.exists():
            check(f"venv {env}", False, "missing")
            continue
        try:
            out = subprocess.run(
                [str(py), "-c",
                 "import torch; print(torch.__version__, torch.cuda.is_available())"],
                capture_output=True, text=True, timeout=120,
            ).stdout.strip()
            check(f"venv {env}", "True" in out, f"torch {out}")
        except Exception as e:  # noqa: BLE001
            check(f"venv {env}", False, str(e))

    check("seed-vc clone", (SEEDVC_DIR / "inference.py").exists())
    check("msst clone", (MSST_DIR / "inference.py").exists())
    check("apollo ckpt", APOLLO_CKPT.exists())
    check("apollo config", APOLLO_CONFIG.exists())

    try:
        import audio_separator  # noqa: F401
        check("audio-separator importable (main env)", True)
    except ImportError:
        check("audio-separator importable (main env)", False,
              "run amtw from the main venv python")
    print("all good" if ok else "problems found — see FAIL lines")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="amtw", description="AG Music Tool Workbench — music production tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="run the pipeline on a vocal stem")
    pr.add_argument("input", help="path to vocal stem (wav/mp3/flac/m4a)")
    pr.add_argument("--stages", nargs="+", default=["cleanup", "superres", "resynth"],
                    help="stages to run, space- or comma-separated "
                         "(default: cleanup superres resynth)")
    pr.add_argument("--name", default=None, help="job name (default: <stem>_<timestamp>)")
    pr.add_argument("--denoise", action="store_true", help="add UVR-DeNoise pass after de-reverb")
    pr.add_argument("--deecho", action="store_true",
                    help="add de-echo pass (Sucial roformer) for short slap/early "
                         "reflections that resynth can re-render as doubling")
    pr.add_argument("--dereverb", choices=["classic", "roformer"], default="classic",
                    help="stage-1 de-reverb model: classic UVR VR (default) or "
                         "anvuew mel-band roformer (higher SDR)")
    pr.add_argument("--engine", choices=["seedvc", "yingmusic"], default="seedvc",
                    help="resynth engine")
    pr.add_argument("--sr", type=int, default=0,
                    help="resample final deliverable to this rate (e.g. 48000); "
                         "0 keeps the pipeline's native 44100")
    pr.add_argument("--match-input-sr", action="store_true",
                    help="resample final deliverable to the source stem's rate")
    pr.add_argument("--diffusion-steps", type=int, default=50)
    pr.add_argument("--cfg-rate", type=float, default=0.7,
                    help="seed-vc guidance: lower can keep more source grit/rasp, "
                         "higher pushes harder toward the reference timbre")
    pr.add_argument("--semitone-shift", type=int, default=0)
    pr.add_argument("--ref-seconds", type=float, default=25.0)
    pr.add_argument("--reference", default=None,
                    help="explicit reference wav for timbre (default: auto-picked from the stem)")
    pr.set_defaults(fn=cmd_run)

    pp = sub.add_parser("report", help="(re)build report.html for a job dir")
    pp.add_argument("jobdir")
    pp.set_defaults(fn=cmd_report)

    pdf = sub.add_parser("defizz", help="fry-gated HF de-fizz, rendered at several strengths")
    pdf.add_argument("input")
    pdf.add_argument("--strengths", type=float, nargs="+", default=[0.35, 0.6, 0.85],
                     help="blend amounts to render for A/B (0=off, 1=full)")
    pdf.add_argument("--f-lo", type=float, default=7000.0, dest="f_lo",
                     help="crossover; only content above this is touched")
    pdf.add_argument("--smear", type=float, default=400.0,
                     help="width of the frequency-axis blur in Hz; wider dissolves "
                          "a broader resonance (400 subtle, 1200 aggressive)")
    pdf.add_argument("--outdir", default=None)
    pdf.set_defaults(fn=cmd_defizz)

    ph = sub.add_parser("harmonic", help="harmonic enhancement on fry-gated frames")
    ph.add_argument("input")
    ph.add_argument("--strengths", type=float, nargs="+", default=[0.5, 0.8, 1.0])
    ph.add_argument("--f-lo", type=float, default=1500.0, dest="f_lo")
    ph.add_argument("--per-lo", type=float, default=0.60, dest="per_lo")
    ph.add_argument("--per-hi", type=float, default=0.92, dest="per_hi")
    ph.add_argument("--mask-floor", type=float, default=0.35, dest="mask_floor",
                    help="lowest the noise component can be pushed (0.35 caps "
                         "reduction near 9 dB; lower = stronger correction)")
    ph.add_argument("--from-notes", default=None, dest="from_notes",
                    help="A/B tool notes JSON: process ONLY the marked segments "
                         "and return everything else bit-identical")
    ph.add_argument("--gate-floor", type=float, default=0.30, dest="gate_floor",
                    help="detections weaker than this are ignored entirely, so "
                         "clean material passes through untouched (0 = old ramp)")
    ph.add_argument("--adaptive", action="store_true",
                    help="also render a version whose strength scales with how "
                         "severe and sustained the scrape is")
    ph.add_argument("--min-strength", type=float, default=0.5, dest="min_strength")
    ph.add_argument("--max-strength", type=float, default=1.0, dest="max_strength")
    ph.add_argument("--outdir", default=None)
    ph.set_defaults(fn=cmd_harmonic)

    pdt = sub.add_parser("detect", help="plot the fry-detector features against your marks")
    pdt.add_argument("input")
    pdt.add_argument("--marks", nargs="*", default=None,
                     help="times (seconds) where you hear the artifact")
    pdt.add_argument("--from-notes", default=None, dest="from_notes",
                     help="an ab_notes JSON from the A/B tool; markers become "
                          "artifact examples unless the note starts with 'clean'")
    pdt.add_argument("--mark-window", type=float, default=0.4,
                     help="seconds around each mark counted as artifact")
    pdt.add_argument("--threshold", type=float, default=0.6)
    pdt.add_argument("--out", default=None)
    pdt.set_defaults(fn=cmd_detect)

    prm = sub.add_parser("remod", help="HF re-modulation for the fry scrape artifact")
    prm.add_argument("input")
    prm.add_argument("--f-lo", type=float, default=4500.0, dest="f_lo",
                     help="bottom of the treated band (the wash sits ~5-12 kHz)")
    prm.add_argument("--expand", type=float, default=1.8,
                     help="envelope expansion ratio (1.0 = off)")
    prm.add_argument("--track", type=float, default=0.5,
                     help="0-1: how much the band follows the voice's low-band motion")
    prm.add_argument("--per-lo", type=float, default=0.60, dest="per_lo",
                     help="gate ramp start; raspy singing measures ~0.70, clean ~0.93")
    prm.add_argument("--per-hi", type=float, default=0.92, dest="per_hi")
    prm.add_argument("--outdir", default=None)
    prm.set_defaults(fn=cmd_remod)

    pab = sub.add_parser("ab", help="A/B compare aligned audio files in the browser")
    pab.add_argument("files", nargs="+", help="audio files to compare (2+)")
    pab.add_argument("--port", type=int, default=8731)
    pab.add_argument("--notes", default=None,
                     help="path for the notes JSON (default: output/ab_notes/<timestamp>.json)")
    pab.set_defaults(fn=cmd_ab)

    pw = sub.add_parser("workbench", help="open the tool workbench in the browser")
    pw.add_argument("--port", type=int, default=8730)
    pw.add_argument("--no-open", action="store_true", help="don't open a browser tab")
    pw.set_defaults(fn=cmd_workbench)

    pm = sub.add_parser("midi-merge",
                        help="merge duplicate stem-to-MIDI tracks into one clean track")
    pm.add_argument("inputs", nargs="+", help="one or two .mid files")
    pm.add_argument("--tracks", nargs="+", type=int,
                    help="track indices to merge (single-file mode); "
                         "default = every track with notes")
    pm.add_argument("--out", default=None, help="default: <input>.merged.mid")
    pm.add_argument("--dup", default="1/16",
                    help="same-pitch notes starting within this are one note "
                         "(default 1/16; also '0.25' beats or '48t' ticks)")
    pm.add_argument("--gap", default="1/128",
                    help="silence left when truncating a held note at a restrike")
    pm.add_argument("--min-len", default="1/64", dest="min_len",
                    help="drop notes shorter than this after merging")
    pm.add_argument("--velocity", default="max",
                    choices=["max", "min", "first", "avg", "longest"],
                    help="velocity kept when two notes collapse (default max)")
    pm.add_argument("--align", default="auto", choices=["auto", "ticks", "time"],
                    help="auto: ticks when the tempo maps match, seconds when they don't")
    pm.add_argument("--bpm", type=float, default=None,
                    help="output tempo when re-timing in seconds")
    pm.add_argument("--ppq", type=int, default=None, help="output ticks per beat")
    pm.add_argument("--channel", type=int, default=0)
    pm.add_argument("--no-cc", action="store_true", dest="no_cc",
                    help="drop controllers (sustain pedal etc.)")
    pm.set_defaults(fn=cmd_midi_merge)

    pmi = sub.add_parser("midi-inspect", help="list a MIDI file's tracks")
    pmi.add_argument("inputs", nargs="+")
    pmi.set_defaults(fn=cmd_midi_inspect)

    pd = sub.add_parser("doctor", help="check venvs, clones, models, CUDA")
    pd.set_defaults(fn=cmd_doctor)

    args = p.parse_args(argv)
    if hasattr(args, "stages"):
        # tolerate both "--stages a b" and "--stages a,b" (PowerShell splits
        # comma lists into separate argv tokens anyway)
        args.stages = [t.strip() for s in args.stages for t in s.split(",") if t.strip()]
    return args.fn(args)

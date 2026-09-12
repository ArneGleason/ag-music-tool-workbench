"""MIDI repair tools.

Three commands in one package because they share `midi.py` — cleaning,
merging and inspecting are the same reader with different output.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ...spec import Field, Tool


def run_merge(args: argparse.Namespace) -> int:
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


def _song_key(path: Path) -> str:
    # "Title (Bass).mid" -> "Title": stems of one export share everything
    # before the instrument parenthetical
    import re
    return re.sub(r"\s*\([^)]*\)\s*$", "", path.stem)


def run_clean(args: argparse.Namespace) -> int:
    from . import clean as clean_mod

    paths = [Path(p) for p in args.inputs]
    missing = [p for p in paths if not p.exists()]
    for p in missing:
        print(f"input not found: {p}", file=sys.stderr)
    paths = [p for p in paths if p.exists()]
    out_dir = Path(args.out_dir) if args.out_dir else None

    # Alignment: measure each stem against its own wav, then trust the song,
    # not the stem — all stems of one export agree to ~25 ms, so the median
    # survives a bad transcription (one lead vocal measured +1.4 s where its
    # siblings said +0.22).
    shifts: dict[Path, float] = {}
    if args.align == "auto":
        measured: dict[str, list[tuple[Path, float, float]]] = {}
        for p in paths:
            wav = p.with_suffix(".wav")
            if not wav.exists():
                print(f"  (no {wav.name} beside it — not aligned)")
                continue
            off, prom = clean_mod.estimate_offset(p, wav)
            measured.setdefault(_song_key(p), []).append((p, off, prom))
        import statistics
        for song, rows in measured.items():
            med = statistics.median(off for _, off, _ in rows)
            for p, off, prom in rows:
                flag = ""
                if abs(off - med) > 0.1 or prom < 1.5:
                    flag = f"  <- outlier (measured {off:+.3f}s, x{prom:.1f}); using the song median"
                print(f"  offset {med:+.3f}s  {p.name}{flag}")
                shifts[p] = med
    elif args.align not in ("off", ""):
        try:
            fixed = float(args.align)
        except ValueError:
            print(f"--align must be auto, off, or seconds; got {args.align!r}", file=sys.stderr)
            return 2
        shifts = {p: fixed for p in paths}

    failed = len(missing)
    for path in paths:
        out = out_dir / (path.stem + ".clean.mid") if out_dir else None
        try:
            clean_mod.clean(
                path, out=out,
                profile=None if args.profile == "auto" else args.profile,
                flicker_ms=args.flicker_ms if args.flicker_ms >= 0 else None,
                tail_gap_ms=args.tail_gap_ms if args.tail_gap_ms >= 0 else None,
                voices=args.voices if args.voices >= 0 else None,
                drum_len_ms=args.drum_len_ms, gap=args.gap,
                shift_s=shifts.get(path, 0.0),
            )
        except ValueError as e:
            print(f"{path.name}: {e}", file=sys.stderr)
            failed += 1
    return 2 if failed else 0


def run_inspect(args: argparse.Namespace) -> int:
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


MERGE = Tool(
    name="midi-merge", title="MIDI track merge", group="MIDI", run=run_merge, order=10,
    help="merge duplicate stem-to-MIDI tracks into one clean track",
    blurb="Folds a stem-to-MIDI export's duplicate tracks into one clean track "
          "with no same-pitch overlaps.",
    note="Suno splits one instrument across two tracks — bass low, voicing high — "
         "then starts writing the same notes to both, which double-triggers the "
         "instrument. Same-pitch notes starting within the duplicate window "
         "collapse (longest tail wins); a later one outside it truncates the held "
         "note instead and inherits its tail.",
    fields=[
        Field("inputs", "MIDI file(s)", "files", accept=["mid", "midi"],
              root="downloads", required=True,
              help="one file (choose tracks below) or two files"),
        Field("tracks", "Tracks to merge", "ints", flag="--tracks",
              help="single-file mode: e.g. '1 2'. Blank = every track with notes"),
        Field("out", "Output file", "text", flag="--out",
              help="blank = <input>.merged.mid"),
        Field("dup", "Duplicate window", "choice", flag="--dup",
              choices=["1/8", "1/16", "1/32", "1/64"], default="1/16",
              help="same-pitch notes starting within this are one note"),
        Field("velocity", "Velocity when collapsing", "choice", flag="--velocity",
              choices=["max", "min", "first", "avg", "longest"], default="max"),
        Field("align", "Alignment", "choice", flag="--align",
              choices=["auto", "ticks", "time"], default="auto",
              help="auto uses ticks when tempo maps match, seconds when they don't"),
        Field("gap", "Restrike gap", "text", flag="--gap", default="1/128",
              advanced=True, help="silence left when truncating a held note"),
        Field("min_len", "Minimum note length", "text", flag="--min-len",
              default="1/64", advanced=True),
        Field("bpm", "Output BPM", "float", flag="--bpm", advanced=True,
              help="only used when re-timing in seconds"),
        Field("ppq", "Output PPQ", "int", flag="--ppq", advanced=True),
        Field("channel", "Output channel", "int", flag="--channel", default=0,
              min=0, max=15, step=1, advanced=True),
        Field("no_cc", "Drop controllers (pedal etc.)", "bool", flag="--no-cc",
              advanced=True),
    ],
)

CLEAN = Tool(
    name="midi-clean", title="MIDI stem clean", group="MIDI", run=run_clean, order=5,
    help="instrument-aware cleanup of Suno per-stem MIDI exports",
    blurb="Drop a Suno Stems folder's MIDI files in: each is lined up with its "
          "wav, tracks fold to one, tail re-detections extend the note instead of "
          "flickering, stray sub-30 ms notes go, and polyphony is capped per "
          "instrument (lead vocal 1, bass 2, guitar 6). Drums keep their 1 ms triggers.",
    note="Suno's MIDI runs EARLY against its own wav by a per-song constant "
         "(0.1–0.55 s measured) — select the whole folder so the offset comes "
         "from every stem at once. Instrument is read from the (Name) in the "
         "filename. The exports carry no pitch bend and one velocity value, so "
         "this fixes timing and voicing only. Writes <name>.clean.mid beside the input.",
    fields=[
        Field("inputs", "MIDI file(s)", "files", accept=["mid", "midi"],
              root="downloads", required=True,
              help="select every .mid in a Suno Stems folder at once"),
        Field("profile", "Instrument", "choice", flag="--profile",
              choices=["auto", "lead", "backing", "bass", "guitar", "keys", "fx", "drums"],
              default="auto", help="auto reads the (Name) in the filename"),
        Field("out_dir", "Output folder", "text", flag="--out-dir",
              help="blank = next to each input"),
        Field("align", "Align to wav", "text", flag="--align", default="auto",
              help="auto = measure against the wav of the same name; off; or seconds to add"),
        Field("voices", "Voice cap override", "int", flag="--voices", default=-1,
              min=-1, max=32, step=1, advanced=True,
              help="-1 = the instrument's default; 0 = unlimited; 1 = mono legato"),
        Field("flicker_ms", "Flicker threshold ms", "float", flag="--flicker-ms",
              default=-1.0, min=-1.0, max=200.0, step=5.0, advanced=True,
              help="notes shorter than this are tails or noise; -1 = default 30"),
        Field("tail_gap_ms", "Tail gap ms", "float", flag="--tail-gap-ms",
              default=-1.0, min=-1.0, max=500.0, step=10.0, advanced=True,
              help="same-pitch flicker within this after a note is its tail; -1 = 100"),
        Field("drum_len_ms", "Drum gate ms", "float", flag="--drum-len-ms",
              default=0.0, min=0.0, max=200.0, step=5.0, advanced=True,
              help="stretch 1 ms drum triggers to at least this; 0 = leave"),
        Field("gap", "Restrike gap", "text", flag="--gap", default="1/128",
              advanced=True, help="silence left when a note is cut at the next onset"),
    ],
)

INSPECT = Tool(
    name="midi-inspect", title="MIDI inspect", group="MIDI", run=run_inspect, order=20,
    help="list a MIDI file's tracks",
    blurb="Lists a MIDI file's tracks — note counts, pitch range, span — so you "
          "know which ones to merge.",
    fields=[
        Field("inputs", "MIDI file(s)", "files", accept=["mid", "midi"],
              root="downloads", required=True),
    ],
)

TOOLS = [CLEAN, MERGE, INSPECT]

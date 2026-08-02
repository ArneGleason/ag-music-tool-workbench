"""MIDI repair tools.

Two commands in one package because they share `midi.py` — merging and
inspecting are the same reader with different output.
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

TOOLS = [MERGE, INSPECT]

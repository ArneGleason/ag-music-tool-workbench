"""Harmonic readout for music written as independent lines.

`harm-read` takes a MIDI file whose tracks are voices and reports, bar by bar,
what those lines are making and what it could still be. It is the opposite of a
chord generator: nothing here suggests a next chord.

The design brief came from a real session. Naming the chords turned out to be
the least useful thing — what moved the work were the *questions*: is the
key-defining tritone ever actually held? where does the leading tone live?
which keys does this bar still fit? which single note would move it somewhere
else? Those are flags on this tool, not separate features.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ...spec import Field, Tool

MIDI = ["mid", "midi"]


def _fmt_voices(voices, meta) -> None:
    print(f"{len(voices)} voices · {meta['time_signature']} · ppq {meta['ppq']}", end="")
    if meta["tempo_events"]:
        lo, hi = meta["bpm_min"], meta["bpm_max"]
        rng = f"{lo}" if lo == hi else f"{lo}-{hi}"
        print(f" · {meta['tempo_events']} tempo events ({rng} bpm)", end="")
    print("\n")
    for v in voices:
        print(f"  [{v.index}] {v.label[:46]:<46} {len(v.notes):>4} notes")
    print()


def run(args: argparse.Namespace) -> int:
    from . import analysis as A

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    voices, bar_ticks, meta = A.read(src)
    if not voices:
        print("no notes in this file", file=sys.stderr)
        return 2

    if args.voices:
        keep = set(args.voices)
        voices = [v for v in voices if v.index in keep]
        if not voices:
            print(f"no voices matched {sorted(keep)}", file=sys.stderr)
            return 2

    lo = hi = None
    if args.bars:
        text = args.bars.replace(" ", "")
        lo, _, rest = text.partition("-")
        lo, hi = int(lo), int(rest) if rest else int(lo)

    candidates = args.keys or None
    rows = A.bars(voices, bar_ticks, lo, hi)

    if not args.json:
        _fmt_voices(voices, meta)

    # ---- the readout -----------------------------------------------------
    out_rows = []
    for bar in rows:
        if not bar.notes:
            continue
        fits = A.key_fits(bar.pcs, candidates)
        chord = A.name_chord(bar.pcs, bar.bass)
        narrow = A.narrowing_voices(bar, voices, candidates)
        out_rows.append({
            "bar": bar.number,
            "chord": chord,
            "pitches": [A.PCS[p] for p in sorted(bar.pcs)],
            "fits": fits,
            "ambiguity": len(fits),
            "narrowed_by": {
                next(v.label for v in voices if v.index == i): keys
                for i, keys in narrow.items()
            },
        })

    if args.json:
        payload = {"file": str(src), "meta": meta, "bar_ticks": bar_ticks,
                   "voices": [{"index": v.index, "name": v.label} for v in voices],
                   "bars": out_rows}
        print(json.dumps(payload, indent=2))
        return 0

    print(f"{'bar':>5}  {'chord':<12} {'pitches':<22} {'fits':<3} keys")
    for r in out_rows:
        print(f"{r['bar']:>5}  {r['chord']:<12} {' '.join(r['pitches']):<22} "
              f"{r['ambiguity']:>3}  {' '.join(r['fits'])}")

    if out_rows:
        widest = max(out_rows, key=lambda r: r["ambiguity"])
        tightest = min(out_rows, key=lambda r: r["ambiguity"])
        print(f"\nwidest  bar {widest['bar']} ({widest['chord']}) — "
              f"{widest['ambiguity']} keys fit")
        print(f"tightest bar {tightest['bar']} ({tightest['chord']}) — "
              f"{tightest['ambiguity']} keys fit")
        first, last = set(out_rows[0]["fits"]), set(out_rows[-1]["fits"])
        shared = first & last
        print(f"first and last bar share {len(shared)} key(s)"
              f"{': ' + ' '.join(sorted(shared)) if shared else ''}")

    # ---- which line is closing the door ----------------------------------
    if args.narrowing:
        print("\nwhich voice narrows the key set, per bar:")
        any_found = False
        for r in out_rows:
            for name, keys in r["narrowed_by"].items():
                any_found = True
                print(f"  bar {r['bar']:>3}  {name[:38]:<38} rules out {' '.join(keys)}")
        if not any_found:
            print("  (no single voice narrows anything — every line agrees)")

    # ---- the queries -----------------------------------------------------
    if args.together:
        if len(args.together) != 2:
            print("--together needs exactly two pitch names, e.g. F B", file=sys.stderr)
            return 2
        a, b = (A.pc(x) for x in args.together)
        hits = A.sounds_together(voices, a, b, meta["ppq"])
        held = [h for h in hits if h[1] >= args.min_beats]
        print(f"\n{args.together[0]} and {args.together[1]} sound together "
              f"{len(hits)} time(s); {len(held)} for >= {args.min_beats} beats")
        for tick, beats, va, vb in held[:20]:
            print(f"  bar {tick // bar_ticks + 1:>3}  {beats:>5.2f} beats   "
                  f"{va[:24]} x {vb[:24]}")
        if hits and not held:
            longest = max(h[1] for h in hits)
            print(f"  longest overlap is {longest:.2f} beats — passing collisions, "
                  f"not a stated interval")

    if args.where:
        for name in args.where:
            hits = A.where_is(voices, A.pc(name), bar_ticks, meta["ppq"])
            print(f"\n{name} appears {len(hits)} time(s):")
            for bar, beat, length, who in hits[:24]:
                print(f"  bar {bar:>3} beat {beat:>5.2f}  {length:>5.2f} beats  {who[:36]}")

    if args.pivots_from:
        bar = next((b for b in rows if b.number == args.pivots_from), None)
        if bar is None or not bar.notes:
            print(f"\nbar {args.pivots_from} has no notes", file=sys.stderr)
        else:
            moves = A.one_note_away(bar.pcs, candidates)
            print(f"\none-note moves out of bar {bar.number} "
                  f"({A.name_chord(bar.pcs, bar.bass)}):")
            if not moves:
                print("  (none — no single semitone relocates this set)")
            for frm, to, key in moves:
                print(f"  {frm:>2} -> {to:<3} puts the whole bar inside {key} major")

    if args.tonic:
        print(f"\nread as modes of {args.tonic}:")
        seen = {k for r in out_rows for k in r["fits"]}
        for k in sorted(seen, key=A.KEY_ORDER.index):
            mode = A.modal_name(k, args.tonic)
            if mode:
                print(f"  {k + ' major':<10} = {mode}")

    return 0


TOOL = Tool(
    name="harm-read", title="Harmonic readout", group="Harmony", run=run, order=10,
    help="bar-by-bar chords, key ambiguity and voice analysis of a MIDI file",
    blurb="Reads a MIDI file whose tracks are independent lines and reports, per "
          "bar, the chord they make, every key that still fits, and which single "
          "voice is narrowing that set.",
    note="This never suggests a chord. It tells you what your lines already made "
         "and what it is still free to become — the number to watch is how many "
         "keys fit. A wide bar is a hinge you can modulate through; a bar where "
         "one voice rules out four keys is the line holding the tonality in place.",
    fields=[
        Field("input", "MIDI file", "file", accept=MIDI, root="downloads",
              required=True, help="tracks are treated as voices"),
        Field("bars", "Bars", "text", flag="--bars",
              help="e.g. '9-16'. Blank = everything. Scope it to the section "
                   "you are actually working on"),
        Field("voices", "Voices to include", "ints", flag="--voices",
              help="track indices, e.g. '0 2 3'. Blank = all with notes"),
        Field("narrowing", "Show which voice narrows the key set", "bool",
              flag="--narrowing", default=True),
        Field("together", "Do these two notes ever sound together?", "texts",
              flag="--together",
              help="two pitch names, e.g. 'F B' — the tritone that pins a key"),
        Field("where", "Locate these pitches in time", "texts", flag="--where",
              help="e.g. 'B' — where the leading tone actually lives"),
        Field("pivots_from", "One-note escapes from bar", "int", flag="--pivots-from",
              help="bar number: which single semitone move relocates it"),
        Field("tonic", "Read collections as modes of", "text", flag="--tonic",
              help="e.g. 'C' — shows 'F major = C Mixolydian'"),
        Field("keys", "Candidate keys", "texts", flag="--keys", advanced=True,
              help="restrict the search, e.g. 'C F Bb Ab'. Blank = all twelve"),
        Field("min_beats", "Minimum overlap (beats)", "float", flag="--min-beats",
              default=0.25, min=0.0, max=4.0, step=0.05, advanced=True,
              help="below this, an overlap is a note-boundary artifact"),
        Field("json", "JSON output", "bool", flag="--json", advanced=True,
              help="for feeding a visualiser"),
    ],
)

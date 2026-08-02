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


def _load(args):
    """Shared front half: read, scope to voices and bars. -> (voices, ticks, meta, bars)

    Both the text readout and the map need exactly this, and they must agree —
    a map that disagreed with the readout would be worse than no map.
    """
    from . import analysis as A

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return None

    voices, bar_ticks, meta = A.read(src)
    if not voices:
        print("no notes in this file", file=sys.stderr)
        return None

    if args.voices:
        keep = set(args.voices)
        voices = [v for v in voices if v.index in keep]
        if not voices:
            print(f"no voices matched {sorted(keep)}", file=sys.stderr)
            return None

    lo = hi = None
    if args.bars:
        text = args.bars.replace(" ", "")
        lo, _, rest = text.partition("-")
        lo, hi = int(lo), int(rest) if rest else int(lo)

    return src, voices, bar_ticks, meta, A.bars(voices, bar_ticks, lo, hi)


def _rows(voices, bars_, candidates, max_readings):
    from . import analysis as A

    name_of = {v.index: v.label for v in voices}
    out_rows = []
    for bar in bars_:
        if not bar.notes:
            continue
        fits = A.key_fits(bar.pcs, candidates)
        rs = A.readings(bar.pcs, bar.bass)
        spread = A.interpretive_spread(rs)
        narrow = A.narrowing_voices(bar, voices, candidates)
        alt = A.readings_without_voice(bar, voices)
        out_rows.append({
            "bar": bar.number,
            "chord": A.name_chord(bar.pcs, bar.bass),   # convenience label only
            "pitches": [A.PCS[p] for p in sorted(bar.pcs)],
            "bass": A.PCS[bar.bass] if bar.bass is not None else None,
            "fits": fits,
            "ambiguity": len(fits),
            # every defensible reading, not a winner. `spread` counts distinct
            # roots among the best-explaining ones: >1 means the lens matters.
            "readings": [{
                "name": r.name, "label": r.label(bar.bass), "root": A.PCS[r.root],
                "quality": r.quality, "explains": r.explains,
                "leftover": [A.PCS[p] for p in sorted(r.leftover)],
                "missing": [A.PCS[p] for p in sorted(r.missing)],
                "root_sounding": r.root_sounding, "bass_root": r.is_bass_root,
            } for r in rs[:max_readings]],
            "spread": [A.PCS[p] for p in spread],
            "forked": len(spread) > 1,
            "narrowed_by": {name_of[i]: keys for i, keys in narrow.items()},
            "without_voice": {
                name_of[i]: [x.label(None) for x in alts[:3]]
                for i, alts in alt.items()
            },
        })
    return out_rows


def run(args: argparse.Namespace) -> int:
    from . import analysis as A

    loaded = _load(args)
    if loaded is None:
        return 2
    src, voices, bar_ticks, meta, bars_ = loaded
    candidates = args.keys or None
    out_rows = _rows(voices, bars_, candidates, args.max_readings)

    if args.json:
        payload = {"file": str(src), "meta": meta, "bar_ticks": bar_ticks,
                   "voices": [{"index": v.index, "name": v.label} for v in voices],
                   "bars": out_rows}
        print(json.dumps(payload, indent=2))
        return 0

    _fmt_voices(voices, meta)
    print(f"{'bar':>5}  {'reading':<14} {'pitches':<22} {'fits':<4} keys")
    for r in out_rows:
        fork = " ⑂" if r["forked"] else "  "
        print(f"{r['bar']:>5}{fork}{r['chord']:<14} {' '.join(r['pitches']):<22} "
              f"{r['ambiguity']:>3}  {' '.join(r['fits'])}")
    if any(r["forked"] for r in out_rows):
        print("  ⑂ = more than one root explains the bar equally well; "
              "run --readings to see them")

    if args.readings:
        print("\nevery defensible reading (the bass is a hypothesis, not a verdict):")
        for r in out_rows:
            head = f"  bar {r['bar']:>3}  {' '.join(r['pitches'])}"
            if r["bass"]:
                head += f"   (lowest: {r['bass']})"
            print(head)
            for rd in r["readings"]:
                tags = []
                if rd["bass_root"]:
                    tags.append("rooted on the bass")
                if not rd["root_sounding"]:
                    tags.append("rootless")
                if rd["leftover"]:
                    tags.append("leaves " + " ".join(rd["leftover"]))
                if rd["missing"]:
                    tags.append("no " + " ".join(rd["missing"]))
                print(f"       {rd['label']:<20} explains {rd['explains']}"
                      f"{'   — ' + ', '.join(tags) if tags else ''}")
            for who, alts in r["without_voice"].items():
                print(f"       if '{who[:30]}' is colour, not a chord tone: "
                      f"{' | '.join(alts)}")

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


def run_map(args: argparse.Namespace) -> int:
    """Write the foundation page: every reading, every key, one timeline."""
    import webbrowser

    from ...core.paths import OUTPUT_DIR

    loaded = _load(args)
    if loaded is None:
        return 2
    src, voices, bar_ticks, meta, bars_ = loaded
    out_rows = _rows(voices, bars_, args.keys or None, args.max_readings)
    if not out_rows:
        print("nothing to map in that range", file=sys.stderr)
        return 2

    span = f"bars {out_rows[0]['bar']}-{out_rows[-1]['bar']}"
    bpm = ""
    if meta["tempo_events"]:
        lo, hi = meta["bpm_min"], meta["bpm_max"]
        bpm = f" · {lo} bpm" if lo == hi else f" · {lo}-{hi} bpm"
    payload = {
        "title": src.stem,
        "subtitle": (f"{span} · {len(voices)} voice(s): "
                     + ", ".join(v.label for v in voices)
                     + f" · {meta['time_signature']}{bpm}"),
        "tonic": args.tonic or "C",
        "bars": out_rows,
    }

    template = (Path(__file__).resolve().parent / "map.html").read_text(encoding="utf-8")
    # json.dumps output is inert inside a <script>, but "</script>" appearing in
    # a track name would close the tag early -- so neutralise the sequence.
    blob = json.dumps(payload).replace("</", "<\\/")
    html = template.replace("__DATA__", blob)

    out = Path(args.out).resolve() if args.out else (
        OUTPUT_DIR / f"harmmap_{src.stem}.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"map -> {out}")
    print(f"  {len(out_rows)} bars · "
          f"{sum(1 for r in out_rows if r['forked'])} forked "
          f"(more than one root explains them equally well)")
    if not args.no_open:
        webbrowser.open(out.as_uri())
    return 0


def run_render(args: argparse.Namespace) -> int:
    """Render a bar range to audio, per voice-set, ready for the A/B tool."""
    from ...core.paths import OUTPUT_DIR
    from . import render as R

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    lo, hi = 1, 9999
    if args.bars:
        text = args.bars.replace(" ", "")
        a, _, b = text.partition("-")
        lo, hi = int(a), int(b) if b else int(a)

    outdir = Path(args.outdir).resolve() if args.outdir else (
        OUTPUT_DIR / f"harmrender_{src.stem}")
    outdir.mkdir(parents=True, exist_ok=True)

    # Each --stack is one voice-set rendered as its own file, so the A/B tool
    # can switch between them in lockstep. "0" is the chord line alone;
    # "0 2 3" is the chords plus melody. Hearing those against each other is
    # the point -- it is how you check whether the arrangement is spending a
    # leading tone the backbone was rationing.
    stacks: list[tuple[str, list[int] | None]] = []
    for spec in (args.stack or []):
        idx = [int(x) for x in spec.replace(",", " ").split()]
        stacks.append((f"voices_{'-'.join(str(i) for i in idx)}", idx))
    if not stacks:
        stacks = [("all", None)]

    made = []
    for name, idx in stacks:
        out = outdir / f"{name}_bars{lo}-{hi}.wav"
        print(f"{name}:")
        path, backend = R.render(src, out, lo, hi, soundfont=args.soundfont,
                                 tracks=idx)
        made.append(path)

    print(f"\n{len(made)} file(s) in {outdir}")
    if len(made) > 1:
        print("compare:\n  .\\amtw.ps1 ab " + " ".join(f'"{p}"' for p in made))
    if "built-in" in backend:
        print("\nFor a real instrument, put a .sf2 in "
              f"{R.SOUNDFONT_DIR} and fluidsynth in {R.FLUIDSYNTH_DIR}.")
    return 0


_SHARED = [
    Field("input", "MIDI file", "file", accept=MIDI, root="downloads",
          required=True, help="tracks are treated as voices"),
    Field("bars", "Bars", "text", flag="--bars",
          help="e.g. '9-16'. Blank = everything. Scope it to the section "
               "you are actually working on"),
    Field("voices", "Voices to include", "ints", flag="--voices",
          help="track indices, e.g. '0 2 3'. Blank = all with notes"),
    Field("tonic", "Tonic", "text", flag="--tonic",
          help="e.g. 'C' — for roman numerals and modal names"),
    Field("keys", "Candidate keys", "texts", flag="--keys", advanced=True,
          help="restrict the search, e.g. 'C F Bb Ab'. Blank = all twelve"),
    Field("max_readings", "Readings per bar", "int", flag="--max-readings",
          default=6, min=1, max=20, step=1, advanced=True),
]

MAP = Tool(
    name="harm-map", title="Harmonic map", group="Harmony", run=run_map, order=20,
    opens_browser=True,
    help="write an interactive page of every reading and every key that fits",
    blurb="The foundation view: one timeline showing every defensible reading of "
          "each bar, which keys still fit, and what the lines are doing — with a "
          "lens switch instead of a single verdict.",
    note="Nothing here is the answer. Switching lens reorders the readings, it "
         "never deletes one, because a bass note is a hypothesis about function "
         "— root, pedal, colour, or an anticipation of the next chord — and all "
         "four readings stay on the page. Click a reading to pin it and the "
         "roman-numeral row rewrites from your picks.",
    fields=_SHARED + [
        Field("out", "Output HTML", "text", flag="--out", advanced=True),
        Field("no_open", "Don't open a browser", "bool", flag="--no-open",
              advanced=True),
    ],
)

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
    fields=_SHARED + [
        Field("narrowing", "Show which voice narrows the key set", "bool",
              flag="--narrowing", default=True),
        Field("readings", "List every defensible reading per bar", "bool",
              flag="--readings", default=True,
              help="the bass is one hypothesis about function, not the answer"),
        Field("together", "Do these two notes ever sound together?", "texts",
              flag="--together",
              help="two pitch names, e.g. 'F B' — the tritone that pins a key"),
        Field("where", "Locate these pitches in time", "texts", flag="--where",
              help="e.g. 'B' — where the leading tone actually lives"),
        Field("pivots_from", "One-note escapes from bar", "int", flag="--pivots-from",
              help="bar number: which single semitone move relocates it"),
        Field("min_beats", "Minimum overlap (beats)", "float", flag="--min-beats",
              default=0.25, min=0.0, max=4.0, step=0.05, advanced=True,
              help="below this, an overlap is a note-boundary artifact"),
        Field("json", "JSON output", "bool", flag="--json", advanced=True,
              help="the same data the map is built from"),
    ],
)

RENDER = Tool(
    name="harm-render", title="Render to audio", group="Harmony",
    run=run_render, order=30,
    help="render a bar range to audio, one file per voice-set, for A/B",
    blurb="Renders a span of bars to wav so you can hear what the analysis is "
          "talking about. Give it several voice-sets and it writes one file "
          "each, ready to switch between in the A/B tool.",
    note="Uses FluidSynth and a soundfont when one is installed in the runtime "
         "root, and a built-in synth otherwise so the tool still makes a sound "
         "on a fresh machine. The built-in one is for checking a reading, not "
         "for judging an arrangement — install a soundfont before you trust "
         "your ears on a mix decision.",
    fields=[
        Field("input", "MIDI file", "file", accept=MIDI, root="downloads",
              required=True),
        Field("bars", "Bars", "text", flag="--bars",
              help="e.g. '9-16'. Blank = the whole file"),
        Field("stack", "Voice sets to render", "texts", flag="--stack",
              help="one file per set, e.g. '0' '0 2 3' — then A/B them"),
        Field("soundfont", "Soundfont", "file", flag="--soundfont",
              accept=["sf2", "sf3"], advanced=True,
              help="blank = the first one found in the runtime root"),
        Field("outdir", "Output folder", "dir", flag="--outdir", root="output",
              advanced=True),
    ],
)

TOOLS = [TOOL, MAP, RENDER]

"""The tool catalog.

One declaration per command, describing its arguments well enough that the
workbench can build a real form for it — file pickers, sliders, checkboxes —
and turn the result back into an argv for the existing CLI. Adding a tool to
the UI means adding an entry here; there is no per-tool UI code.

The CLI stays the source of truth for *behaviour*; this is only about how the
arguments are presented and assembled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# field types the UI knows how to render
#   file / files / dir   path pickers (files = multi-select)
#   text                 free text
#   int / float          number box, or a slider when min+max are given
#   floats               space-separated list of numbers
#   bool                 checkbox (emits the flag when true)
#   choice               dropdown
#   multichoice          checkbox group (emits several values after one flag)


@dataclass
class Field:
    name: str                      # argparse dest
    label: str
    type: str = "text"
    flag: str | None = None        # None = positional
    default: Any = None
    help: str = ""
    choices: list[str] | None = None
    accept: list[str] | None = None  # extensions for path pickers
    root: str | None = None        # where the file browser should open
    min: float | None = None
    max: float | None = None
    step: float | None = None
    advanced: bool = False         # tucked behind "More options"
    required: bool = False


@dataclass
class Tool:
    name: str                      # amtw subcommand
    title: str
    group: str
    blurb: str
    fields: list[Field] = field(default_factory=list)
    note: str = ""                 # shown under the form, for hard-won context
    background: bool = False       # long-lived server; don't wait for it
    opens_browser: bool = False


AUDIO = ["wav", "mp3", "flac", "m4a", "aiff", "ogg"]


def _catalog() -> list[Tool]:
    return [
        Tool(
            name="run", title="Run pipeline", group="Pipeline",
            blurb="Full restore + re-synthesis on a vocal stem. Writes a job folder "
                  "with every stage's output and a comparison report.",
            note="Restoration-only (cleanup + superres, no resynth) can't touch grit "
                 "because it never re-synthesizes — worth A/B-ing on every song.",
            fields=[
                Field("input", "Vocal stem", "file", accept=AUDIO, root="input",
                      required=True, help="wav / mp3 / flac / m4a"),
                Field("stages", "Stages", "multichoice", flag="--stages",
                      choices=["cleanup", "superres", "resynth"],
                      default=["cleanup", "superres", "resynth"]),
                Field("name", "Job name", "text", flag="--name",
                      help="blank = <stem>_<timestamp>"),
                Field("deecho", "De-echo pass", "bool", flag="--deecho",
                      help="kills short slap reflections that resynth otherwise "
                           "re-renders as a doubled vocal"),
                Field("dereverb", "De-reverb model", "choice", flag="--dereverb",
                      choices=["classic", "roformer"], default="classic",
                      help="measured difference between these is ~4% — classic is fine"),
                Field("engine", "Resynth engine", "choice", flag="--engine",
                      choices=["seedvc", "yingmusic"], default="seedvc"),
                Field("reference", "Timbre reference", "file", flag="--reference",
                      accept=AUDIO, root="output", advanced=True,
                      help="blank = auto-picked from the stem itself"),
                Field("cfg_rate", "CFG rate", "float", flag="--cfg-rate", default=0.7,
                      min=0.0, max=1.0, step=0.05, advanced=True,
                      help="lower keeps more source grit; higher pushes toward the reference"),
                Field("diffusion_steps", "Diffusion steps", "int", flag="--diffusion-steps",
                      default=50, min=10, max=100, step=5, advanced=True),
                Field("semitone_shift", "Semitone shift", "int", flag="--semitone-shift",
                      default=0, min=-12, max=12, step=1, advanced=True),
                Field("ref_seconds", "Reference seconds", "float", flag="--ref-seconds",
                      default=25.0, min=5, max=60, step=1, advanced=True),
                Field("denoise", "Extra de-noise pass", "bool", flag="--denoise",
                      advanced=True),
                Field("sr", "Output sample rate", "int", flag="--sr", default=0,
                      advanced=True, help="0 keeps the pipeline's native 44100"),
                Field("match_input_sr", "Match input rate", "bool", flag="--match-input-sr",
                      advanced=True),
            ],
        ),
        Tool(
            name="harmonic", title="Fry scrape repair", group="Fry repair",
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
                      min=0.0, max=1.0, step=0.05, advanced=True),
                Field("f_lo", "Crossover Hz", "float", flag="--f-lo", default=1500.0,
                      advanced=True),
                Field("outdir", "Output folder", "dir", flag="--outdir", root="output",
                      advanced=True),
            ],
        ),
        Tool(
            name="detect", title="Detector check", group="Fry repair",
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
                      default=0.4, min=0.1, max=2.0, step=0.1),
                Field("threshold", "Threshold line", "float", flag="--threshold",
                      default=0.6, min=0.0, max=1.0, step=0.05, advanced=True),
                Field("out", "Output PNG", "text", flag="--out", advanced=True),
            ],
        ),
        Tool(
            name="defizz", title="HF de-fizz", group="Fry repair",
            blurb="Narrowband spectral smear above a crossover, rendered at several "
                  "strengths for A/B.",
            note="Not yet shown to work — every earlier test ran through the broken "
                 "periodicity gate, so it deserves a retest rather than trust.",
            fields=[
                Field("input", "Vocal stem", "file", accept=AUDIO, root="input",
                      required=True),
                Field("strengths", "Strengths", "floats", flag="--strengths",
                      default=[0.35, 0.6, 0.85]),
                Field("f_lo", "Crossover Hz", "float", flag="--f-lo", default=7000.0),
                Field("smear", "Smear width Hz", "float", flag="--smear", default=400.0,
                      min=100, max=2000, step=50,
                      help="400 subtle, 1200 aggressive"),
                Field("outdir", "Output folder", "dir", flag="--outdir", root="output",
                      advanced=True),
            ],
        ),
        Tool(
            name="remod", title="HF re-modulation", group="Fry repair",
            blurb="Expands and voice-tracks the high band's envelope, rendering four "
                  "variants that isolate each mechanism.",
            note="Also unproven, and also only ever run through the broken gate.",
            fields=[
                Field("input", "Vocal stem", "file", accept=AUDIO, root="input",
                      required=True),
                Field("f_lo", "Band bottom Hz", "float", flag="--f-lo", default=4500.0,
                      help="the wash sits ~5-12 kHz"),
                Field("expand", "Envelope expansion", "float", flag="--expand", default=1.8,
                      min=1.0, max=4.0, step=0.1),
                Field("track", "Voice tracking", "float", flag="--track", default=0.5,
                      min=0.0, max=1.0, step=0.05),
                Field("per_lo", "Periodicity ramp low", "float", flag="--per-lo",
                      default=0.60, min=0.0, max=1.0, step=0.01, advanced=True),
                Field("per_hi", "Periodicity ramp high", "float", flag="--per-hi",
                      default=0.92, min=0.0, max=1.0, step=0.01, advanced=True),
                Field("outdir", "Output folder", "dir", flag="--outdir", root="output",
                      advanced=True),
            ],
        ),
        Tool(
            name="ab", title="A/B listening", group="Listening",
            blurb="Play aligned files in lockstep, switch instantly, mark regions. "
                  "Opens in its own tab; marks save to output/ab_notes.",
            note="Mark a region by dragging the waveform and pressing S. Those marks are "
                 "what the fry repair reads.",
            background=True, opens_browser=True,
            fields=[
                Field("files", "Files to compare", "files", accept=AUDIO, root="output",
                      required=True, help="two or more aligned files"),
                Field("notes", "Notes JSON", "text", flag="--notes", advanced=True,
                      help="blank = output/ab_notes/<timestamp>.json"),
                Field("port", "Port", "int", flag="--port", default=8731, advanced=True),
            ],
        ),
        Tool(
            name="midi-merge", title="MIDI track merge", group="MIDI",
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
        ),
        Tool(
            name="midi-inspect", title="MIDI inspect", group="MIDI",
            blurb="Lists a MIDI file's tracks — note counts, pitch range, span — so you "
                  "know which ones to merge.",
            fields=[
                Field("inputs", "MIDI file(s)", "files", accept=["mid", "midi"],
                      root="downloads", required=True),
            ],
        ),
        Tool(
            name="report", title="Rebuild report", group="Pipeline",
            blurb="Regenerates report.html for an existing job folder.",
            fields=[
                Field("jobdir", "Job folder", "dir", root="output", required=True),
            ],
        ),
        Tool(
            name="doctor", title="Doctor", group="Pipeline",
            blurb="Checks venvs, CUDA, third-party clones and model checkpoints.",
            fields=[],
        ),
    ]


CATALOG: list[Tool] = _catalog()
BY_NAME: dict[str, Tool] = {t.name: t for t in CATALOG}


def build_argv(tool_name: str, values: dict) -> list[str]:
    """Turn form values into an argv for the amtw CLI."""
    tool = BY_NAME[tool_name]
    positional: list[str] = []
    optional: list[str] = []

    for f in tool.fields:
        raw = values.get(f.name)

        if f.type == "bool":
            if bool(raw):
                optional.append(f.flag)
            continue

        # normalise to a list of strings, dropping blanks
        if isinstance(raw, list):
            items = [str(v).strip() for v in raw if str(v).strip() != ""]
        elif raw is None:
            items = []
        else:
            text = str(raw).strip()
            # number lists arrive as one string from a text input; paths never
            # get split, because they contain spaces
            items = text.split() if f.type in ("floats", "ints") else ([text] if text else [])

        if not items:
            if f.required:
                raise ValueError(f"{f.label} is required")
            continue

        if f.flag is None:
            positional.extend(items)
        else:
            # skip anything left at its default -- keeps the command line honest
            if f.default is not None and not isinstance(f.default, list):
                if len(items) == 1 and items[0] == str(f.default):
                    continue
            optional.extend([f.flag, *items])

    return [tool_name, *positional, *optional]


def catalog_json() -> list[dict]:
    return [
        {
            "name": t.name, "title": t.title, "group": t.group, "blurb": t.blurb,
            "note": t.note, "background": t.background, "opens_browser": t.opens_browser,
            "fields": [
                {k: v for k, v in vars(f).items() if v is not None or k == "default"}
                for f in t.fields
            ],
        }
        for t in CATALOG
    ]

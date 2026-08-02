# Adding a tool

A tool is **one folder** under `amtw/tools/`. Drop it in and it appears on the
bench and in `--help` — there is no catalog to update and no `cli.py` to edit.

That used to be three separate edits (module, argparse block, catalog entry),
and the catalog entry was the one that got skipped. It also drifted:
`detect --marks` existed in the CLI and never appeared on the bench, because
nothing forced the two to agree. Now there is one declaration and both are
generated from it.

Worked example: `midi-merge`, in `amtw/tools/midi/`.

## The shape

```
amtw/tools/yourthing/
    __init__.py      TOOL = Tool(...) — the declaration and the run() entry point
    yourthing.py     the actual work
    README.md        optional; what it does and why, for a reader who lands here
```

`amtw/registry.py` walks `amtw/tools/*/` and collects `TOOL` from each package.
A folder exporting `TOOLS` (a list) contributes several — that is how
`midi-merge` and `midi-inspect` share one `midi.py`.

Import errors are deliberately **not** swallowed. A tool that fails to import
is a broken tool, and finding out at startup beats finding out when the bench
renders a form whose command doesn't exist.

## 1. The work — `yourthing.py`

Pure functions where possible, taking and returning data rather than paths, so
the logic can be tested without a file on disk. Take an optional `log=print` if
the tool has progress worth streaming; the workbench captures stdout.

```python
def merge(inputs, out=None, dup="1/16", log=print) -> dict:
    """Do the thing. Return stats the caller can report."""
```

Put the *why* in the module docstring. `amtw/tools/midi/midi.py` opens by
explaining what Suno does wrong, because that is what a reader won't guess.

Shared STFT/gating primitives live in `amtw/core/dsp.py` — import them, don't
re-derive them. Two tools disagreeing about the frame grid shows up as "the
detector says fry but the repair does nothing".

## 2. The declaration — `__init__.py`

```python
from ...spec import AUDIO, Field, Tool


def run(args) -> int:
    from . import yourthing          # lazy: keeps --help fast
    ...
    return 0


TOOL = Tool(
    name="yourthing",            # the subcommand
    title="Your Thing",
    group="MIDI",                # groups the sidebar; reuse an existing one
    run=run,
    order=10,                    # rank within the group; ties sort by name
    help="one line, shown in --help",
    blurb="One or two sentences: what it does and what it writes.",
    note="Anything hard-won the user should see at the moment they use it.",
    fields=[
        Field("input", "Source file", "file", accept=AUDIO, root="input",
              required=True),
        Field("dup", "Duplicate window", "choice", flag="--dup",
              choices=["1/8", "1/16", "1/32"], default="1/16",
              help="shown as small grey text under the widget"),
        Field("verbose", "Verbose", "bool", flag="--verbose", advanced=True),
    ],
)
```

Groups render in `registry.GROUP_ORDER`; an unlisted group still appears, just
after the established ones.

**Field types** and what they render as:

| type | widget | argparse | emits |
|---|---|---|---|
| `file` / `dir` | path box + Browse | one value | one path |
| `files` | path box + multi-select Browse | `nargs="+"` | several paths |
| `text` | text box | one value | one value |
| `int` / `float` | number box, or a **slider** when `min` and `max` are set | `type=int/float` | one value |
| `ints` / `floats` | text box, split on spaces | `type=…, nargs="+"` | several values |
| `bool` | checkbox | `store_true` | the flag alone, when true |
| `choice` | dropdown | `choices=…` | one value |
| `multichoice` | chip group | `choices=…, nargs="+"` | several values |

**Field rules that matter:**

- `flag=None` means positional. Positionals are emitted in declaration order,
  before any flags. A positional that isn't `required` gets `nargs="?"`.
- `default` is compared against the entered value, and matching values are
  **omitted** from the command line, so the console shows a short honest
  command rather than every flag restated.
- On a `bool`, `default` is a **UI hint only** — whether the box starts ticked.
  It is never an argparse default, because a flag defaulting to true could not
  be switched off from the command line.
- `advanced=True` tucks the field behind "More options". Be aggressive with
  this: `run` has 14 fields and shows 6.
- `root=` picks where the file browser opens: `input`, `output`, `ab_notes`,
  `downloads`, `project`, `music`, `desktop`.
- `accept=` filters by extension. `AUDIO` is predefined.
- `background=True` on the Tool for a long-lived server (like `ab`) — the UI
  keeps a Stop button instead of waiting for exit.

**The `note` field is not decoration.** It is where a finding gets in front of
the user at the moment of use. Compare:

> *fry repair* — "Marks decide where, the detector decides how much. Everything
> outside a mark comes back bit-identical."

> *de-fizz* — "Not yet shown to work — every earlier test ran through the broken
> periodicity gate, so it deserves a retest rather than trust."

The second one stops someone trusting a tool that hasn't earned it.

## 3. Verify

```powershell
.\amtw.ps1 yourthing <a real file>     # CLI works
.\amtw.ps1 workbench                   # then run it from the UI
```

Check the console shows the command you expected — that's the argv builder
agreeing with you. Then check the result chips at the bottom actually open.

## 4. Record it

- `CHANGELOG.md` under `[Unreleased]`.
- Anything you measured → `docs/findings.md`, negative results included.
- A new *family* of tools (not just one tool) → a section in `README.md`.

## Gotchas the argv builder will hit you with

- A field whose value equals its default is dropped. If a flag must always be
  passed, don't give it a default.
- List defaults (`[0.5, 0.8, 1.0]`) are always emitted — the comparison only
  skips scalars.
- `files` values arrive as a list and are never split on whitespace; paths
  contain spaces. `floats`/`ints` arrive as one string and *are* split.
- Required fields raise `ValueError` in `build_argv`, which the UI shows next to
  the Run button. Mark genuinely-required fields `required=True` so the user
  gets that instead of an argparse stack trace.
- Anything deriving a path from `__file__` belongs in `amtw/core/paths.py`, not
  in your tool. `PROJECT_ROOT` is counted from the package root, and moving a
  file changed that count once — every subprocess died with "No module named
  amtw", because the bench sets its cwd from it.

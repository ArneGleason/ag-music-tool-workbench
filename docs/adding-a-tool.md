# Adding a tool

A tool is three things: a module that does the work, a CLI subcommand, and a
catalog entry that puts it on the bench. The catalog entry is the part agents
skip and shouldn't — a tool that isn't on the bench doesn't exist to the person
using this.

Worked example: `midi-merge`, added in v0.2.0.

## 1. The module — `amtw/yourthing.py`

Pure functions where possible, taking and returning data rather than paths, so
the logic can be tested without a file on disk. Take an optional `log=print` if
the tool has progress worth streaming; the workbench captures stdout.

```python
def merge(inputs, out=None, dup="1/16", log=print) -> dict:
    """Do the thing. Return stats the caller can report."""
```

Put the *why* in the module docstring. `amtw/midi.py` opens by explaining what
Suno does wrong, because that is the thing a reader won't guess.

## 2. The CLI subcommand — `amtw/cli.py`

A `cmd_yourthing(args)` function returning an exit code, plus a parser in
`main()`. Import your module *inside* the function — `cli.py` is imported on
every invocation and lazy imports keep `--help` fast.

```python
def cmd_yourthing(args):
    from . import yourthing
    ...
    return 0

# in main():
py = sub.add_parser("yourthing", help="one line, shown in --help")
py.add_argument("input")
py.add_argument("--dup", default="1/16", help="...")
py.set_defaults(fn=cmd_yourthing)
```

The CLI stays the source of truth for behaviour. The UI never bypasses it — the
workbench literally runs `python -m amtw yourthing ...` as a subprocess.

## 3. The catalog entry — `amtw/tools.py`

This is what builds the form. No UI code is involved.

```python
Tool(
    name="yourthing",            # must match the subcommand exactly
    title="Your Thing",
    group="MIDI",                # groups the sidebar; reuse an existing one
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

**Field types** and what they render as:

| type | widget | emits |
|---|---|---|
| `file` / `dir` | path box + Browse | one path |
| `files` | path box + multi-select Browse | several paths |
| `text` | text box | one value |
| `int` / `float` | number box, or a **slider** when `min` and `max` are set | one value |
| `floats` / `ints` | text box, split on spaces | several values |
| `bool` | checkbox | the flag alone, when true |
| `choice` | dropdown | one value |
| `multichoice` | chip group | several values |

**Field rules that matter:**

- `flag=None` means positional. Positionals are emitted in declaration order,
  before any flags.
- `default` is compared against the entered value, and matching values are
  **omitted** from the command line, so the console shows a short honest
  command rather than every flag restated.
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

## 4. Verify

```powershell
.\amtw.ps1 yourthing <a real file>     # CLI works
.\amtw.ps1 workbench                   # then run it from the UI
```

Check the console shows the command you expected — that's the argv builder
agreeing with you. Then check the result chips at the bottom actually open.

## 5. Record it

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

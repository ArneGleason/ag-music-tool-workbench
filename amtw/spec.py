"""The vocabulary a tool is declared in.

One declaration per command, describing its arguments well enough that two
different consumers can be generated from it:

  * the workbench builds a real form — file pickers, sliders, checkboxes —
    and turns the result back into an argv (`build_argv`);
  * the CLI builds an argparse subparser (`add_to_parser`).

That is the point of this module. Previously a tool was declared twice — once
as an argparse block and once as a catalog entry — and the two drifted:
`detect --marks` existed in the CLI but never appeared on the bench, because
nothing forced them to agree. Now there is one declaration and both are
derived from it, so a tool cannot exist in one and not the other.

The tool's `run` callable stays the source of truth for *behaviour*; this is
only about how its arguments are presented and assembled.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Callable

# field types the UI knows how to render
#   file / files / dir   path pickers (files = multi-select)
#   text / texts         free text; texts is a space-separated list
#   int / float          number box, or a slider when min+max are given
#   ints / floats        space-separated list of numbers
#   bool                 checkbox (emits the flag when true)
#   choice               dropdown
#   multichoice          checkbox group (emits several values after one flag)

MULTI = ("files", "texts", "ints", "floats", "multichoice")

# types that arrive from a text box as one string and are split on whitespace.
# `files` is deliberately absent: paths contain spaces.
SPLIT_ON_SPACE = ("texts", "ints", "floats")


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
    run: Callable[[argparse.Namespace], int] | None = None
    fields: list[Field] = field(default_factory=list)
    note: str = ""                 # shown under the form, for hard-won context
    help: str = ""                 # one-liner for `--help`; defaults to the blurb
    order: int = 50                # rank within the group; ties sort by name
    background: bool = False       # long-lived server; don't wait for it
    opens_browser: bool = False

    def __post_init__(self) -> None:
        if not self.help:
            self.help = self.blurb.split(". ")[0].rstrip(".").lower()


AUDIO = ["wav", "mp3", "flac", "m4a", "aiff", "ogg"]


# --------------------------------------------------------------------------- #
# CLI: Field -> argparse
# --------------------------------------------------------------------------- #


def _argparse_kwargs(f: Field) -> dict:
    kw: dict[str, Any] = {}
    if f.type == "bool":
        # NOTE: a bool's `default` is a UI hint (whether the box starts ticked),
        # never an argparse default. A flag that defaulted to True could not be
        # switched off from the command line.
        return {"action": "store_true"}

    if f.type in ("int", "ints"):
        kw["type"] = int
    elif f.type in ("float", "floats"):
        kw["type"] = float

    if f.type in MULTI:
        kw["nargs"] = "+"
    if f.choices:
        kw["choices"] = f.choices
    if f.default is not None:
        kw["default"] = f.default
    if f.help:
        kw["help"] = f.help
    return kw


def add_to_parser(tool: Tool, sub) -> None:
    """Build `tool`'s argparse subparser from its field declarations."""
    p = sub.add_parser(tool.name, help=tool.help)
    for f in tool.fields:
        kw = _argparse_kwargs(f)
        if f.flag is None:
            # argparse positionals are required by default; an optional one
            # needs an explicit nargs so it can be omitted.
            if not f.required and "nargs" not in kw:
                kw["nargs"] = "?"
            p.add_argument(f.name, **kw)
        else:
            p.add_argument(f.flag, dest=f.name, **kw)
    p.set_defaults(fn=tool.run, _tool=tool.name)


# --------------------------------------------------------------------------- #
# Workbench: form values -> argv
# --------------------------------------------------------------------------- #


def build_argv(tool: Tool, values: dict) -> list[str]:
    """Turn form values into an argv for the amtw CLI."""
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
            items = text.split() if f.type in SPLIT_ON_SPACE else ([text] if text else [])

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

    return [tool.name, *positional, *optional]


def tool_json(tool: Tool) -> dict:
    return {
        "name": tool.name, "title": tool.title, "group": tool.group,
        "blurb": tool.blurb, "note": tool.note, "background": tool.background,
        "opens_browser": tool.opens_browser,
        "fields": [
            {k: v for k, v in vars(f).items() if v is not None or k == "default"}
            for f in tool.fields
        ],
    }

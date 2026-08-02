"""The bench and the CLI must stay in agreement.

Every tool declares its arguments once, and two things are generated from that
declaration: the workbench form (which produces an argv) and the argparse
subparser (which consumes one). This test drives the full loop for every
registered tool — build an argv the way the browser would, then parse it the
way `python -m amtw` would.

It exists because the two used to be written by hand and drifted:
`detect --marks` worked on the command line but was never offered on the bench.
A field type the argv builder handles and argparse doesn't (or vice versa) is
invisible until someone runs that tool, which for the unproven fry tools could
be months.

Run it with the main venv's python. pytest is not a dependency of this repo,
so the file doubles as its own runner:

    & "$env:LOCALAPPDATA\\VocalStemRegen\\venvs\\main\\Scripts\\python.exe" tests\\test_roundtrip.py

The `test_*` functions are plain asserts, so `pytest tests` also works if you
happen to have it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amtw import registry                      # noqa: E402
from amtw.spec import add_to_parser, build_argv  # noqa: E402

# one plausible value per field type, as the browser would submit it
SAMPLE = {
    "file": "x.wav", "files": "a.wav", "dir": "outdir", "text": "t",
    "texts": "F B", "int": "3", "float": "0.5",
    "ints": "1 2", "floats": "0.5 0.8",
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="amtw")
    sub = p.add_subparsers(dest="cmd", required=True)
    for tool in registry.catalog():
        add_to_parser(tool, sub)
    return p


def _form_values(tool) -> dict:
    """What the workbench would POST for this tool, using defaults."""
    values = {}
    for f in tool.fields:
        if f.type == "choice":
            values[f.name] = f.choices[0] if f.choices else "x"
        elif f.type == "multichoice":
            values[f.name] = f.choices[:1] if f.choices else ["x"]
        elif f.required or f.default is None:
            values[f.name] = SAMPLE.get(f.type, "v")
        else:
            values[f.name] = f.default
    return values


def test_every_tool_round_trips() -> None:
    parser = _parser()
    for tool in registry.catalog():
        argv = build_argv(tool, _form_values(tool))
        assert argv[0] == tool.name, f"{tool.name}: argv starts with {argv[0]!r}"

        ns = parser.parse_args(argv)          # raises SystemExit if they disagree

        missing = [f.name for f in tool.fields if not hasattr(ns, f.name)]
        assert not missing, f"{tool.name}: parsed namespace missing {missing}"
        assert ns.fn is tool.run, f"{tool.name}: wired to the wrong run()"


def test_required_fields_are_reported_not_crashed() -> None:
    """A blank required field must raise ValueError, which the UI shows next to
    the Run button — not an argparse stack trace in the console."""
    for tool in registry.catalog():
        required = [f for f in tool.fields if f.required]
        if not required:
            continue
        values = _form_values(tool)
        values[required[0].name] = ""
        try:
            build_argv(tool, values)
        except ValueError:
            continue
        raise AssertionError(
            f"{tool.name}: blank {required[0].name!r} did not raise ValueError")


def test_tool_names_are_unique() -> None:
    names = [t.name for t in registry.catalog()]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate tool names: {dupes}"


def test_launchers_are_ascii() -> None:
    """Shell launchers must be pure ASCII.

    Windows PowerShell 5.1 reads a .ps1 with no BOM as ANSI. A single em-dash
    in an error string became mojibake, swallowed the closing quote, and the
    script died with "The string is missing the terminator" before running a
    line. PowerShell 7 decodes it as UTF-8 and never sees the problem — so this
    only breaks for someone on the older shell, which is most people, and it
    survived unnoticed here for exactly that reason.
    """
    root = Path(__file__).resolve().parents[1]
    for p in sorted(root.rglob("*.ps1")) + sorted(root.rglob("*.cmd")):
        if ".git" in p.parts or "output" in p.parts:
            continue
        text = p.read_text(encoding="utf-8")
        bad = {c for c in text if ord(c) > 127}
        assert not bad, f"{p.name} has non-ASCII {bad!r} — breaks PowerShell 5.1"


if __name__ == "__main__":
    # standalone runner so this works without pytest installed
    failures = 0
    for fn in (test_every_tool_round_trips,
               test_required_fields_are_reported_not_crashed,
               test_tool_names_are_unique,
               test_launchers_are_ascii):
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except (AssertionError, SystemExit) as e:
            print(f"  FAIL {fn.__name__}: {e}")
            failures += 1
    print(f"\n{len(registry.catalog())} tools · {failures} failures")
    sys.exit(1 if failures else 0)

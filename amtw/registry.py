"""Tool discovery.

Every package under `amtw/tools/` that exports `TOOL` (or `TOOLS`, for a
folder holding a small family) is a tool. Nothing lists them; this walks the
directory and imports what it finds.

That is the whole point: adding a tool is *dropping in a folder*. There is no
central catalog to forget to update, which is what used to happen — the
catalog entry was the step most likely to be skipped, and a tool that isn't on
the bench doesn't exist to the person using this.

A tool whose dependencies are missing is recorded as UNAVAILABLE rather than
crashing the whole registry. That is a reversal: this file used to let
ImportError propagate, on the reasoning that a tool which cannot import is
broken and should say so loudly. It does say so — but it took the other
fourteen tools down with it, so a machine without the audio stack could not run
`harm-reduce`, which needs nothing but `mido`, or even `--help`.

Unavailable tools are still reported, by `unavailable()` and by `doctor`. They
are not hidden; they are just not fatal. Anything that is not an ImportError
still propagates, because that is a real bug rather than a missing package.
"""
from __future__ import annotations

import importlib
import pkgutil

from .spec import Tool

# Sidebar order. Groups not listed here sort after these, alphabetically, so a
# new group appears without needing to be registered — just not jumping the
# queue ahead of the established ones.
GROUP_ORDER = ["Pipeline", "Fry repair", "Drums", "Listening", "MIDI", "Harmony"]


_MISSING: list[tuple[str, str]] = []


def _discover() -> list[Tool]:
    from . import tools as tools_pkg

    found: list[Tool] = []
    _MISSING.clear()
    for mod in sorted(pkgutil.iter_modules(tools_pkg.__path__), key=lambda m: m.name):
        if not mod.ispkg:
            continue
        try:
            m = importlib.import_module(f"{tools_pkg.__name__}.{mod.name}")
        except ImportError as e:
            # a package this tool needs is not installed; the others still work
            _MISSING.append((mod.name, str(e)))
            continue
        if hasattr(m, "TOOLS"):
            found.extend(m.TOOLS)
        elif hasattr(m, "TOOL"):
            found.append(m.TOOL)

    def key(t: Tool) -> tuple:
        try:
            return (0, GROUP_ORDER.index(t.group), t.order, t.name)
        except ValueError:
            return (1, 0, t.order, t.name)

    return sorted(found, key=key)


_CACHE: list[Tool] | None = None


def catalog() -> list[Tool]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _discover()
    return _CACHE


def unavailable() -> list[tuple[str, str]]:
    """[(package name, why)] for tools that could not be imported."""
    catalog()
    return list(_MISSING)


def by_name(name: str) -> Tool:
    for t in catalog():
        if t.name == name:
            return t
    raise KeyError(name)


def catalog_json() -> list[dict]:
    from .spec import tool_json

    return [tool_json(t) for t in catalog()]

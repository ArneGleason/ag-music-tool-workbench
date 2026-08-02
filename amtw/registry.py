"""Tool discovery.

Every package under `amtw/tools/` that exports `TOOL` (or `TOOLS`, for a
folder holding a small family) is a tool. Nothing lists them; this walks the
directory and imports what it finds.

That is the whole point: adding a tool is *dropping in a folder*. There is no
central catalog to forget to update, which is what used to happen — the
catalog entry was the step most likely to be skipped, and a tool that isn't on
the bench doesn't exist to the person using this.

Import errors are deliberately not swallowed. A tool that fails to import is a
broken tool, and finding out at startup beats finding out when the bench
renders a form whose command does not exist.
"""
from __future__ import annotations

import importlib
import pkgutil

from .spec import Tool

# Sidebar order. Groups not listed here sort after these, alphabetically, so a
# new group appears without needing to be registered — just not jumping the
# queue ahead of the established ones.
GROUP_ORDER = ["Pipeline", "Fry repair", "Listening", "MIDI", "Harmony"]


def _discover() -> list[Tool]:
    from . import tools as tools_pkg

    found: list[Tool] = []
    for mod in sorted(pkgutil.iter_modules(tools_pkg.__path__), key=lambda m: m.name):
        if not mod.ispkg:
            continue
        m = importlib.import_module(f"{tools_pkg.__name__}.{mod.name}")
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


def by_name(name: str) -> Tool:
    for t in catalog():
        if t.name == name:
            return t
    raise KeyError(name)


def catalog_json() -> list[dict]:
    from .spec import tool_json

    return [tool_json(t) for t in catalog()]

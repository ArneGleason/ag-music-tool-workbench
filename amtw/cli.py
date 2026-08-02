"""Command line interface.

    python -m amtw run input\\my_vocal.wav [options]
    python -m amtw report output\\my_vocal_20260703-101500
    python -m amtw doctor

Subcommands are not written here. Every package under `amtw/tools/` declares
its own arguments once, and both this CLI and the workbench form are generated
from that declaration — see amtw/spec.py and amtw/registry.py.

`workbench` is the exception: it is the bench itself, not a tool on it.
"""
from __future__ import annotations

import argparse

from . import registry
from .spec import add_to_parser


def cmd_workbench(args: argparse.Namespace) -> int:
    from .bench.server import serve

    return serve(port=args.port, open_browser=not args.no_open)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="amtw", description="AG Music Tool Workbench — music production tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    for tool in registry.catalog():
        add_to_parser(tool, sub)

    pw = sub.add_parser("workbench", help="open the tool workbench in the browser")
    pw.add_argument("--port", type=int, default=8730)
    pw.add_argument("--no-open", action="store_true", help="don't open a browser tab")
    pw.set_defaults(fn=cmd_workbench)

    args = p.parse_args(argv)
    if getattr(args, "stages", None):
        # tolerate both "--stages a b" and "--stages a,b" (PowerShell splits
        # comma lists into separate argv tokens anyway)
        args.stages = [t.strip() for s in args.stages for t in s.split(",") if t.strip()]
    return args.fn(args)

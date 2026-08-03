"""Bitwig bridge: the workbench, reachable from inside the DAW.

The extension in Bitwig is a transport and nothing more — it reads the selected
clip, writes notes into a NEW clip, and shows popups. Every question about what
a chord is gets answered here, by the same Python that `harm-read` and
`harm-reduce` already use, so there is one implementation rather than a Java
twin that drifts.

That shape has one honest cost: `bitwig-bridge` has to be running. The
extension is built to degrade quietly when it is not — one line in the
controller console, no popups, no nagging on every Bitwig start.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from ...spec import Field, Tool


def run_install(args: argparse.Namespace) -> int:
    from ...core.paths import OUTPUT_DIR
    from . import build as B

    bw = B.find_bitwig()
    if not bw:
        print("Bitwig Studio not found — set BITWIG_HOME", file=sys.stderr)
        return 2
    print(f"bitwig: {bw}")

    staged = Path(args.out).resolve() if args.out else (
        OUTPUT_DIR / "bitwig" / "AmtwHarmony.bwextension")
    try:
        B.build(staged)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.no_install:
        print(f"built only (not installed): {staged}")
        return 0

    dest_dir = Path(args.dest).resolve() if args.dest else B.extensions_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / staged.name
    shutil.copy2(staged, dest)
    print(f"installed -> {dest}")
    print()
    print("In Bitwig: Settings > Controllers > Add Controller >")
    print("  AG Music Tool Workbench > Harmony Bridge")
    print("Then run `amtw bitwig-bridge`; the buttons appear in the project")
    print("panel under 'AMTW Harmony'.")
    return 0


def run_bridge(args: argparse.Namespace) -> int:
    import traceback

    from . import bridge as B

    if args.port:
        B.RECV_PORT = args.port
    try:
        return B.Bridge().serve()
    except KeyboardInterrupt:
        return 0
    except Exception:  # noqa: BLE001
        # Last resort. If the bridge dies, the window must not close on top of
        # the reason -- "it crashed" with nothing to read is the worst possible
        # report, and it is what the user got.
        print("\n" + "=" * 60)
        print("the bridge stopped with an error:")
        print(traceback.format_exc())
        print("=" * 60)
        print("Copy the lines above - they say exactly what happened.")
        try:
            input("press Enter to close ...")
        except EOFError:
            pass
        return 1


INSTALL = Tool(
    name="bitwig-install", title="Install Bitwig extension", group="Bitwig",
    run=run_install, order=10,
    help="build and install the Bitwig control-surface extension",
    blurb="Compiles the bridge extension and copies it into your Bitwig "
          "Extensions folder.",
    note="AFTER INSTALLING: fully quit and reopen Bitwig, then Settings > "
         "Controllers > Add Controller > AG Music Tool Workbench > Harmony "
         "Bridge. The restart matters — the extension's port is held for the "
         "life of the Bitwig process, so installing over a running copy and "
         "re-adding the controller is the one sequence that reliably fails.\n"
         "\n"
         "Needs no JDK: it compiles with the Eclipse batch compiler running on "
         "Bitwig's own bundled java.exe, against the API classes inside "
         "Bitwig's bitwig.jar. Nothing is added to PATH. If it reports ecj "
         "missing, that jar is the one download this needs.",
    fields=[
        Field("dest", "Extensions folder", "dir", flag="--dest", advanced=True,
              help="blank = your Bitwig Extensions folder"),
        Field("out", "Build to", "text", flag="--out", advanced=True),
        Field("no_install", "Build only, don't copy", "bool",
              flag="--no-install", advanced=True),
    ],
)

BRIDGE = Tool(
    name="bitwig-bridge", title="Bitwig bridge", group="Bitwig",
    run=run_bridge, order=20, background=True, opens_browser=True,
    help="run the workbench end of the Bitwig bridge",
    blurb="Streams whatever clip is selected in Bitwig to a live piano-roll "
          "page, and sends analysis and results back. Start it here and leave "
          "it running; press Stop when you are done.",
    note="LIVE VIEW: once running, open http://127.0.0.1:8750/ — it draws the "
         "selected clip and redraws as you click around Bitwig.\n"
         "\n"
         "FIRST TIME, in Bitwig: Settings > Controllers > Add Controller > "
         "AG Music Tool Workbench > Harmony Bridge. Run 'Install Bitwig "
         "extension' first if it is not in that list, and fully quit and "
         "reopen Bitwig after installing — the extension holds its port for "
         "the life of the Bitwig process, so re-adding the controller without "
         "a restart is the one thing that reliably breaks it.\n"
         "\n"
         "Typed commands (r to reduce, a to analyse) need a console, so run it "
         "from a terminal if you want those. Started from here it still "
         "streams the live view, which is what most of the value is.",
    fields=[
        Field("port", "Listen port", "int", flag="--port", default=8732,
              advanced=True),
    ],
)

TOOLS = [INSTALL, BRIDGE]

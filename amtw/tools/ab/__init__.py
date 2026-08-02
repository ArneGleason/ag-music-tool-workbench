"""A/B listening tool — the thing verdicts actually come from."""
from __future__ import annotations

import argparse

from ...spec import AUDIO, Field, Tool


def run(args: argparse.Namespace) -> int:
    from .abtool import serve

    return serve(args.files, port=args.port, notes=args.notes)


TOOL = Tool(
    name="ab", title="A/B listening", group="Listening", run=run,
    help="A/B compare aligned audio files in the browser",
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
)

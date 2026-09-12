"""Listen before committing to a separated kit."""
from ...spec import AUDIO, Field, Tool


def run(args):
    from .audition import render
    render(args.input, args.starts, args.duration)
    return 0


TOOL = Tool(
    name="drum-audition", title="Drum separation audition", group="Drums", run=run,
    blurb="Separate short passages into six drum parts, with an original, recombined kit and difference comparison.",
    note="Separation only: no regeneration, gating or normalization. Listen for missing hits and altered cymbal tails. Claps have no dedicated class. Requires shared DrumSep weights; see docs/drum-audition.md.",
    fields=[Field("input", "Drum stem", "file", accept=AUDIO, root="downloads", required=True),
            Field("starts", "Excerpt starts (seconds)", "floats", flag="--starts", default=[40, 95, 180]),
            Field("duration", "Seconds per excerpt", "float", flag="--duration", default=12, min=2, max=30)],
)

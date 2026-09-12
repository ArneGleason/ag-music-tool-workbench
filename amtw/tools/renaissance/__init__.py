"""The approved Renaissance core vocal, rendered without Apollo."""
from ...spec import AUDIO, Field, Tool


def run(args):
    from .render import render
    render(args.input)
    return 0


TOOL = Tool(
    name="renaissance", title="Renaissance vocal cleanup", group="Pipeline", run=run,
    blurb="Render a full cleaned vocal into the shared runtime, preserving duration and stereo channels.",
    note="Keeps a cleaner core voice but can remove intentional doubling and effects. Keep the original for blending. Independent L/R processing; no Apollo or loudness normalization.",
    fields=[Field("input", "Vocal stem", "file", accept=AUDIO, root="downloads", required=True)],
)

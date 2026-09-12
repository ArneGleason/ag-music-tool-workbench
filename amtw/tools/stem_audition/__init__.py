"""Short restoration comparisons, so ears decide before a full-song render."""
from ...spec import AUDIO, Field, Tool


def run(args):
    from .audition import prepare
    prepare(args.input, args.starts, args.duration)
    return 0


TOOL = Tool(
    name="stem-audition", title="Vocal restoration audition", group="Listening",
    run=run, blurb="Prepare aligned original, Apollo and Renaissance excerpts plus a Renaissance difference signal.",
    note="Experimental: Renaissance processes stereo channels independently. Listen for lost breath or doubled voices; the difference is source minus output, not an isolated noise stem. Outputs go to the shared runtime.",
    fields=[
        Field("input", "Vocal stem", "file", accept=AUDIO, root="downloads", required=True),
        Field("starts", "Excerpt starts (seconds)", "floats", flag="--starts", default=[6, 48, 182]),
        Field("duration", "Seconds per excerpt", "float", flag="--duration", default=12),
    ],
)

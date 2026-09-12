"""Apollo comparisons reuse the accepted separation and its real context."""
from ...spec import Field, Tool


def run(args):
    from .audition import render
    render(args.jobs)
    return 0


TOOL = Tool(name="drum-restore-audition", title="Apollo drum refinement audition",
    group="Drums", run=run,
    blurb="Compare separated snare and hi-hat before/after Apollo universal, alone and back in the kit.",
    note="Select manifest.json files from Drum separation audition jobs. Reuses surrounding audio context; no gate, gain matching or timing correction. Improvement needs listening.",
    fields=[Field("jobs", "Separation manifests", "files", accept=".json", root="output", required=True)])

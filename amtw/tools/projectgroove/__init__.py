"""Consolidate an unedited Suno import and fit its performance grid.

Original MIDI is required: Bitwig names many imported children Acoustic Grand
Piano and does not move imported tempo automation when the clips are moved.
Exact note fingerprints establish identity; the source MIDI establishes time.
Never infer either from the group order or the misleading project tempo lane.
"""
from ...spec import Field, Tool


def run(args):
    from .process import process
    process(args.project, args.stems, args.out, args.work)
    return 0


TOOL = Tool(
    name="project-groove", title="Clean MIDI and fit project groove", group="Bitwig",
    run=run, order=25,
    blurb="Consolidate Suno MIDI groups, align them to the audio, and fit linear tempo ramps. Writes a separate DAWproject with its audio embedded.",
    note="For unedited imports with a common start in 4/4. Original MIDI files must match the project notes. Drums lead; instrument consensus fills drumless passages; vocals never set the grid. Audio moves slightly before the musical start to absorb the measured offset. Original audio bytes are retained. Review the click mix before composing.",
    fields=[
        Field("project", "DAWproject", "file", accept=["dawproject"], root="bitwig", required=True),
        Field("stems", "Original Suno stems folder", "dir", root="downloads", required=True),
        Field("out", "Output DAWproject", "text", flag="--out", required=True),
        Field("work", "Review and analysis folder", "text", flag="--work", required=True),
    ],
)

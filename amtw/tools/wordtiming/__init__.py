"""Acoustic lyric alignment; authored performance text stays separate from results."""
from ...spec import AUDIO, Field, Tool


def run(args):
    import subprocess
    from pathlib import Path
    from ...core.paths import RUNTIME_ROOT, subprocess_env, venv_python
    command = [str(venv_python('vevo2')), str(Path(__file__).with_name('align.py')),
               '--audio', args.audio, '--performance', args.performance, '--out', args.out,
               '--offset', str(args.offset), '--runtime', str(RUNTIME_ROOT)]
    return subprocess.call(command, env=subprocess_env())


ALIGN_TOOL = Tool(
    name='word-timing', title='Align performed lyric words', group='Analysis', run=run,
    blurb='Align a reconciled performance transcript to a vocal stem. Save word edges, review flags and audition files.',
    note='Input JSON holds phrases with source-second start/end windows and performed text. Singing, wordless ad-libs and repeats need review. Word ends are acoustically aligned, never set to the next onset or snapped to beats. Requires the word-timing runtime overlay and existing vevo2 environment; see tool README.',
    fields=[Field('audio', 'Vocal stem', 'file', flag='--audio', accept=AUDIO, required=True),
            Field('performance', 'Performed lyric JSON', 'file', flag='--performance', accept=['json'], required=True),
            Field('out', 'Result directory', 'dir', flag='--out', required=True),
            Field('offset', 'Stem start in master (seconds)', 'float', flag='--offset', default=0.0)],
)


def review(args):
    from .serve import serve
    serve(args.directory,args.port)
    return 0


TOOLS = [ALIGN_TOOL, Tool(
    name='word-timing-review', title='Open vocal timing review', group='Analysis', run=review,
    background=True, blurb='Serve saved word-timing results with accurate audio seeking.',
    note='Open the printed localhost URL. Keep this running while auditioning. Does not change timing files.',
    fields=[Field('directory','Timing result directory','dir',required=True),
            Field('port','Port','int',flag='--port',default=8741,advanced=True)],
)]

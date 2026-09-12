"""Full-length delivery of the drum choices approved by listening."""
from ...spec import AUDIO, Field, Tool

def run(args):
    from .render import render
    render(args.input)
    return 0

TOOL=Tool(name='drum-render',title='Render separated drums',group='Drums',run=run,
    blurb='Full-length six-part separation, with Apollo on active hi-hat/shaker passages only.',
    note='Keeps untreated snare, kick and percussion. Quiet hi-hat stretches remain unchanged; no gating or brightening. Retains all six raw parts for recovery. One GPU job at a time.',
    fields=[Field('input','Drum stem','file',accept=AUDIO,root='downloads',required=True)])

"""Persistent, local listening notes, separate from generated timing data."""
from ...spec import Field,Tool

def run(args):
 from .server import serve
 serve(args.directory,args.port)
 return 0
TOOL=Tool(name='creative-notes',title='Listen and mark creative notes',group='Video',run=run,background=True,
 blurb='Linked listening timeline and asset catalog with dictation, stable IDs and version reviews.',
 note='Notes save to creative-notes.json; asset reviews save to assets/catalog.json. Approval belongs to one asset version. Addressed timeline notes remain recoverable. Blender remains the rendering rig.',
 fields=[Field('directory','Timing job directory','dir',required=True),Field('port','Port','int',flag='--port',default=8742,advanced=True)])

"""Blender-native timing animatic, following the Rivers VSE workflow."""
from ...spec import Field, Tool

def run(args):
    import subprocess
    from pathlib import Path
    from ...core.paths import venv_python, subprocess_env
    here=Path(__file__).parent
    cmd=[str(venv_python('vevo2')),str(here/'prepare.py'),'--timing',args.timing,'--dawproject',args.dawproject,'--out',args.out]
    result=subprocess.call(cmd,env=subprocess_env())
    if result:return result
    cmd=[args.blender,'-b','--python-exit-code','1','-P',str(here/'build.py'),'--',args.out]
    if args.render:cmd.append('--render')
    result=subprocess.call(cmd,env=subprocess_env())
    if result:return result
    return subprocess.call([args.blender,'-b',str(Path(args.out)/'MonstersLoose-lyric-animatic-v01.blend'),'--python-exit-code','1','-P',str(here/'finish.py')],env=subprocess_env())

TOOL=Tool(name='lyric-animatic',title='Build Blender lyric animatic',group='Video',run=run,
 blurb='Build an editable Blender timing sheet with performed words, DAW beats and vocal amplitude.',
 note='Uses the Rivers of Mars VSE pattern. Alignment remains provisional. Outputs a separate .blend; Render also creates a full-song MP4. Requires Blender and the existing vevo2 audio environment. Does not edit the DAW project.',
 fields=[Field('timing','Combined vocal timing JSON','file',flag='--timing',accept=['json'],required=True),
 Field('dawproject','Locked DAWproject export','file',flag='--dawproject',accept=['dawproject'],required=True),
 Field('out','Animatic output folder','dir',flag='--out',required=True),
 Field('render','Render full-song video','bool',flag='--render'),
 Field('blender','Blender executable','file',flag='--blender',default=r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe',advanced=True)])

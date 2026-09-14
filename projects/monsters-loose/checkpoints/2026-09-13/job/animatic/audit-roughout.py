import bpy,json,pathlib
root=pathlib.Path(__file__).resolve().parent
def audio_state(scene):
    return [(st.name,bpy.path.abspath(st.sound.filepath),st.frame_start,st.frame_final_start,st.frame_final_end,st.volume) for st in scene.sequence_editor.strips if st.type=='SOUND']
bpy.ops.wm.open_mainfile(filepath=str(root/'MonstersLoose-narrative-animatic-v02.blend'))
original=audio_state(bpy.context.scene)
bpy.ops.wm.open_mainfile(filepath=str(root/'MonstersLoose-scene-roughout-v04.blend'))
s=bpy.context.scene;images=sorted([st for st in s.sequence_editor.strips if st.channel==1],key=lambda x:x.frame_final_start)
assert audio_state(s)==original,'Audio changed'
assert images[0].frame_final_start==s.frame_start
assert images[-1].frame_final_end==s.frame_end+1
for a,b in zip(images,images[1:]):assert a.frame_final_end==b.frame_final_start,(a.name,b.name)
for st in images:
    assert st.type=='IMAGE'
    assert pathlib.Path(bpy.path.abspath(st.directory),st.elements[0].filename).is_file()
report={'images':len(images),'unique_assets':len({st['asset_id'] for st in images}),'frames':s.frame_end,'fps':s.render.fps,'audio_identical_to_narrative_v02':True,'coverage':'continuous, no gaps or overlaps, including final frame'}
(root/'roughout-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(report)

import bpy,json,pathlib
p=pathlib.Path(__file__).resolve().parent
def snapshot(name):
 bpy.ops.wm.open_mainfile(filepath=str(p/name));s=bpy.context.scene
 return {'words':{st.name:[st.text,st.frame_final_start,st.frame_final_end,st['acoustic_start_seconds'],st['acoustic_end_seconds']] for st in s.sequence_editor.strips if 'acoustic_start_seconds' in st},'audio':[(str(pathlib.Path(bpy.path.abspath(st.sound.filepath)).resolve()),st.frame_final_start,st.frame_final_end,st.volume) for st in s.sequence_editor.strips if st.type=='SOUND'],'frames':s.frame_end,'fps':s.render.fps}
a=snapshot('MonstersLoose-lyric-animatic-v01.blend');b=snapshot('MonstersLoose-narrative-animatic-v02.blend')
assert a==b,'Source lyric/audio timing changed'
s=bpy.context.scene
bgs=sorted([st for st in s.sequence_editor.strips if st.channel==1],key=lambda st:st.frame_final_start)
assert bgs[0].frame_final_start==1 and bgs[-1].frame_final_end==s.frame_end+1
assert all(x.frame_final_end==y.frame_final_start for x,y in zip(bgs,bgs[1:]))
for channel,count in [(100,15),(101,28),(102,28)]:
 strips=sorted([st for st in s.sequence_editor.strips if st.channel==channel],key=lambda st:st.frame_final_start)
 assert len(strips)==count and strips[0].frame_final_start==1 and strips[-1].frame_final_end==s.frame_end+1
 assert all(x.frame_final_end==y.frame_final_start for x,y in zip(strips,strips[1:]))
r={'native_lyric_audio_unchanged':True,'word_strips':len(b['words']),'frames':b['frames'],'fps':b['fps'],'scenes':len(bgs),'caption_cards':28,'coverage':'continuous from frame 1 through 5290','audio':b['audio']}
(p/'narrative-native-validation.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps(r))

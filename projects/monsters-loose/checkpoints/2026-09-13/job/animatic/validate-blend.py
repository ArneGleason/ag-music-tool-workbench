import bpy,json,pathlib
s=bpy.context.scene;p=pathlib.Path(bpy.data.filepath).parent
seq=s.sequence_editor.strips
words=[st for st in seq if st.type=='TEXT' and 'acoustic_start_seconds' in st]
assert len(words)==360
assert len([st for st in seq if st.type=='SOUND'])==1
assert s.frame_start==1 and s.frame_end==5290
for st in words:
 a=round(st['acoustic_start_seconds']*24)+1;e=round(st['acoustic_end_seconds']*24)+1
 assert st.frame_final_start<=a and st.frame_final_end>=e,(st.name,st.frame_final_start,a,st.frame_final_end,e)
print('VALIDATED 360 native text strips, complete word spans, master frame 1, 5290 frames.')
print([(sc.name,[(a.type,a.spaces.active.type) for a in sc.areas]) for sc in bpy.data.screens][:2])
(p/'blender-validation.json').write_text(json.dumps(dict(word_strips=len(words),frames=s.frame_end,checks=['all acoustic word spans covered','one master audio strip','master zero at frame 1','native editable text'],screens=[dict(name=sc.name,areas=[a.type for a in sc.areas]) for sc in bpy.data.screens]),indent=2))

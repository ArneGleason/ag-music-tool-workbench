"""Full scene-level roughout in the existing editable Blender sequencer rig."""
import bpy,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parent;job=root.parent
bpy.ops.wm.open_mainfile(filepath=str(root/'MonstersLoose-narrative-animatic-v02.blend'))
s=bpy.context.scene;strips=s.sequence_editor.strips;fps=s.render.fps
specs=json.loads((job/'rough-anchors-v04.json').read_text(encoding='utf-8'))
data=json.loads((root/'animatic-data.json').read_text(encoding='utf-8'))
words={w['id']:w for p in data['phrases'] for w in p.get('words',[])}
for st in list(strips):
    if st.channel==1 and st.type=='COLOR':strips.remove(st);continue
    if st.type=='TEXT' and 'acoustic_start_seconds' in st:
        w=words.get(st.name.split(' ',1)[0])
        if w:st.text=w['text']
    if st.name=='Pass label':st.text='SCENE ROUGHOUT / 04'
for x in specs:
    a=round(x['start']*fps)+1;b=min(s.frame_end+1,round(x['end']*fps)+1)
    # The existing rig rounds the audio tail up to a complete output frame.
    if x is specs[-1]:b=s.frame_end+1
    st=strips.new_image(name=x['id']+' / '+x['name'],filepath=str(job/'assets'/x['image']),channel=1,frame_start=a,fit_method='FIT')
    st.frame_final_duration=b-a;st.color_multiply=.48
    st['asset_id']=x['id'];st['scene_id']=x['scene'];st['purpose']='Broad scene beat; not a locked shot.'
    s.timeline_markers.new(x['id'],frame=a)
s.name='Monsters Loose - scene roughout v04'
s.render.image_settings.media_type='IMAGE';s.render.image_settings.file_format='PNG'
for sec in (15,74,150,210):
    s.frame_set(round(sec*fps)+1);s.render.filepath=str(root/f'roughout-preview-{sec}.png');bpy.ops.render.render(write_still=True)
s.render.image_settings.media_type='VIDEO';s.render.image_settings.file_format='FFMPEG'
s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264';s.render.ffmpeg.constant_rate_factor='HIGH';s.render.ffmpeg.audio_codec='AAC';s.render.ffmpeg.audio_bitrate=256
s.render.filepath=str(root/'MonstersLoose-scene-roughout-v04.mp4');s.frame_set(1)
bpy.ops.file.make_paths_relative();bpy.ops.wm.save_as_mainfile(filepath=str(root/'MonstersLoose-scene-roughout-v04.blend'))
print('Saved',len(specs),'scene anchors',s.frame_end,'frames',flush=True)
if '--render' in sys.argv:bpy.ops.render.render(animation=True)

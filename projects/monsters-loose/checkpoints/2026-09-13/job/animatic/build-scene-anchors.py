"""Scene mood anchors in the native VSE rig; no invented shot cuts or camera moves."""
import bpy, json, pathlib, sys
root=pathlib.Path(__file__).resolve().parent
job=root.parent
bpy.ops.wm.open_mainfile(filepath=str(root/'MonstersLoose-narrative-animatic-v02.blend'))
s=bpy.context.scene; strips=s.sequence_editor.strips; fps=s.render.fps
specs=json.loads((job/'scene-anchor-specs.json').read_text(encoding='utf-8'))
# Carry current text corrections into the editable native rig, not the old render.
data=json.loads((root/'animatic-data.json').read_text(encoding='utf-8'))
words={w['id']:w for p in data['phrases'] for w in p.get('words',[])}
for st in strips:
 if st.type=='TEXT' and 'acoustic_start_seconds' in st:
  w=words.get(st.name.split(' ',1)[0])
  if w: st.text=w['text']
 if st.name=='Pass label':st.text='SCENE ANCHORS / 03'
for spec in specs:
 a=round(spec['start']*fps)+1; b=round(spec['end']*fps)+1
 # Replace just the flat background; all lyric/music/narrative strips stay editable.
 for st in list(strips):
  if st.type=='COLOR' and st.channel==1 and st.frame_final_start==a:
   strips.remove(st)
 st=strips.new_image(name=spec['id']+' / '+spec['scene']+' mood anchor',filepath=str(job/'assets'/(spec['id']+'-v001.png')),channel=1,frame_start=a,fit_method='FIT')
 st.frame_final_duration=b-a
 st.color_multiply=.48
 st['purpose']='Scene mood reference held across broad scene; not a shot/start/end frame.'
 st['asset_id']=spec['id'];st['scene_id']=spec['scene']
 s.timeline_markers.new(spec['id']+' scene mood',frame=a)
s.name='Monsters Loose - scene anchors v03'
s.render.image_settings.media_type='IMAGE';s.render.image_settings.file_format='PNG'
s.frame_set(round(15*fps)+1);s.render.filepath=str(root/'scene-anchors-preview-15.png');bpy.ops.render.render(write_still=True)
s.render.image_settings.media_type='VIDEO';s.render.image_settings.file_format='FFMPEG'
s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264';s.render.ffmpeg.constant_rate_factor='HIGH';s.render.ffmpeg.audio_codec='AAC';s.render.ffmpeg.audio_bitrate=256
s.render.filepath=str(root/'MonstersLoose-scene-anchors-v03.mp4')
s.frame_set(1)
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=str(root/'MonstersLoose-scene-anchors-v03.blend'))
print('Scene anchors saved',len(specs),s.frame_end,fps,flush=True)
if '--render' in sys.argv:bpy.ops.render.render(animation=True)

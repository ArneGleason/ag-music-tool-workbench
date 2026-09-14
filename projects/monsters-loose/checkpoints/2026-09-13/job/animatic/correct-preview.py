import bpy,pathlib
p=pathlib.Path(bpy.data.filepath).parent;s=bpy.context.scene
# Repair the native rig first. The proof-only composition below reuses the
# already-rendered picture to avoid repeating unchanged lyric rendering.
label=next(x for x in s.sequence_editor.strips if x.name=='Meter unit');label.text='RMS  -60 to 0 dBFS';font=label.font
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
old=p/'MonstersLoose-lyric-animatic-v01.mp4';original=p/'render-before-label-fix.mp4';old.rename(original)
sc=bpy.data.scenes.new('Readout correction — render only');bpy.context.window.scene=sc
r=sc.render;r.engine='BLENDER_EEVEE';r.resolution_x=1280;r.resolution_y=720;r.resolution_percentage=100;r.fps=24;r.use_sequencer=True
sc.frame_start=1;sc.frame_end=5290;sc.view_settings.view_transform='Standard';sc.view_settings.look='None'
q=sc.sequence_editor_create().strips;q.new_movie(name='Native Blender lyric render',filepath=str(original),channel=1,frame_start=1)
# Use the original master so this pass does not re-encode previously encoded audio.
q.new_sound(name='Original locked master',filepath=str(p/'master.wav'),channel=2,frame_start=1)
st=q.new_effect(name='Clear only technical label',type='COLOR',channel=3,frame_start=1,length=5290);st.color=(.067,.157,.176);st.blend_type='ALPHA_OVER';st.transform.scale_x=230/1280;st.transform.scale_y=30/720;st.transform.offset_x=1045-640;st.transform.offset_y=139-360
st=q.new_effect(name='Correct RMS units',type='TEXT',channel=4,frame_start=1,length=5290);st.text='RMS  -60 to 0 dBFS';st.font=font;st.font_size=15;st.color=(.4,.52,.51,1);st.location=(.5,.5);st.anchor_x='CENTER';st.anchor_y='CENTER';st.alignment_x='CENTER';st.blend_type='ALPHA_OVER';st.transform.offset_x=1045-640;st.transform.offset_y=139-360
r.image_settings.media_type='VIDEO';r.image_settings.file_format='FFMPEG';r.ffmpeg.format='MPEG4';r.ffmpeg.codec='H264';r.ffmpeg.constant_rate_factor='HIGH';r.ffmpeg.audio_codec='AAC';r.ffmpeg.audio_bitrate=256;r.filepath=str(old)
bpy.ops.render.render(animation=True)

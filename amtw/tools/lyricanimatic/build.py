"""Editable VSE text and geometry strips. No browser renderer or baked lyric movie.

Frame 1 is master second zero. Acoustic edges stay in source JSON; frame rounding,
preview and hold are presentation only. Words use local-centred strip transforms
so a small scale emphasis cannot orbit the whole frame (Rivers VSE lesson).
"""
import bpy,blf,json,math,pathlib,sys
import numpy as np
out=pathlib.Path(sys.argv[sys.argv.index('--')+1]);d=json.loads((out/'animatic-data.json').read_text(encoding='utf-8'))
W,H=1280,720;fps=d['fps'];N=d['frames']
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene;s.name='Monsters Loose - lyric timing';s.render.resolution_x=W;s.render.resolution_y=H;s.render.resolution_percentage=100
s.render.fps=fps;s.frame_start=1;s.frame_end=N;s.render.use_sequencer=True;s.render.engine='BLENDER_EEVEE'
s.view_settings.view_transform='Standard';s.view_settings.look='None';s.view_settings.exposure=0;s.view_settings.gamma=1
seq=s.sequence_editor_create().strips
font=bpy.data.fonts.load(str(out/d['font']));fid=blf.load(str(out/d['font']))
INK=(.067,.157,.176,1);PAPER=(.945,.875,.714,1);RED=(1,.329,.184,1);MUTED=(.40,.52,.51,1);TEAL=(.23,.68,.64,1)
def F(t):return max(1,min(N+1,round(t*fps)+1))
def key(o,p,f,v):
 setattr(o,p,v);o.keyframe_insert(data_path=p,frame=f)
def effect(name,typ,ch,a=1,b=None):
 return seq.new_effect(name=name,type=typ,channel=ch,frame_start=a,length=max(1,(b if b is not None else N+1)-a))
def rect(name,x,y,w,h,c,ch,a=1,b=None):
 st=effect(name,'COLOR',ch,a,b);st.color=c[:3];st.blend_type='ALPHA_OVER'
 st.transform.scale_x=w/W;st.transform.scale_y=h/H;st.transform.offset_x=x-W/2;st.transform.offset_y=y-H/2
 return st
def text(name,body,x,y,size,c,ch,a=1,b=None):
 st=effect(name,'TEXT',ch,a,b);st.text=body;st.font=font;st.font_size=size;st.color=c;st.blend_type='ALPHA_OVER'
 st.location=(.5,.5);st.anchor_x='CENTER';st.anchor_y='CENTER';st.alignment_x='CENTER'
 st.transform.offset_x=x-W/2;st.transform.offset_y=y-H/2
 return st
rect('Ink background',W/2,H/2,W,H,INK,1)
rect('Cream top rule',640,630,1152,2,PAPER,3)
rect('Red registration accent',70,656,12,30,RED,4)
text('Song title',d['title'],236,660,32,PAPER,5)
text('Pass label','LYRIC ANIMATIC / 01',1070,660,22,MUTED,6)
text('Footer status','WORD TIMING DRAFT  /  AMBER = REVIEW',340,31,18,MUTED,6)
text('Lead label','LEAD',968,200,18,PAPER,5)
text('Backing label','BACKING',1125,200,18,TEAL,6)
# Quiet, fixed meters: -60 to 0 dBFS RMS, linear in dB, not decorative randomness.
for j,(role,col,x) in enumerate([('lead',PAPER,968),('backing',TEAL,1125)]):
 rect(role+' meter bed',x,164,124,10,MUTED,7+j)
 st=rect(role+' RMS -60 to 0 dBFS',x-62,164,1,10,col,9+j)
 for i,v in enumerate(d['envelopes'][role]):
  width=max(.1,124*v);key(st.transform,'scale_x',i+1,width/W);key(st.transform,'offset_x',i+1,x-62+width/2-W/2)
text('Meter unit','RMS  -60 to 0 dBFS',1045,139,15,MUTED,11)
# Generate the static measured overview in Blender itself; text remains native.
pix=np.zeros((H,W,4),dtype=np.float32)
def box(x0,y0,x1,y1,c):pix[max(0,int(y0)):min(H,int(y1)),max(0,int(x0)):min(W,int(x1))]=c
for x in range(64,1216,3):
 t=(x-64)/1152*d['duration'];v=d['envelopes']['lead'][min(N-1,int(t*fps))];height=max(1,26*v)
 box(x,89-height,x+2,89+height,(*TEAL[:3],.65))
for beat in d['beats']:
 x=64+1152*beat['time']/d['duration'];down=beat['beat']==1
 box(x,53,x+1,63 if down else 58,(*PAPER[:3],.8 if down else .28))
img=bpy.data.images.new('Measured lead envelope and tempo ticks',width=W,height=H,alpha=True)
img.pixels.foreach_set(pix.ravel());img.filepath_raw=str(out/'timing-overview.png');img.file_format='PNG';img.save()
st=seq.new_image(name='Lead envelope + actual DAW beat grid',filepath=str(out/'timing-overview.png'),channel=12,frame_start=1);st.frame_final_duration=N;st.blend_type='ALPHA_OVER'
playhead=rect('Master playhead',64,87,2,72,RED,13)
key(playhead.transform,'offset_x',1,64-W/2);key(playhead.transform,'offset_x',N,1216-W/2)
# Four native beat pads with a bar/beat readout. Export begins on beat 4, not 1.
for k in range(4):rect('Beat pad '+str(k+1),82+k*42,180,26,8,MUTED,14+k)
for i,b in enumerate(d['beats'][:-1]):
 a=F(b['time']);end=F(d['beats'][i+1]['time'])
 if a>=N:continue
 st=rect(f"Beat {b['bar']}.{b['beat']}",82+(b['beat']-1)*42,180,26,8,RED if b['beat']==1 else PAPER,18,a,end)
 key(st,'blend_alpha',a,1);key(st,'blend_alpha',min(end-1,a+5),.35)
 text('Grid '+str(i),f"BAR {b['bar']:02} / BEAT {b['beat']}",376,181,22,PAPER,19,a,end)
 s.timeline_markers.new(f"{b['bar']}.{b['beat']}",frame=a)
for second in range(math.ceil(d['duration'])):
 text('Master clock '+str(second),f'{second//60}:{second%60:02}',675,181,22,PAPER,95,F(second),F(second+1))
# Phrase layout with whole-line preview, per-word timing, and duration underline.
phrases=[]
# Adjacent acoustic windows can overlap. Group them rather than clipping either
# word or allowing two pages to overwrite each other. This changes only layout.
for original in d['phrases']:
 p=dict(original);p['words']=list(original['words'])
 if phrases and p['start'] < phrases[-1]['end']:
  previous=phrases[-1];previous['id']+=' + '+p['id'];previous['words']+=p['words'];previous['end']=max(previous['end'],p['end']);previous['text']+=' '+p['text']
 else:phrases.append(p)
layout=[]
for i,p in enumerate(phrases):
 a=F(max(0,p['start']-.5));end=F(min(d['duration'],max(p['end'],min(p['end']+1.0,phrases[i+1]['start']-.5 if i+1<len(phrases) else d['duration']))))
 if i:a=max(a,layout[-1]['end_frame'])
 end=max(a+1,end)
 words=p['words'];is_event=not words
 if is_event:words=[dict(text='[vocal sound]',start=p['start'],end=p['end'],flags=['unresolved'])]
 size=70 if len(words)<10 else 62 if len(words)<18 else 52
 if p.get('kind')=='vocalization':size=60
 def measure(t):blf.size(fid,size);return blf.dimensions(fid,t)[0]
 widths=[measure(w['text']) for w in words];gap=measure(' ')+7
 # Wrap measured words into stable rows; no word moves to a new line mid-song.
 lines=[[]];used=0
 for j,ww in enumerate(widths):
  if lines[-1] and used+gap+ww>1060:lines.append([]);used=0
  lines[-1].append(j);used+=ww+(gap if len(lines[-1])>1 else 0)
 if len(lines)==2:
  split=min(range(1,len(words)),key=lambda k:max(sum(widths[:k])+gap*(k-1),sum(widths[k:])+gap*(len(words)-k-1)))
  if max(sum(widths[:split])+gap*(split-1),sum(widths[split:])+gap*(len(words)-split-1))<1060:
   lines=[list(range(split)),list(range(split,len(words)))]
 assert len(lines)<=3
 for line in lines:assert sum(widths[j] for j in line)+gap*(len(line)-1)<1120
 record=dict(id=p['id'],start_frame=a,end_frame=end,words=[])
 label='VOCALIZATION / SYLLABLES PROVISIONAL' if p.get('kind')=='vocalization' else 'UNRESOLVED VOCAL SOUND' if is_event else 'LEAD VOCAL'
 text(p['id']+' role',label,640,546,19,MUTED,20,a,end)
 if any(w.get('flags') for w in words):text(p['id']+' review','•  TIMING / TEXT REVIEW',1050,31,18,(.76,.61,.35,1),21,a,end)
 for li,line in enumerate(lines):
  x=(W-sum(widths[j] for j in line)-gap*(len(line)-1))/2;y=411+(len(lines)-1)*49-li*98
  for j in line:
   w=words[j];ww=widths[j];cx=x+ww/2;on=max(a,F(w['start']));off=max(on+1,F(w['end']));ch=24+j*2
   st=text(w.get('id',p['id'])+' '+w['text'],w['text'],cx,y,size,MUTED,ch,a,end)
   st['acoustic_start_seconds']=w['start'];st['acoustic_end_seconds']=w['end'];st['review_flags']=', '.join(w.get('flags',[]))
   key(st,'color',a,MUTED);key(st,'color',max(a,on-1),MUTED);key(st,'color',on,PAPER)
   # Small entrance lift; meaningful emphasis is selective, with no reflow.
   key(st.transform,'offset_y',max(a,on-1),y-H/2-5);key(st.transform,'offset_y',on+2,y-H/2+3);key(st.transform,'offset_y',on+5,y-H/2)
   if w['text'].lower().strip('.,!?') in {'loose','monsters','higher','down','grow','shrink','mean'}:
    key(st.transform,'scale_x',on,1);key(st.transform,'scale_y',on,1)
    key(st.transform,'scale_x',on+3,1.06);key(st.transform,'scale_y',on+3,1.06)
    key(st.transform,'scale_x',off,1);key(st.transform,'scale_y',off,1)
   if on<end:
    under=rect(w.get('id',p['id'])+' duration',x,y-size*.48,1,4,RED,ch+1,on,min(end,off))
    key(under.transform,'scale_x',on,1/W);key(under.transform,'offset_x',on,x-W/2)
    key(under.transform,'scale_x',max(on+1,off-1),ww/W);key(under.transform,'offset_x',max(on+1,off-1),x+ww/2-W/2)
   record['words'].append(dict(text=w['text'],x=cx,y=y,width=ww,start=w['start'],end=w['end']))
   x+=ww+gap
 layout.append(record)
 s.timeline_markers.new(p['id']+' '+p['text'][:32],frame=F(p['start']))
# Deliberate rests rather than manufacturing vocals during gaps.
prev=1
for r in layout+[dict(start_frame=N+1,end_frame=N+1)]:
 if r['start_frame']-prev>fps:
  text('Vocal rest','MONSTERS LOOSE',640,420,64,PAPER,22,prev,r['start_frame'])
  text('Rest label','VOCAL REST',640,350,20,MUTED,23,prev,r['start_frame'])
 prev=r['end_frame']
seq.new_sound(name='LOCKED MASTER — zero at frame 1',filepath=str(out/'master.wav'),channel=2,frame_start=1)
s.sync_mode='AUDIO_SYNC'
# Linear prevents splines overshooting measured levels or timing edges.
if s.animation_data and s.animation_data.action:
 for layer in s.animation_data.action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for k in fc.keyframe_points:k.interpolation='LINEAR'
(out/'layout.json').write_text(json.dumps(layout,indent=2),encoding='utf-8')
bpy.data.texts.new('README — Monsters Loose').write('Blender VSE timing animatic. Frame 1 = master zero. 24 fps. Barlow Semi Condensed SemiBold. All words are editable TEXT strips; independent acoustic edges retained as strip properties. Source timings remain provisional. No caption boxes or speech bubbles yet. Lead/backing RMS meters are measured at frame rate, -60 to 0 dBFS. Beat markers integrate DAWproject linear tempo ramps. See animatic-data.json for provenance.\n')
# Save a useful Video Editing workspace when opened interactively.
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.type='SEQUENCE_EDITOR'
s.frame_set(F(12.5))
r=s.render
r.image_settings.file_format='PNG';r.image_settings.color_mode='RGBA'
for t in [12.5,46,132.5,199.9]:
 s.frame_set(F(t));r.filepath=str(out/f'preview-{t}.png');bpy.ops.render.render(write_still=True)
if hasattr(r.image_settings,'media_type'):r.image_settings.media_type='VIDEO'
r.image_settings.file_format='FFMPEG';r.ffmpeg.format='MPEG4';r.ffmpeg.codec='H264';r.ffmpeg.constant_rate_factor='HIGH';r.ffmpeg.audio_codec='AAC';r.ffmpeg.audio_bitrate=256
r.filepath=str(out/'MonstersLoose-lyric-animatic-v01.mp4');s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'MonstersLoose-lyric-animatic-v01.blend'))
print(f'BUILT: {len(seq)} editable strips, {N} frames.',flush=True)
if '--render' in sys.argv:bpy.ops.render.render(animation=True)


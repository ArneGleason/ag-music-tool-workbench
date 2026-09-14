"""Add broad narrative beats to the native Blender lyric rig; no shot decisions."""
import bpy, blf, json, pathlib, math
ROOT = pathlib.Path(__file__).resolve().parent
source = json.loads((ROOT.parent/'creative-notes.json').read_text(encoding='utf-8'))
# Scene boundaries are editorial groupings of approximate user anchors, not cuts.
scenes = [
 (0, '01 / A STRANGE PLACE', (.045,.105,.095), [
  (0, 'An obscure creature detail foreshadows what is coming.\nThe swamp surrounds a secret monster zoo and laboratory.')]),
 (8.6, '02 / THE KEEPER ON DUTY', (.045,.105,.15), [
  (8.6, 'Meet our keeper and singer: capable, alert, expecting trouble.\nThe creatures remain mostly hidden.'),
  (12.13, 'A breached enclosure hints that something has slipped out.\nThe keeper hears trouble before we see its source.')]),
 (20.96, '03 / A PLACE BUILT FOR MONSTERS', (.115,.105,.045), [
  (20.96, 'Illustrated creature faces hint at the hybrids made here.\nThe keeper plays with expressions; the real monsters stay hidden.'),
  (26.07, 'Her equipment hints at a special restraining lasso.\nA garbled PA announcement warns that something is wrong.'),
  (36.38, 'Explore the zoo\'s different habitats and small enclosures.\nBuilding cage-rattles suggest something much larger inside.')]),
 (42.98, '04 / DANGEROUS AMBITION', (.125,.055,.10), [
  (42.98, 'Meet the laboratory team and its reckless scientist.\nA town left burning recalls what their last creation could do.'),
  (48.37, 'The scientist proposes something even bigger and meaner.\nThe keeper looks upward: its full scale stays out of view.')]),
 (54.32, '05 / TROUBLE BREWING', (.075,.09,.14), [
  (54.32, 'Return to the zoo as the threat of escape builds.\nOPEN: use this breathing space to establish what comes next.')]),
 (62.77, '06 / THE VISITORS\' TOUR', (.11,.085,.04), [
  (62.77, 'The keeper welcomes visitors to this strangely cheerful zoo.\nHer account begins to reveal how dangerous its residents are.'),
  (71.14, 'Now demonstrate her lasso skills: she keeps the monsters in.\nShe enjoys giving the visitors a playful scare.'),
  (78.48, 'A skeptical child sees through the keeper\'s teasing.\nReal danger nearby makes that confidence funny and uneasy.')]),
 (84.8, '07 / CHOOSE YOUR CREATURE', (.04,.115,.10), [
  (84.8, 'Reveal the variety: jungle, desert, lake, ice and alien habitats.\nSave the creatures of the surrounding swamp for later.'),
  (90.37, 'Imagine the monsters in the wild, where they were captured.\nTheir version of hide-and-seek is really hunting.')]),
 (102.55, '08 / THE MONSTER SHOWDOWN', (.16,.055,.04), [
  (102.55, 'A countdown gathers monsters into a showdown.\nVisitors root for favorites; the contest soon narrows to two.'),
  (109.52, 'Two final rivals face off while spectators back their choices.\nOPEN: a natural clash or something staged at the zoo?'),
  (113.6, 'An impossible monster-movie kick sends a rival over mountains.\nBattered but resilient, it prepares to return to the fight.')]),
 (121.04, '09 / WHAT SHALL WE MAKE NEXT?', (.125,.055,.10), [
  (121.04, 'The scientists regroup to imagine their next creation.\nPerhaps the visitors join this dangerously enthusiastic discussion.')]),
 (134.23, '10 / THE SCIENTIST\'S SECRET', (.155,.045,.055), [
  (134.23, 'Reveal the scientist\'s plan: unlock the zoo and let them loose.\nThis circles back to the warnings we heard at the beginning.')]),
 (140.74, '11 / CONTAINMENT FAILS', (.135,.07,.035), [
  (140.74, 'A huge creature shrinks small enough to escape.\nAbilities once contained now become ways out.'),
  (146.41, 'A small, insect-like creature grows to enormous size.\nIts enclosure cannot hold it.'),
  (151.7, 'Another creature becomes smoke and slips through a keyhole.\nAn apparently impenetrable door is no defense.')]),
 (157.23, '12 / NO WAY. YES WAY.', (.11,.085,.04), [
  (157.23, 'The child refuses to believe it; the keeper insists it is true.\nIs she exaggerating, or should you always trust the tour guide?'),
  (161.74, 'Widen the story to the escape unfolding around them.\nSome people seem to enjoy it as a show rather than a disaster.')]),
 (171.87, '13 / FAMILIAR FACES, NOW REAL', (.115,.105,.045), [
  (171.87, 'Return to the faces introduced on the illustrated zoo sign.\nNow the audience meets the actual creatures.')]),
 (176.7, '14 / BEYOND THE FENCE', (.045,.105,.095), [
  (176.7, 'Return to the swamp outside the zoo: creatures live here too.\nPOSSIBILITY: they and the scientist share a secret escape plan.'),
  (183.88, 'Revisit our favorite monsters as they finally break free.\nEven the keeper\'s lasso skills cannot hold them all.')]),
 (206.27, '15 / LOOSE AT LAST', (.065,.115,.13), [
  (206.27, 'Collected and created monsters are free to be themselves.\nThe ending relaxes into natural behavior, rather than a rampage.')]),
]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'MonstersLoose-lyric-animatic-v01.blend'))
s=bpy.context.scene; seq=s.sequence_editor.strips; fps=s.render.fps; N=s.frame_end
s.name='Monsters Loose - timed narrative v02'
# The base .blend is a rendered snapshot. Carry subsequent text-only corrections
# from the current source forward without silently restoring old lyric labels.
current_data=json.loads((ROOT/'animatic-data.json').read_text(encoding='utf-8'))
current_words={w['id']:w for p in current_data['phrases'] for w in p.get('words',[])}
for st in seq:
 if st.type=='TEXT' and 'acoustic_start_seconds' in st:
  word=current_words.get(st.name.split(' ',1)[0])
  if word is not None:st.text=word['text']
font=next(f for f in bpy.data.fonts if 'Barlow' in f.name)
fid=blf.load(str(ROOT/'BarlowSemiCondensed-SemiBold.ttf'))
def F(t): return min(N+1,max(1,round(t*fps)+1))
def text(name,body,y,size,color,ch,a,b):
 st=seq.new_effect(name=name,type='TEXT',channel=ch,frame_start=a,length=b-a)
 st.text=body;st.font=font;st.font_size=size;st.color=color;st.blend_type='ALPHA_OVER'
 st.location=(.5,.5);st.anchor_x='CENTER';st.anchor_y='CENTER';st.alignment_x='CENTER'
 st.transform.offset_y=y-360
 blf.size(fid,size)
 assert max(blf.dimensions(fid,line)[0] for line in body.split('\n')) < 1150, body
 return st
# Free the area just above the lyrics; retain all lyric timing and music geometry.
for st in list(seq):
 if st.name=='Ink background' or (st.type=='TEXT' and (st.name.endswith(' role') or st.text in ['LEAD VOCAL','VOCALIZATION / SYLLABLES PROVISIONAL','UNRESOLVED VOCAL SOUND'])):
  seq.remove(st)
 elif st.name=='Pass label': st.text='NARRATIVE / 02'
# Use opaque flat colors under every original editable layer. Same setting gets
# the same color on return, so color does not imply that every caption is a cut.
records=[]
for i,(start,title,col,cards) in enumerate(scenes):
 end=scenes[i+1][0] if i+1<len(scenes) else N/fps
 a,b=F(start),F(end)
 bg=seq.new_effect(name=title+' background',type='COLOR',channel=1,frame_start=a,length=b-a);bg.color=col
 text(title,title,611,21,(.65,.78,.76,1),100,a,b)
 s.timeline_markers.new('STORY '+title,frame=a)
 item={'scene':title,'start':start,'end':min(end,220.387),'color':col,'cards':[]}
 for j,(t,body) in enumerate(cards):
  e=cards[j+1][0] if j+1<len(cards) else end
  # Two single-line strips make line height independent of Blender font metrics.
  lines=body.split('\n')
  for k,line in enumerate(lines):text(title+' narrative '+str(j)+' '+str(k),line,582-k*29,26,(.96,.92,.82,1),101+k,F(t),F(e))
  item['cards'].append({'start':t,'end':min(e,220.387),'text':body})
 records.append(item)
data={'title':'Monsters Loose — timed narrative v02','source_revision':source['revision'],'source_note_ids':[n['id'] for n in source['notes']], 'fps':fps,'frames':N,'duration':220.387,'note':'Broad editorial scene groupings, not a shot list. Anchors remain approximate. Original notes are not marked addressed. Lyric corrections remain pending in this pass.','scenes':records}
(ROOT/'narrative-v02.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
def tc(t): return f'{int(t)//60}:{t%60:04.1f}'
md=['# Monsters Loose — timed narrative v02','',data['note'],'','Scene colors identify broad settings or story phases; captions within them do not prescribe cuts.','']
for rec in records:
 md += [f"## {tc(rec['start'])}–{tc(rec['end'])} · {rec['scene']}",'']
 for card in rec['cards']:md += [f"**{tc(card['start'])}** — "+card['text'].replace('\n',' '),'']
md += ['## Pending lyric review','','The source notes also request repeated “play” rather than “baby,” a later entrance for “five,” and an “un/until” interpretation of the vocalization around 2:12. These are retained for a dedicated timing/text correction pass.','','World direction: retro graphic-novel B-movie fun, with hybrid creatures and an East/West swamp setting. Possible Rivers of Mars amber/DNA callback remains available. No creature designs, camera plan, or shot count are locked.']
(ROOT/'narrative-v02.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
# Preserve exact original notes with this revision for future provenance.
(ROOT/'narrative-v02-source-notes.json').write_text(json.dumps(source,ensure_ascii=False,indent=2),encoding='utf-8')
s.render.image_settings.media_type='IMAGE';s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
for t in [21,80,114,148,179,211]:
 s.frame_set(F(t));s.render.filepath=str(ROOT/f'narrative-preview-{t}.png');bpy.ops.render.render(write_still=True)
s.render.image_settings.media_type='VIDEO';s.render.image_settings.file_format='FFMPEG'
s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264';s.render.ffmpeg.constant_rate_factor='HIGH';s.render.ffmpeg.audio_codec='AAC';s.render.ffmpeg.audio_bitrate=256
s.render.filepath=str(ROOT/'MonstersLoose-narrative-animatic-v02.mp4')
s.frame_set(1)
for f in bpy.data.fonts:
 if f.filepath and not f.packed_file:
  try:f.pack()
  except RuntimeError:pass
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'MonstersLoose-narrative-animatic-v02.blend'))
print('Narrative saved: 15 scenes, '+str(sum(len(x[3]) for x in scenes))+' cards',flush=True)
if '--render' in __import__('sys').argv:bpy.ops.render.render(animation=True)

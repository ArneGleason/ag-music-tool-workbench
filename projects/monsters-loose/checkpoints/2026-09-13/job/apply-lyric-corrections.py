"""User-confirmed text corrections; preserve acoustic edges and raw ASR evidence."""
from pathlib import Path
import json,shutil,csv,datetime
root=Path(__file__).resolve().parent
backup=root/'lyric-correction-history'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True)
changes={
 'lead-026':('And play, play.','User correction at 103.38s: final word is play, not baby; four play repetitions across this passage.'),
 'lead-036':('Un un un un nun nun nun nun…','User interpretation at 131.72s: musical un/nun pickup evokes Undone but resolves into Until in lead-037. Existing eight timing slots are provisional; syllable count and edges are not newly verified.')}
words={'lead-026-w003':'play.'}
words.update({f'lead-036-w{i+1:03}':x for i,x in enumerate(['Un','un','un','un','nun','nun','nun','nun…'])})
def update(obj):
 if isinstance(obj,list):
  for item in obj:update(item)
 elif isinstance(obj,dict):
  ident=obj.get('id')
  if ident in changes:
   obj['text'],obj['note']=changes[ident]
   obj['text_status']='user_corrected' if ident=='lead-026' else 'user_interpretation_syllable_count_provisional'
   if 'alignment_segments' in obj:obj['alignment_segments_status']='Historical alignment of previous text; do not treat as alignment of the corrected text.'
  if ident in words:
   obj['text']=words[ident];obj['text_status']='user_corrected'
   if 'flags' in obj:
    obj['flags']=list(dict.fromkeys(obj['flags']+['text_corrected_alignment_pending']))
  if ident in ('lead-027','lead-027-w001'):
   obj['timing_review_note']='User reports Five starts too early. A later onset is required; exact replacement timestamp remains unmeasured.'
  for key,value in obj.items():
   if key not in ('raw_candidates','alignment_segments'):update(value)
def edges(obj):
 out=[]
 if isinstance(obj,list):
  for v in obj:out+=edges(v)
 elif isinstance(obj,dict):
  if 'id' in obj:out.append((obj['id'],obj.get('start'),obj.get('end'),obj.get('source_start'),obj.get('source_end')))
  for v in obj.values():
   if isinstance(v,(dict,list)):out+=edges(v)
 return out
for rel in ['lead.performance.json','lead/words.json','timing.json','animatic/animatic-data.json']:
 path=root/rel;data=json.loads(path.read_text(encoding='utf-8'));before=edges(data)
 shutil.copy2(path,backup/rel.replace('/','__'))
 update(data);assert edges(data)==before
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
data=json.loads((root/'lead/words.json').read_text(encoding='utf-8'))
for name in ['words.csv','phrases.vtt','review.md','review.html']:shutil.copy2(root/'lead'/name,backup/name)
cols=['id','phrase_id','role','text','kind','start','end','source_start','source_end','alignment_score','status','flags']
with (root/'lead/words.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for item in data['words']:w.writerow({k:'; '.join(item[k]) if k=='flags' else item.get(k) for k in cols})
def stamp(t):
 ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
vtt=['WEBVTT','']
for p in data['phrases']:vtt += [p['id'],f"{stamp(p['start'])} --> {stamp(p['end'])}",p['text'],'']
(root/'lead/phrases.vtt').write_text('\n'.join(vtt),encoding='utf-8')
md=['# Performed lyric timing review','','User text corrections applied. Word timing remains provisional; no audio realignment or movie rendering performed.','','| Phrase | Start–end | Text | Review |','|---|---|---|---|']
for p in data['phrases']:md.append(f"| {p['id']} | {p['start']:.3f}–{p['end']:.3f} | {p['text']} | {p.get('note','')} {p.get('timing_review_note','')} |")
(root/'lead/review.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
template=Path('C:/code/github/ag-music-tool-workbench/amtw/tools/wordtiming/review.html').read_text(encoding='utf-8')
(root/'lead/review.html').write_text(template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')),encoding='utf-8')
(root/'lyric-corrections.md').write_text('# Lyric corrections\n\n- 1:43: “baby” corrected to another “play.” The passage has four play repetitions.\n- 2:12: “ah-na-na” corrected to a musical “un/un/nun…” pickup that evokes “Undone” and resolves into “Until.” Existing syllable timing/count remains provisional.\n- Separate timing issue: “Five” starts too early. Recorded on the phrase and word; exact later onset still needs measurement.\n\nApplied to performance source, word JSON/CSV/VTT/review, combined timing JSON and animatic input JSON. Raw transcription/alignment evidence and original notes retained. Existing MP4s and Blender files remain the previously rendered snapshots.\n',encoding='utf-8')
print(json.dumps({'updated':changes,'backup':str(backup),'acoustic_edges_changed':False,'rendered':False},ensure_ascii=False))

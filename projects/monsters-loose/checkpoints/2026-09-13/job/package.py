import json,pathlib,shutil,hashlib,collections,math,csv
root=pathlib.Path(r'C:\audio\shared\amtw-runtime\jobs\monsters-loose-word-timing-20260913')
master=pathlib.Path(r'C:\Users\arneg\OneDrive\Documents\Export Audio\MonstersLoose 2026-09-12 2155.wav')
shutil.copy2(master,root/'master.wav')
template=pathlib.Path('amtw/tools/wordtiming/review.html').read_text(encoding='utf8')
tracks=[];stats={};ids=set()
for role in ['lead','backing']:
 f=root/role/'words.json';d=json.loads(f.read_text());d['master_preview']='../master.wav';f.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf8')
 pf=root/f'{role}.performance.json';pd=json.loads(pf.read_text());pd['master_preview']='../master.wav';pf.write_text(json.dumps(pd,indent=2),encoding='utf8')
 (root/role/'review.html').write_text(template.replace('__DATA__',json.dumps(d,ensure_ascii=False).replace('<','\\u003c')),encoding='utf8')
 flags=collections.Counter(f for w in d['words'] for f in w['flags'])
 for w in d['words']:
  assert w['id'] not in ids;ids.add(w['id'])
  assert 0<=w['start']<w['end']<=220.387
  assert abs(w['start']-w['source_start']-d['stem_offset_seconds'])<1e-6
  assert abs(w['end']-w['source_end']-d['stem_offset_seconds'])<1e-6
 stats[role]=dict(words=len(d['words']),lyric_words=sum(w['kind']=='lyric' for w in d['words']),vocalization_syllables=sum(w['kind']=='vocalization' for w in d['words']),phrases=len(d['phrases']),unresolved_events=sum(p['kind']=='unresolved_event' for p in d['phrases']),flag_counts=dict(flags))
 tracks.append(d)
with master.open('rb') as f:masterhash=hashlib.file_digest(f,'sha256').hexdigest()
manifest=dict(schema_version=1,title='Monsters Loose vocal timing — pass 1',created='2026-09-13',timebase='master_seconds',master_audio=str(master),master_sha256=masterhash,master_duration=220.387,export_start='4.4.1.00',export_end='89.1.1.00',export_start_beat=15,export_end_beat=352,tempo_map_predicted_duration=220.39024011164474,stem_offset_seconds=.3828161236545444,lyric_source=tracks[0]['lyric_source'],review_status='Machine-reconciled first pass. Listening verification pending. Unresolved events are not confirmed words.',statistics=stats,tracks=tracks)
(root/'timing.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
(root/'validation.json').write_text(json.dumps(dict(checks=['unique IDs','positive word durations','word bounds within master','source/master offsets agree within 1 microsecond','byte-range server returned exact requested bytes'],statistics=stats),indent=2),encoding='utf8')
print(json.dumps(stats,indent=2))

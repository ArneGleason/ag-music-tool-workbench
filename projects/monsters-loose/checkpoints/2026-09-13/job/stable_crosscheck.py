import sys,json,pathlib,torch
sys.path.insert(0,r'C:\audio\shared\amtw-runtime\tools\word-timing')
import stable_whisper,whisper
p=pathlib.Path(r'C:\audio\shared\amtw-runtime\jobs\monsters-loose-word-timing-20260913')
d=json.loads((p/'lead.performance.json').read_text());source=json.loads((p/'lead/words.json').read_text())['source_audio'];audio=whisper.load_audio(source)
torch.set_num_threads(6);m=stable_whisper.load_model('large-v3-turbo',device='cuda',download_root=r'C:\Users\arneg\.cache\whisper')
results=[]
for row in d['phrases']:
 a,b=row['start'],row['end']
 r=m.align(audio[int(a*16000):int(b*16000)],row['text'],language='en',regroup=False,word_dur_factor=None,max_word_dur=None,nonspeech_skip=None,verbose=None)
 result=r.to_dict() if r else None
 if result:
  for s in result['segments']:
   s['start']+=a;s['end']+=a
   for w in s['words']:w['start']+=a;w['end']+=a
 results.append(dict(id=row['id'],result=result));print(row['id'],flush=True)
(p/'lead.stable-alignment.json').write_text(json.dumps(results,indent=2),encoding='utf8')

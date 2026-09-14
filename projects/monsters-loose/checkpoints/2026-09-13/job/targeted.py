import whisper,torch,json,pathlib
p=pathlib.Path(r'C:\audio\shared\amtw-runtime\jobs\monsters-loose-word-timing-20260913')
d=json.loads((p/'lead/words.json').read_text()); y=whisper.load_audio(d['source_audio']); torch.set_num_threads(6)
m=whisper.load_model('large-v3-turbo',device='cuda',download_root=r'C:\Users\arneg\.cache\whisper')
results=[]
for a,b in [(73,83),(130.5,140),(171,183),(194,219.48)]:
 r=m.transcribe(y[int(a*16000):int(b*16000)],language='en',word_timestamps=True,condition_on_previous_text=False,temperature=0,verbose=False)
 for s in r['segments']:
  s['start']+=a;s['end']+=a
  for w in s.get('words',[]): w['start']+=a;w['end']+=a
 print(a,b,[(s['start'],s['end'],s['text']) for s in r['segments']],flush=True)
 results.append(dict(crop_start=a,crop_end=b,result=r))
(p/'targeted-crosscheck.json').write_text(json.dumps(results,indent=2),encoding='utf8')

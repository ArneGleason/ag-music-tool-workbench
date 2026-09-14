"""Local Whisper worker. Load existing cached weights; no cloud transcription."""
import json,pathlib,subprocess,sys
import numpy as np
import torch,whisper
source,output=sys.argv[1:3]
# Bound decoding even when a WebM recording has no duration metadata.
r=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',source,'-t','181','-f','f32le','-ac','1','-ar','16000','-'],capture_output=True,check=True,timeout=45)
audio=np.frombuffer(r.stdout,dtype=np.float32).copy()
if len(audio)>int(180.5*16000):raise ValueError('Recording exceeds three minutes')
if len(audio)<1600 or float(np.sqrt(np.mean(audio**2)))<1e-5:raise ValueError('No audible speech detected')
weights=pathlib.Path.home()/'.cache/whisper/large-v3-turbo.pt'
if not weights.exists():raise FileNotFoundError('Cached Whisper turbo weights are missing')
torch.set_num_threads(6);device='cuda' if torch.cuda.is_available() else 'cpu'
model=whisper.load_model(str(weights),device=device)
result=model.transcribe(audio,language='en',fp16=device=='cuda',temperature=0,condition_on_previous_text=False,verbose=None)
text=' '.join(s['text'].strip() for s in result['segments'] if not (s.get('no_speech_prob',0)>.6 and s.get('avg_logprob',0)<-1)).strip()
if not text:raise ValueError('No speech recognized; please try again')
pathlib.Path(output).write_text(json.dumps(dict(text=text,model='Whisper large-v3-turbo',local=True,duration=len(audio)/16000)),encoding='utf-8')

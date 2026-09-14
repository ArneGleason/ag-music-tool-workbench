"""One local document, atomic revisions, recoverable history; never write source timings."""
import json,math,os,threading,time,subprocess,tempfile
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
from ..wordtiming.serve import RangeHandler
LOCK=threading.Lock()
DICTATION_LOCK=threading.Lock()
class Handler(RangeHandler):
 def reply(self,data,status=200):
  raw=json.dumps(data,ensure_ascii=False).encode('utf-8');self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def document(self):
  p=Path(self.directory)/'creative-notes.json'
  return json.loads(p.read_text(encoding='utf-8')) if p.exists() else dict(version=1,revision=0,notes=[])
 def do_GET(self):
  if urlsplit(self.path).path=='/api/assets':
   with LOCK:
    p=Path(self.directory)/'assets'/'catalog.json'
    self.reply(json.loads(p.read_text(encoding='utf-8')) if p.exists() else dict(version=1,revision=0,assets=[],scenes=[]))
  elif urlsplit(self.path).path=='/api/notes':
   with LOCK:self.reply(self.document())
  else:super().do_GET()
 def do_POST(self):
  if self.path not in ('/api/notes','/api/dictation','/api/assets'):return self.reply({'error':'Not found'},404)
  # Require same-origin JSON to prevent a remote page writing local notes.
  origin=self.headers.get('Origin');host=self.headers.get('Host','');expected='http://'+host
  if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):return self.reply({'error':'Host not allowed'},403)
  if origin and origin!=expected:return self.reply({'error':'Origin not allowed'},403)
  if self.path=='/api/dictation':return self.dictation()
  if self.path=='/api/assets':return self.asset_review()
  if self.headers.get_content_type()!='application/json':return self.reply({'error':'JSON required'},415)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=1048576:raise ValueError('Invalid request size')
   request=json.loads(self.rfile.read(length));notes=request['notes'];ids=set()
   duration=json.loads((Path(self.directory)/'timing.json').read_text(encoding='utf-8'))['master_duration']
   if not isinstance(notes,list) or len(notes)>3000:raise ValueError('Invalid notes list')
   for n in notes:
    if not isinstance(n.get('id'),str) or n['id'] in ids:raise ValueError('Duplicate or invalid note id')
    ids.add(n['id'])
    if n.get('status') not in ('open','addressed') or n.get('kind') not in ('idea','lyric','scene','other'):raise ValueError('Invalid note state')
    if not isinstance(n.get('text'),str) or not n['text'].strip() or len(n['text'])>20000:raise ValueError('Note text required')
    if not all(isinstance(n.get(k),(int,float)) and math.isfinite(n[k]) for k in ('start','end')):raise ValueError('Invalid time')
    if not 0<=n['start']<=n['end']<=duration:raise ValueError('Time outside master')
   with LOCK:
    prior=self.document()
    if request.get('revision')!=prior['revision']:return self.reply({'error':'Notes changed elsewhere. Reload saved notes before saving.','document':prior},409)
    # Addressing is a state transition, never physical deletion through this UI.
    if not {n['id'] for n in prior['notes']}.issubset(ids):raise ValueError('Notes cannot be deleted; mark addressed instead')
    root=Path(self.directory);hist=root/'note-history';hist.mkdir(exist_ok=True)
    (hist/f"revision-{prior['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(prior,indent=2,ensure_ascii=False),encoding='utf-8')
    doc=dict(version=1,revision=prior['revision']+1,notes=notes,updated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    temp=root/'creative-notes.pending.json';temp.write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf-8');os.replace(temp,root/'creative-notes.json')
    self.reply(doc)
  except (ValueError,KeyError,TypeError) as e:self.reply({'error':str(e)},400)
 def asset_review(self):
  """Review an existing immutable asset version, never accept browser file paths.

  Generation creates versions separately. Approval belongs to one version so
  replacing an image cannot silently inherit an earlier approval.
  """
  if self.headers.get_content_type()!='application/json':return self.reply({'error':'JSON required'},415)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=65536:raise ValueError('Invalid request size')
   request=json.loads(self.rfile.read(length))
   if request.get('status') not in ('awaiting_review','approved','revise','parked'):raise ValueError('Invalid review status')
   if not isinstance(request.get('review'),str) or len(request['review'])>20000:raise ValueError('Invalid review text')
   with LOCK:
    root=Path(self.directory)/'assets';path=root/'catalog.json'
    doc=json.loads(path.read_text(encoding='utf-8'))
    if request.get('revision')!=doc['revision']:return self.reply({'error':'Catalog changed elsewhere. Reload the catalog; your draft is retained.'},409)
    asset=next((a for a in doc['assets'] if a['id']==request.get('id')),None)
    if not asset or asset.get('kind')=='source':raise ValueError('Choose a generated asset to review')
    version=next((v for v in asset['versions'] if v['id']==request.get('version')),None)
    if version is None:raise ValueError('Unknown asset version')
    hist=root/'history';hist.mkdir(exist_ok=True)
    (hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    version.update(status=request['status'],review=request['review'],reviewed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    doc['revision']+=1
    temp=root/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,path)
    self.reply(doc)
  except (ValueError,KeyError,TypeError,OSError) as e:self.reply({'error':str(e)},400)
 def dictation(self):
  if self.headers.get_content_type() not in ('audio/webm','audio/ogg','audio/mp4','audio/wav','application/octet-stream'):
   return self.reply({'error':'Unsupported recording format'},415)
  try:length=int(self.headers.get('Content-Length','0'))
  except ValueError:return self.reply({'error':'Invalid recording size'},400)
  if not 0<length<=25*1024*1024:return self.reply({'error':'Recording too large; keep it under three minutes'},413)
  if not DICTATION_LOCK.acquire(blocking=False):return self.reply({'error':'Whisper is busy. Keep this recording and retry shortly.'},429)
  try:
   from ...core.paths import RUNTIME_ROOT,venv_python,subprocess_env
   scratch=RUNTIME_ROOT/'jobs'/'dictation-temp';scratch.mkdir(parents=True,exist_ok=True)
   with tempfile.TemporaryDirectory(prefix='note-',dir=scratch) as temp:
    audio=Path(temp)/'recording';result=Path(temp)/'transcript.json'
    audio.write_bytes(self.rfile.read(length))
    completed=subprocess.run([str(venv_python('vevo2')),str(Path(__file__).with_name('dictate.py')),str(audio),str(result)],env=subprocess_env(),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
    if completed.returncode:
     detail=completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else 'Transcription failed'
     return self.reply({'error':detail},422)
    self.reply(json.loads(result.read_text(encoding='utf-8')))
  except subprocess.TimeoutExpired:self.reply({'error':'Transcription timed out. Your recording can be retried.'},504)
  except (OSError,ValueError) as e:self.reply({'error':'Local transcription failed: '+str(e)},500)
  finally:DICTATION_LOCK.release()

def serve(directory,port=8742):
 root=Path(directory).resolve()
 if not (root/'timing.json').is_file():raise ValueError('Choose a timing job containing timing.json')
 page=root/'animatic'/'notes.html'
 page.parent.mkdir(exist_ok=True)
 page.write_text(Path(__file__).with_name('notes.html').read_text(encoding='utf-8'),encoding='utf-8')
 (root/'assets').mkdir(exist_ok=True)
 for name in ('assets.html','assets.js'):
  (root/'assets'/name).write_text(Path(__file__).with_name(name).read_text(encoding='utf-8'),encoding='utf-8')
 print(f'Listening notes: http://127.0.0.1:{port}/animatic/notes.html',flush=True)
 ThreadingHTTPServer(('127.0.0.1',port),partial(Handler,directory=str(root))).serve_forever()

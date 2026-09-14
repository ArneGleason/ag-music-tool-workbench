"""Exercise review persistence against a disposable copy, never approve real art."""
from pathlib import Path
from types import SimpleNamespace
from io import BytesIO
from email.message import Message
import json,shutil,sys,copy
sys.path.insert(0,'C:/code/github/ag-music-tool-workbench')
from amtw.tools.creativenotes.server import Handler
source=Path(__file__).resolve().parent
qa=source.parent/'asset-catalog-ui-check';qa.mkdir(exist_ok=True);(qa/'assets').mkdir(exist_ok=True)
shutil.copy2(source/'timing.json',qa/'timing.json')
source_bytes=(source/'assets/catalog.json').read_bytes()
doc=json.loads(source_bytes)
assert doc['assets'][0]['versions'][0]['status']=='awaiting_review'
doc['assets'][0]['versions'].append({**doc['assets'][0]['versions'][0],'id':'v002','status':'awaiting_review'})
(qa/'assets/catalog.json').write_text(json.dumps(doc),encoding='utf-8')
for a in doc['assets']:
 for v in a['versions']:shutil.copy2(source/'assets'/v['image'],qa/'assets'/v['image'])
def post(payload,origin='http://127.0.0.1:8743'):
 raw=json.dumps(payload).encode();h=object.__new__(Handler);h.directory=str(qa);h.path='/api/assets';h.server=SimpleNamespace(server_port=8743)
 h.headers=Message();h.headers['Content-Type']='application/json';h.headers['Content-Length']=str(len(raw));h.headers['Host']='127.0.0.1:8743';h.headers['Origin']=origin;h.rfile=BytesIO(raw);answer=[];h.reply=lambda data,status=200:answer.append((status,data));h.do_POST();return answer[0]
p={'revision':0,'id':'CHAR-001','version':'v001','status':'approved','review':'QA only — retain freckles and original badge.'}
code,result=post(p);assert code==200 and result['assets'][0]['versions'][0]['status']=='approved'
assert result['assets'][0]['versions'][1]['status']=='awaiting_review'
before=(qa/'assets/catalog.json').read_bytes()
assert post(p)[0]==409
assert post({**p,'revision':1,'version':'missing'})[0]==400
assert post({**p,'revision':1,'id':'SRC-001'})[0]==400
assert post({**p,'revision':1,'status':'invented'})[0]==400
assert post({**p,'revision':1},'http://foreign.example')[0]==403
assert (qa/'assets/catalog.json').read_bytes()==before
assert len(list((qa/'assets/history').glob('*.json')))>=1
assert (source/'assets/catalog.json').read_bytes()==source_bytes
print('PASS: per-version approval, history, stale revision, source/unknown/state rejection and foreign-origin rejection. QA directory:',qa)

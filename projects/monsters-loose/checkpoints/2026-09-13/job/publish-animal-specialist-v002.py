"""Add the requested character revision; run with the review server stopped."""
from pathlib import Path
import json,shutil,sys,time,hashlib,os
root=Path(__file__).resolve().parent/'assets';path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'));asset=next(a for a in doc['assets'] if a['id']=='CHAR-005')
assert not any(v['id']=='v002' for v in asset['versions'])
image=root/'CHAR-005-v002.png';assert not image.exists();shutil.copy2(sys.argv[1],image)
hist=root/'history';hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
asset['name']='Test-animal research specialist'
asset['brief']='Scientist in charge of the test animals. v002 adds a small familiar rat-monkey companion on her shoulder.'
asset['continuity']='Preserve her face, short natural curls, dark brown skin, sturdy build, ivory coat, slate-blue shirt, olive trousers and analog meter. v001 is the original without a companion. v002 adds a small gray-brown rat-monkey hybrid seated on her anatomical LEFT shoulder (image right), with rounded ears, a whiskered muzzle, grasping paws and a long curling rat tail. Keep its scale and shoulder consistent if approved.'
asset['versions'].append({'id':'v002','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':['CHAR-005 / v001'],'prompt':(root/'CHAR-005-v002-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'change_request':'Scientist in charge of test animals; a small familiar lab-rat/monkey hybrid sitting on her shoulder.'})
doc['revision']+=1;temp=root/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
print(json.dumps({'asset':'CHAR-005/v002','status':'awaiting_review','revision':doc['revision'],'image':str(image)}))


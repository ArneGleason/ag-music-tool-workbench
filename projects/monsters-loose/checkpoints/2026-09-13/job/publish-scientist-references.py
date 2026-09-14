"""Publish one candidate per scientist while the review service is stopped."""
from pathlib import Path
import json,shutil,sys,time,hashlib,os
job=Path(__file__).resolve().parent;root=job/'assets';path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'))
specs=json.loads((job/'scientist-reference-specs.json').read_text(encoding='utf-8'))
images=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
known={a['id'] for a in doc['assets']}
for spec in specs:
 assert spec['id'] not in known
 assert Path(images[spec['id']]).is_file()
 assert not (root/(spec['id']+'-v001.png')).exists()
hist=root/'history';hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
for spec in specs:
 ident=spec['id'];image=root/(ident+'-v001.png');shutil.copy2(images[ident],image)
 scenes=['SCN-004','SCN-009']
 if ident=='CHAR-004':scenes+=['SCN-010','SCN-014']
 doc['assets'].append({'id':ident,'name':spec['name'],'kind':'character','brief':('One of the three scientist concepts from the original narrative notes.' if ident!='CHAR-005' else 'Proposed fourth scientist for variety: a hands-on field biologist and containment researcher. Role and design remain open for approval.'),'continuity':spec['description'],'scene_ids':scenes,'versions':[{'id':'v001','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':['SRC-001 / v001'],'prompt':(root/(ident+'-v001-prompt.txt')).read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]})
doc['revision']+=1;temp=root/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
print(json.dumps({'added':[s['id']+'/v001' for s in specs],'revision':doc['revision'],'status':'awaiting_review'}))

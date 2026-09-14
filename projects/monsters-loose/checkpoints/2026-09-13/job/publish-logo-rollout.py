"""Publish logo revisions while the catalog server is stopped; retain all reviews."""
from pathlib import Path
import json, shutil, sys, time, hashlib, os
job=Path(__file__).resolve().parent; root=job/'assets'; path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'))
specs=json.loads((job/'logo-rollout-specs.json').read_text(encoding='utf-8'))
images=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
specs=[s for s in specs if s['id'] in images]
for s in specs:
 a=next(a for a in doc['assets'] if a['id']==s['id'])
 assert not any(v['id']==s['to'] for v in a['versions'])
 assert not (root/(s['id']+'-'+s['to']+'.png')).exists()
 assert Path(images[s['id']]).is_file()
hist=root/'history'; hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
for s in specs:
 a=next(a for a in doc['assets'] if a['id']==s['id'])
 image=root/(s['id']+'-'+s['to']+'.png'); shutil.copy2(images[s['id']],image)
 a['versions'].append({'id':s['to'],'image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image editing using approved master logo; exact model not specified by tool','source_ids':[s['id']+' / '+s['from'],'BRAND-001 / v001'],'prompt':s['prompt'],'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'change_request':'Unify existing zoo branding with approved BRAND-001/v001.'})
 a['continuity'] += ' '+s['to']+' updates visible zoo marks to approved BRAND-001/v001. Earlier versions retain old branding; use the master creature silhouette for future logo applications.'
brand=next(a for a in doc['assets'] if a['id']=='BRAND-001')
brand['brief']='Approved common M.U.C.F. creature emblem derived from CHAR-010. Logo rollout candidates are linked by source IDs in revised character and environment versions; earlier versions and historical cover remain available.'
doc['revision']+=1; temp=root/'catalog.pending.json'; temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(temp,path)
print(json.dumps({'added':[s['id']+'/'+s['to'] for s in specs],'revision':doc['revision']}))

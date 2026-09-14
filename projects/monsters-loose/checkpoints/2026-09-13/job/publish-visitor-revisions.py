"""Append immutable visitor revisions while catalog service is stopped."""
from pathlib import Path
import json, shutil, sys, time, hashlib, os
job=Path(__file__).resolve().parent
root=job/'assets'; path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'))
specs=json.loads((job/'visitor-revision-specs.json').read_text(encoding='utf-8'))
images=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for spec in specs:
 asset=next(a for a in doc['assets'] if a['id']==spec['id'])
 assert not any(v['id']=='v002' for v in asset['versions'])
 assert not (root/(spec['id']+'-v002.png')).exists()
 assert Path(images[spec['id']]).is_file()
hist=root/'history'; hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
for spec in specs:
 ident=spec['id']; asset=next(a for a in doc['assets'] if a['id']==ident)
 image=root/(ident+'-v002.png'); shutil.copy2(images[ident],image)
 asset['brief']=spec['brief']; asset['continuity']=spec['continuity']
 asset['versions'].append({'id':'v002','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image editing; exact model not specified by tool','source_ids':[ident+' / v001'],'prompt':spec['prompt'],'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'change_request':spec['brief']})
doc['revision']+=1
temp=root/'catalog.pending.json'; temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(temp,path)
print(json.dumps({'added':[s['id']+'/v002' for s in specs],'revision':doc['revision']}))

from pathlib import Path
import json, shutil, sys, time, hashlib, os
job=Path(__file__).resolve().parent;root=job/'assets';path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'));specs=json.loads((job/'scene-anchor-specs.json').read_text(encoding='utf-8'));images=json.loads((job/'scene-anchor-images.json').read_text(encoding='utf-8'))
for s in specs:
 assert not any(a['id']==s['id'] for a in doc['assets'])
 assert not (root/(s['id']+'-v001.png')).exists()
hist=root/'history';hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
for s in specs:
 image=root/(s['id']+'-v001.png');shutil.copy2(images[s['id']],image)
 doc['assets'].append({'id':s['id'],'name':s['scene']+' · '+s['name'],'kind':'scene_anchor','brief':s['body'],'continuity':'Scene mood anchor, NOT a locked shot or video start/end frame. Held across the broad scene in the animatic only to assess mood and progression. Camera, cuts, action timing and alternate locations remain open. Any illustrated lasso is provisional.','scene_ids':[s['scene']],'versions':[{'id':'v001','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':[f.removesuffix('.png') for f in s['refs']],'prompt':s['prompt'],'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]})
doc['revision']+=1;temp=root/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
print('Published anchors',doc['revision'])

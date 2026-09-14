"""Add a proposed master mark without prematurely changing scene references."""
from pathlib import Path
import json, shutil, sys, time, hashlib, os
job=Path(__file__).resolve().parent; root=job/'assets'; path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'))
assert not any(a['id']=='BRAND-001' for a in doc['assets'])
image=root/'BRAND-001-v001.png'; assert not image.exists(); shutil.copy2(sys.argv[1],image)
hist=root/'history'; hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
doc['assets'].append({'id':'BRAND-001','name':'M.U.C.F. · creature emblem','kind':'brand','brief':'Proposed common M.U.C.F. emblem derived from CHAR-010. Approve the master mark before propagating to pavement, enclosure banners, signs and uniform patches. Existing references have not yet been changed.','continuity':'Use one master silhouette consistently: broad short snout, hunched posture, long clawed arms, bent legs, simplified spine crest and curling tail. Flat near-black and ivory; bold readable M.U.C.F. lettering. This PNG is a design candidate, not a production vector. After approval, prepare reusable master artwork and adapt placement/finish rather than independently inventing new creature shapes for each surface. No legal clearance is implied.','scene_ids':[],'versions':[{'id':'v001','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation with creature reference; exact model not specified by tool','source_ids':['CHAR-010 / v001'],'prompt':(root/'BRAND-001-v001-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]})
doc['revision']+=1; temp=root/'catalog.pending.json'; temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(temp,path)
print(json.dumps({'added':'BRAND-001/v001','revision':doc['revision']}))

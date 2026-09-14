"""Add a creature candidate without changing existing references or reviews."""
from pathlib import Path
import json, shutil, sys, time, hashlib, os
job=Path(__file__).resolve().parent; root=job/'assets'; path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'))
assert not any(a['id']=='CHAR-010' for a in doc['assets'])
image=root/'CHAR-010-v001.png'; assert not image.exists()
shutil.copy2(sys.argv[1],image)
hist=root/'history'; hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
doc['assets'].append({'id':'CHAR-010','name':'Cover creature · spiny reptile','kind':'character','brief':'Full-body continuity reference extending the creature on the right of the original cover. Initial scene appearances reveal only parts of it; this reference is not a full-reveal shot. Candidate anatomy remains open for approval.','continuity':'Source anchors: broad short reptilian snout, large yellow-green eyes, pointed ivory teeth, red mouth, mottled teal/olive pebbled scales, ochre highlights, pale segmented underside, rusty pointed dorsal spines, crouched body and long clawed arms. Hidden anatomy is a proposed extension: hind legs, feet and tapering tail; digit count is proposed for repeatability rather than claimed to be established by the cover. Use this version to keep isolated eyes, jaws, claws, scales and spine silhouettes consistent after approval. Exact scale relative to Harper is not yet fixed.','scene_ids':['SCN-001'],'versions':[{'id':'v001','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation with cover reference; exact model not specified by tool','source_ids':['SRC-001 / v001'],'prompt':(root/'CHAR-010-v001-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]})
doc['revision']+=1; temp=root/'catalog.pending.json'; temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(temp,path)
print(json.dumps({'added':'CHAR-010/v001','revision':doc['revision']}))

"""Publish a stage reference with the review server stopped."""
from pathlib import Path
import json, shutil, sys, time, hashlib, os
job=Path(__file__).resolve().parent; root=job/'assets'; path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'))
assert not any(a['id']=='ENV-002' for a in doc['assets'])
image=root/'ENV-002-v001.png'; assert not image.exists(); shutil.copy2(sys.argv[1],image)
hist=root/'history'; hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
doc['assets'].append({'id':'ENV-002','name':'Central concourse · night','kind':'environment','brief':'Wide, long open zoo concourse for Harper\'s confident introduction and later action. Shared walking/service access with pedestrian branches. Flush M.U.C.F. pavement emblem provides orientation without blocking action. First candidate angle; further angles should preserve this set after approval.','continuity':'Nighttime only. Preserve distant laboratory/tower, flanking cream-concrete and black-steel enclosures, branching paths, warm industrial lamps, cool moonlight and central pavement emblem. Keep the center unobstructed. No statue or raised centerpiece. This is an empty stage reference, not a full monster reveal. Exact layout is proposed pending approval.','scene_ids':['SCN-002'],'versions':[{'id':'v001','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation with environment reference; exact model not specified by tool','source_ids':['ENV-001 / v001'],'prompt':(root/'ENV-002-v001-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]})
harper=next(a for a in doc['assets'] if a['id']=='CHAR-001')
harper['continuity'] += ' Equipment planning: lasso available when needed, optionally coiled at her hip. Not carried in every scene. Opening appearance as foreshadowing, carrying side and exact prop design remain undecided; existing reference image is unchanged.'
doc['revision']+=1; temp=root/'catalog.pending.json'; temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(temp,path)
print(json.dumps({'added':'ENV-002/v001','revision':doc['revision']}))

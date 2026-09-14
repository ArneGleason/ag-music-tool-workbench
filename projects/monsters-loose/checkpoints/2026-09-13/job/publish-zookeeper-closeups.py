"""Publish a supplemental face sheet without replacing the full-body reference.

Run while the local review server is stopped to serialize with review writes.
"""
from pathlib import Path
import json,shutil,sys,time,hashlib,os
root=Path(__file__).resolve().parent/'assets'
path=root/'catalog.json';doc=json.loads(path.read_text(encoding='utf-8'))
asset_id='CHAR-001-CU'
assert not any(a['id']==asset_id for a in doc['assets']),'Existing asset must not be replaced'
image=root/'CHAR-001-CU-v001.png';assert not image.exists()
shutil.copy2(Path(sys.argv[1]),image)
parent=next(a for a in doc['assets'] if a['id']=='CHAR-001')
hist=root/'history';hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
asset={'id':asset_id,'parent_asset_id':'CHAR-001','name':'Harper · face & singing continuity','kind':'character','brief':'Supplemental 2×2 close-up sheet: A three-quarter, B profile, C singing AH, D frontal smile. Same character as CHAR-001; the full-body reference stays separate.','continuity':'Compare all four faces against CHAR-001. Preserve freckles, eye color and shape, fringe/curl silhouette, nose, lips and jaw. Panels C and D establish a candidate shared dental baseline: natural ivory teeth, consistent incisors, spacing and dental arch. Approve the mouth/teeth appearance before using it to guide close-up shots.','scene_ids':parent.get('scene_ids',[]),'versions':[{'id':'v001','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':['CHAR-001 / v001','SRC-001 / v001'],'prompt':(root/'CHAR-001-CU-v001-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]}
doc['assets'].insert(doc['assets'].index(parent)+1,asset);doc['revision']+=1
tmp=root/'catalog.pending.json';tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,path)
print(json.dumps({'asset':asset_id,'version':'v001','status':'awaiting_review','revision':doc['revision'],'image':str(image)}))

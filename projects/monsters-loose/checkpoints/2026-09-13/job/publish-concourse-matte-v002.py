"""Add the requested character revision; run with the review server stopped."""
from pathlib import Path
import json,shutil,sys,time,hashlib,os
root=Path(__file__).resolve().parent/'assets';path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'));asset=next(a for a in doc['assets'] if a['id']=='ENV-002')
assert not any(v['id']=='v002' for v in asset['versions'])
image=root/'ENV-002-v002.png';assert not image.exists();shutil.copy2(sys.argv[1],image)
hist=root/'history';hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
asset['brief']='Wide central concourse for Harper introduction and later action. v002 replaces wet glossy paving with rough matte paving and soft diffuse illumination, keeping the center clear and the M.U.C.F. ground emblem.'
asset['continuity']='Night only. Preserve sky, laboratory/tower, enclosure fronts, vegetation, lamps, camera layout and flush M.U.C.F. emblem. v001 has wet reflective paving; v002 uses rough matte paving without long specular light streaks. Carry the matte ground direction into future angles and animation to keep attention on the action.'
asset['versions'].append({'id':'v002','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':['ENV-002 / v001'],'prompt':(root/'ENV-002-v002-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'change_request':'Matte down the concourse ground: rougher material, much less shine and no distracting elongated light reflections.'})
doc['revision']+=1;temp=root/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
print(json.dumps({'asset':'ENV-002/v002','status':'awaiting_review','revision':doc['revision'],'image':str(image)}))


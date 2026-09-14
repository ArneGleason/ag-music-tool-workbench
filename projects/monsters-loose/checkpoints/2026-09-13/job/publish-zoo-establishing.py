"""Add the environment candidate while the review server is stopped."""
from pathlib import Path
import json,shutil,sys,time,hashlib,os
job=Path(__file__).resolve().parent;root=job/'assets';path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'));assert not any(a['id']=='ENV-001' for a in doc['assets'])
image=root/'ENV-001-v001.png';assert not image.exists();shutil.copy2(Path(sys.argv[1]),image)
history=root/'history';history.mkdir(exist_ok=True)
(history/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
direction={'time_of_day':'night throughout the video','interiors':'Artificially lit interiors; practical fixtures motivate the lighting.','exteriors':'Moonlight and artificial lighting reveal environments and faces while retaining a nocturnal mood.','world':'Remote zoo and biological laboratory amid swampland, with a suggested coastal setting.','status':'User-directed nighttime rule; specific facility layout and optional helipad/road remain candidate design choices.'}
doc['visual_direction']=direction
doc['assets'].append({'id':'ENV-001','name':'Remote zoo & lab · night establishing','kind':'environment','brief':'Wide establishing reference for the remote containment zoo and laboratory in coastal swampland. Nighttime is the direction for the entire video; the architecture, causeway road and helipad are candidate layout choices.','continuity':'Keep the zoo/lab relationship, perimeter, approach road, helipad and wetland/coast geography consistent once approved. Cool readable moonlit surroundings, warm practical exterior lights, lit laboratory interiors and restrained red beacons. Delay full monster reveals.','scene_ids':['SCN-001','SCN-014'],'versions':[{'id':'v001','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':['SRC-001 / v001'],'prompt':(root/'ENV-001-v001-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]})
doc['revision']+=1;tmp=root/'catalog.pending.json';tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,path)
(root/'visual-direction.json').write_text(json.dumps(direction,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'asset':'ENV-001/v001','status':'awaiting_review','revision':doc['revision'],'path':str(image)}))

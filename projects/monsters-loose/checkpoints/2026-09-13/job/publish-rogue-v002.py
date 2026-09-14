"""Add the requested character revision; run with the review server stopped."""
from pathlib import Path
import json,shutil,sys,time,hashlib,os
root=Path(__file__).resolve().parent/'assets';path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'));asset=next(a for a in doc['assets'] if a['id']=='CHAR-004')
assert not any(v['id']=='v002' for v in asset['versions'])
image=root/'CHAR-004-v002.png';assert not image.exists();shutil.copy2(sys.argv[1],image)
hist=root/'history';hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
asset['brief']='Rogue experimenter. v002 follows the requested wilder hair, Captain Hook-inspired facial hair and retro mechanical replacement hand. Compare with v001 using the version selector.'
asset['continuity']='Same long expressive face, pale eyes, hooked nose, energetic overconfidence and rumpled lab outfit. v001 is the original clean-shaven design. v002 adds collar/shoulder-length unruly silver hair, a pointed curled mustache and goatee. In v002 his anatomical RIGHT hand (raised on image left) is mechanical: articulated steel/brass fingers and a wrist cuff. His LEFT hand holding the notebook stays human. Keep this handedness consistent if the revision is approved.'
asset['versions'].append({'id':'v002','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':['CHAR-004 / v001'],'prompt':(root/'CHAR-004-v002-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'change_request':'Longer wilder hair; Captain Hook-like mustache with goatee; one retro robotic replacement hand.'})
doc['revision']+=1;temp=root/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
print(json.dumps({'asset':'CHAR-004/v002','status':'awaiting_review','revision':doc['revision'],'image':str(image)}))

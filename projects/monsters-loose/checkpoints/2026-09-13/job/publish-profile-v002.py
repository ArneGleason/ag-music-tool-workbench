"""Add the requested character revision; run with the review server stopped."""
from pathlib import Path
import json,shutil,sys,time,hashlib,os
root=Path(__file__).resolve().parent/'assets';path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'));asset=next(a for a in doc['assets'] if a['id']=='CHAR-001-CU')
assert not any(v['id']=='v002' for v in asset['versions'])
image=root/'CHAR-001-CU-v002.png';assert not image.exists();shutil.copy2(sys.argv[1],image)
hist=root/'history';hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
# Retain the existing sheet brief.
asset['continuity'] += ' v002 corrects B so curls cover the profile ear. A, C and D are copied pixel-for-pixel from v001.'
asset['versions'].append({'id':'v002','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image editing plus deterministic panel-B compositing; exact model not specified by tool','source_ids':['CHAR-001-CU / v001'],'prompt':(root/'CHAR-001-CU-v002-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'change_request':'Cover the visible ear with curls in panel B only; preserve A, C and D exactly.'})
doc['revision']+=1;temp=root/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
print(json.dumps({'asset':'CHAR-001-CU/v002','status':'awaiting_review','revision':doc['revision'],'image':str(image)}))


"""Add the requested character revision; run with the review server stopped."""
from pathlib import Path
import json,shutil,sys,time,hashlib,os
root=Path(__file__).resolve().parent/'assets';path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'));asset=next(a for a in doc['assets'] if a['id']=='CHAR-007')
assert not any(v['id']=='v002' for v in asset['versions'])
image=root/'CHAR-007-v002.png';assert not image.exists();shutil.copy2(sys.argv[1],image)
hist=root/'history';hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
asset['brief']='Fictional state governor: formerly a used-car salesman and con man, now pursuing his wheeling and dealing inside government. v002 follows the requested short, overweight physique, unhandsome face, expensive suit and artificial hair.'
asset['continuity']='v001 is the original tall, polished candidate. v002 establishes a short squat build, generous belly, short legs, fleshy jowls, ruddy complexion and ingratiating salesman grin. Dense dark chestnut toupee contrasts with sparse gray temples. Fine navy suit, patterned gold tie, tie clip, cream pocket square and polished shoes. Preserve these proportions and artificial-hair appearance if approved; the con-man backstory is user-defined.'
asset['versions'].append({'id':'v002','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':['CHAR-007 / v001'],'prompt':(root/'CHAR-007-v002-prompt.txt').read_text(encoding='utf-8').strip(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'change_request':'Short overweight former used-car salesman turned corrupt governor; unattractive face compensated for with a nice suit and artificial hair.'})
doc['revision']+=1;temp=root/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
print(json.dumps({'asset':'CHAR-007/v002','status':'awaiting_review','revision':doc['revision'],'image':str(image)}))


"""Publish connected stage candidates with narrative source links."""
from pathlib import Path
import json, shutil, sys, time, hashlib, os
job=Path(__file__).resolve().parent; root=job/'assets'; path=root/'catalog.json'
doc=json.loads(path.read_text(encoding='utf-8'))
specs=json.loads((job/'concourse-stage-specs.json').read_text(encoding='utf-8'))
images=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for s in specs:
 assert not any(a['id']==s['id'] for a in doc['assets'])
 assert not (root/(s['id']+'-v001.png')).exists()
 assert Path(images[s['id']]).is_file()
hist=root/'history'; hist.mkdir(exist_ok=True)
(hist/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
for s in specs:
 image=root/(s['id']+'-v001.png'); shutil.copy2(images[s['id']],image)
 doc['assets'].append({'id':s['id'],'name':s['name'],'kind':'environment','brief':'Connected empty stage candidate derived from ENV-002/v003. '+s['desc'],'continuity':'Proposed extension of the concourse, awaiting spatial review; not a locked shot. Preserve matte paving, nighttime, cream concrete, black steel, warm lamps and approved creature emblem. See concourse-candidate-views.md for scene-by-scene camera ideas and unresolved locations. Validate junctions and reverse geography before final storyboards.','scene_ids':s['scenes'],'versions':[{'id':'v001','image':image.name,'status':'awaiting_review','review':'','generator':'Built-in Codex image generation with three continuity references; exact model not specified by tool','source_ids':['ENV-002 / v003','ENV-001 / v002','BRAND-001 / v001'],'prompt':s['prompt'] + ('\n\nCorrection pass: '+(root/(s['id']+'-v001-correction-prompt.txt')).read_text(encoding='utf-8') if (root/(s['id']+'-v001-correction-prompt.txt')).exists() else ''),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]})
next(a for a in doc['assets'] if a['id']=='ENV-006')['continuity'] += ' Review issue: right-side numerals still show 2 near and 3 far; reverse geography requires 3 near and 2 far. Correct before storyboards.'
doc['revision']+=1; temp=root/'catalog.pending.json'; temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); os.replace(temp,path)
print(json.dumps({'added':[s['id']+'/v001' for s in specs],'revision':doc['revision']}))


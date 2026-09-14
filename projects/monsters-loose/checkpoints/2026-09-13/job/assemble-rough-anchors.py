"""Collect independently generated scene references without changing user reviews."""
from pathlib import Path
import json, hashlib, time, os
J=Path(__file__).resolve().parent
A=J/'assets'
items=[]
for group in ('opening','middle','ending'):
    items.extend(json.loads((J/f'anchors-{group}-manifest.json').read_text(encoding='utf-8')))
items.sort(key=lambda x:x['start'])
scenes=json.loads((J/'animatic/narrative-v02.json').read_text(encoding='utf-8'))['scenes']
for n,scene in enumerate(scenes,1):
    part=[x for x in items if x['scene']==f'SCN-{n:03}']
    assert 2<=len({x['id'] for x in part})<=3,(n,len(part))
    assert abs(part[0]['start']-scene['start'])<.02,(n,'start')
    assert abs(part[-1]['end']-scene['end'])<.02,(n,'end')
    for left,right in zip(part,part[1:]):assert abs(left['end']-right['start'])<.02,(n,'gap')
for x in items:assert (A/x['image']).stat().st_size>10000,x['image']
(J/'rough-anchors-v04.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Monsters Loose — scene roughout 04','','Scene-level mood and action references; camera moves and final shot construction remain open. Two stills per scene, with three for the transformation sequence. Existing opening anchors retained. New creature designs, laboratory details and props are provisional until approved.','', '| Scene | Time | Asset | Story emphasis |','|---|---|---|---|']
for x in items:lines.append(f"| {x['scene']} | {x['start']:.2f}–{x['end']:.2f} | [{x['id']}](assets/assets.html#{x['id']}/v001) | {x['name']} |")
(J/'rough-anchors-v04.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Validated',len(items),'anchors covering',len(scenes),'scenes')

if '--publish' in __import__('sys').argv:
    # Stop the local review server first, so its in-memory revision cannot race this append.
    path=A/'catalog.json';doc=json.loads(path.read_text(encoding='utf-8'))
    (A/'history'/f"revision-{doc['revision']:06}-{time.time_ns()}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    known={x['id'] for x in doc['assets']}
    for x in items:
        if x['id'] in known:continue
        doc['assets'].append({'id':x['id'],'name':x['scene']+' · '+x['name'],'kind':'scene_anchor','brief':x['body'],'continuity':'Broad scene/action anchor, not a locked shot or video start/end frame. New creatures, props and interior details remain provisional. Approved source references govern continuity.','scene_ids':[x['scene']],'versions':[{'id':'v001','image':x['image'],'status':'awaiting_review','review':'','generator':'Built-in Codex image generation; exact model not specified by tool','source_ids':[f.removesuffix('.png') for f in x['refs']],'prompt':x['prompt'],'sha256':hashlib.sha256((A/x['image']).read_bytes()).hexdigest()}]})
        known.add(x['id'])
    doc['revision']+=1
    temp=A/'catalog.pending.json';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
    print('Published revision',doc['revision'])

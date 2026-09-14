"""Make a review copy using the existing shared note store and dictation UI."""
from pathlib import Path
import json,html
p=Path(__file__).resolve().parent
d=json.loads((p/'narrative-v02.json').read_text(encoding='utf-8'))
page=(p/'notes.html').read_text(encoding='utf-8')
page=page.replace('Monsters Loose · listening notes','Monsters Loose · narrative review / 02').replace('Monsters Loose / listening notes','Monsters Loose / narrative 02')
page=page.replace('Listen, imagine, mark. Blender remains the video rig.','Broad scenes · shared timeline notes')
page=page.replace('preview-12.5.png','narrative-preview-80.png').replace('MonstersLoose-lyric-animatic-v01.mp4?v=2','MonstersLoose-narrative-animatic-v02.mp4')
page=page.replace('height:31vh','height:auto;aspect-ratio:16/9')
# Seek into the first rendered frame, not the unsnapped source time just before it.
options=''.join(f'<option data-scene="SCN-{i+1:03}" value="{round(x["start"]*d["fps"])/d["fps"]+.001}">SCN-{i+1:03} · {html.escape(x["scene"].split(" / ",1)[-1])}</option>' for i,x in enumerate(d['scenes']))
controls='<div class="transport"><label for="storyScene">Story scene</label><select id="storyScene">'+options+'</select><a href="MonstersLoose-narrative-animatic-v02.mp4" download>MP4</a><a href="MonstersLoose-narrative-animatic-v02.blend" download>Blender project</a></div><p class="hint muted">Narrative captions are a proposed grouping of your notes. Colors mark broad scenes, not individual shots. Existing notes and dictation share the same song timeline.</p>'
page=page.replace('</video>','</video>'+controls,1)
page+='\n<script>const sceneMenu=document.querySelector("#storyScene");sceneMenu.addEventListener("change",()=>seek(Number(sceneMenu.value)));v.addEventListener("timeupdate",()=>{let i=0;for(let j=0;j<sceneMenu.options.length;j++)if(Number(sceneMenu.options[j].value)<=v.currentTime)i=j;if(document.activeElement!==sceneMenu)sceneMenu.selectedIndex=i});const requestedScene=new URLSearchParams(location.search).get("scene");if(requestedScene){const target=Array.from(sceneMenu.options).find(o=>o.dataset.scene===requestedScene);if(target){const jump=()=>{if(ready&&v.readyState>0){sceneMenu.value=target.value;seek(Number(target.value));clearInterval(waitForScene)}};const waitForScene=setInterval(jump,100);setTimeout(()=>clearInterval(waitForScene),15000);}}</script>\n'
(p/'notes-narrative.html').write_text(page,encoding='utf-8')
index=(p/'index.html').read_text(encoding='utf-8')
if 'notes-narrative.html' not in index:
 index=index.replace('<div id="jumps">','<p><a href="notes-narrative.html">NEW: timed narrative / 02 — watch and add notes</a></p><div id="jumps">')
 (p/'index.html').write_text(index,encoding='utf-8')
print('Review page created;',len(d['scenes']),'scenes;',sum(len(s['cards']) for s in d['scenes']),'captions; source revision',d['source_revision'])

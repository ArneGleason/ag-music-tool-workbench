from pathlib import Path
import json,html
root=Path(__file__).resolve().parent
items=json.loads((root.parent/'rough-anchors-v04.json').read_text(encoding='utf-8'))
page=(root/'notes-scene-anchors.html').read_text(encoding='utf-8')
page=page.replace('scene anchors / 03','scene roughout / 04').replace('scene anchors 03','scene roughout 04')
page=page.replace('MonstersLoose-scene-anchors-v03','MonstersLoose-scene-roughout-v04').replace('scene-anchors-preview-15.png','roughout-preview-15.png')
page=page.replace('Opening three scenes have mood anchors; later scenes retain narrative colors. These are not shots or video start/end frames. Existing notes and dictation share the same timeline.','All 15 scenes illustrated: two anchors per scene, three for containment transformations. These are broad scene beats for pacing review. Existing notes and dictation share the same timeline.')
options=''.join(f'<option value="{round(x["start"]*24)/24+.002}">{html.escape(x["id"]+" · "+x["name"])}</option>' for x in items)
ui='<div class="transport"><label for="anchorMenu">Anchor</label><select id="anchorMenu">'+options+'</select><a id="anchorAsset" href="../assets/assets.html#ANCH-001/v001">Review this asset</a></div>'
page=page.replace('<div class="transport"><button id="prev"',ui+'<div class="transport"><button id="prev"',1)
script='''<script>
const anchorEntries=ANCHOR_DATA;
const anchorMenu=document.querySelector('#anchorMenu'),anchorAsset=document.querySelector('#anchorAsset');
anchorMenu.addEventListener('change',()=>seek(Number(anchorMenu.value)));
function showAnchor(){let i=0;for(let j=0;j<anchorEntries.length;j++)if(Math.round(anchorEntries[j].start*24)/24<=v.currentTime+.001)i=j;const a=anchorEntries[i];if(document.activeElement!==anchorMenu)anchorMenu.selectedIndex=i;anchorAsset.href='../assets/assets.html#'+a.id+'/v001';anchorAsset.textContent='Review '+a.id;}
v.addEventListener('timeupdate',showAnchor);showAnchor();
</script>'''.replace('ANCHOR_DATA',json.dumps([{'id':x['id'],'start':x['start']} for x in items]))
page+=script
(root/'notes-roughout.html').write_text(page,encoding='utf-8')
for filename in ('notes-narrative.html','notes-scene-anchors.html'):
    p=root/filename;s=p.read_text(encoding='utf-8')
    if 'href="notes-roughout.html"' not in s:s=s.replace('<nav style=', '<nav style=',1).replace('</nav>','<a href="notes-roughout.html">Full scene roughout</a></nav>',1)
    p.write_text(s,encoding='utf-8')
print('Prepared roughout review page with',len(items),'anchor destinations')

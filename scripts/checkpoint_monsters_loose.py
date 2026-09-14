"""Make a verifiable, non-destructive recovery snapshot without audio/video payloads."""
from pathlib import Path
import hashlib,json,shutil,zipfile

REPO=Path(__file__).resolve().parents[1]
JOB=Path(r'C:\audio\shared\amtw-runtime\jobs\monsters-loose-word-timing-20260913')
DAW=Path(r'C:\Users\arneg\OneDrive\Documents\Bitwig Studio\Projects\MonstersUndone.cleaned-groove')
DEST=REPO/'projects/monsters-loose/checkpoints/2026-09-13'
allowed={'.png','.jpg','.jpeg','.webp','.svg','.blend','.json','.md','.txt','.csv','.vtt','.srt','.html','.js','.css','.py','.ps1','.ttf','.otf'}
assert not DEST.exists(), 'Checkpoint already exists; choose a new date/version, never overwrite reviews.'
files=[];excluded=[]
def copy(source,relative):
    target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
    files.append({'path':relative.as_posix(),'bytes':target.stat().st_size,'sha256':digest})
for p in sorted(JOB.rglob('*')):
    if not p.is_file():continue
    if p.suffix.lower() in allowed and '__pycache__' not in p.parts:
        assert p.stat().st_size<50*1024*1024,p
        copy(p,Path('job')/p.relative_to(JOB))
    else:excluded.append({'source':str(p),'bytes':p.stat().st_size,'reason':'Audio/video, cache, render log, or redundant autosave'})
for p in sorted(DAW.glob('*.bwproject')):copy(p,Path('bitwig')/p.name)
with zipfile.ZipFile(DAW/'MonstersLoose.dawproject') as z:
    for name in ('project.xml','metadata.xml'):
        if name in z.namelist():
            target=DEST/'bitwig/dawproject-metadata'/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(z.read(name));files.append({'path':target.relative_to(DEST).as_posix(),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    (DEST/'bitwig/dawproject-contents.json').write_text(json.dumps([{'path':i.filename,'bytes':i.file_size} for i in z.infolist()],indent=2),encoding='utf-8')
excluded.append({'source':str(DAW/'MonstersLoose.dawproject'),'bytes':(DAW/'MonstersLoose.dawproject').stat().st_size,'reason':'Large audio-bearing export; small XML metadata extracted'})
catalog=json.loads((DEST/'job/assets/catalog.json').read_text(encoding='utf-8'))
for a in catalog['assets']:
    for v in a['versions']:assert (DEST/'job/assets'/v['image']).is_file(),(a['id'],v['id'])
manifest={'source_job':str(JOB),'source_bitwig':str(DAW),'files':files,'excluded':excluded,'asset_count':len(catalog['assets']),'asset_versions':sum(len(a['versions']) for a in catalog['assets']),'bytes':sum(f['bytes'] for f in files)}
(DEST/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in manifest.items() if k not in ('files','excluded')},indent=2))

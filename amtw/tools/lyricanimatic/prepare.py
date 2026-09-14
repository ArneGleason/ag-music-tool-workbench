"""Prepare measured references; keep exact seconds separate from display frames."""
import argparse,bisect,json,math,pathlib,shutil,urllib.request,zipfile,xml.etree.ElementTree as ET
import numpy as np
import soundfile as sf

def prepare(a):
 out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
 data=json.loads(pathlib.Path(a.timing).read_text(encoding='utf-8'))
 fps=24; duration=data['master_duration']; n=math.ceil(duration*fps)
 with zipfile.ZipFile(a.dawproject) as z:r=ET.fromstring(z.read('project.xml'))
 pts=[(float(p.attrib['time']),float(p.attrib['value'])) for p in r.find('.//TempoAutomation').findall('RealPoint')]
 assert all(b[0]>a[0] for a,b in zip(pts,pts[1:]))
 def seconds(beat):
  total=0.
  for i,(b,v) in enumerate(pts):
   if b>=beat:break
   end=min(beat,pts[i+1][0] if i+1<len(pts) else beat)
   slope=(pts[i+1][1]-v)/(pts[i+1][0]-b) if i+1<len(pts) else 0
   d=end-b
   total+=60*d/v if abs(slope)<1e-9 else 60/slope*math.log((v+slope*d)/v)
  return total
 origin=seconds(data['export_start_beat'])
 beats=[dict(time=seconds(b)-origin,bar=b//4+1,beat=b%4+1,project_beat=b) for b in range(data['export_start_beat'],data['export_end_beat']+1)]
 assert abs(beats[-1]['time']-data['tempo_map_predicted_duration'])<1e-7
 envelopes={}
 for tr in data['tracks']:
  y,sr=sf.read(tr['source_audio'],always_2d=True);energy=np.mean(y*y,axis=1)
  rms=[]
  for i in range(n):
   s=max(0,round((i/fps-tr['stem_offset_seconds'])*sr));e=max(0,round(((i+1)/fps-tr['stem_offset_seconds'])*sr))
   v=float(np.sqrt(np.mean(energy[s:e]))) if e>s and s<len(energy) else 0
   rms.append(round(max(0,min(1,(20*math.log10(max(v,1e-8))+60)/60)),5))
  envelopes[tr['role']]=rms
 font=out/'BarlowSemiCondensed-SemiBold.ttf'
 for name in [font.name,'OFL.txt']:
  if not (out/name).exists():urllib.request.urlretrieve('https://raw.githubusercontent.com/google/fonts/main/ofl/barlowsemicondensed/'+name,out/name)
 master=out/'master.wav'
 if not master.exists():shutil.copy2(data['master_audio'],master)
 # Presentation timing can preview/hold words but never overwrites acoustic edges.
 payload=dict(title='MONSTERS LOOSE',fps=fps,frames=n,duration=duration,beats=beats,envelopes=envelopes,
   phrases=data['tracks'][0]['phrases'],master='master.wav',font=font.name,
   source_timing=str(pathlib.Path(a.timing).resolve()),source_dawproject=str(pathlib.Path(a.dawproject).resolve()),
   review_status=data['review_status'],palette=dict(ink='#11282d',paper='#f1dfb6',red='#ff542f',muted='#81928d'))
 (out/'animatic-data.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
 print(f'Prepared {n} frames, {len(beats)} beat boundaries, {len(payload["phrases"])} phrases.',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for k in ['timing','dawproject','out']:p.add_argument('--'+k,required=True)
 prepare(p.parse_args())

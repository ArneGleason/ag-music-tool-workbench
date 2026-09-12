"""Continuous separation, sparse restoration, full-length deliverables.

Use stereo energy for activity so opposite-polarity channels cannot cancel and
hide shaker details. The existing Apollo span policy supplies 1s pads, 3s merges;
we add 2s of inference context outside those spans and blend only inside pads.
Quiet audio is copied, not gated. All exports keep source rate and frame count.
"""
from pathlib import Path
import hashlib,json,math,time,uuid,subprocess
from ...core.paths import RUNTIME_ROOT,MODELS,MSST_DIR,venv_python

def render(source):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from ..drum_audition.audition import STEMS
    from ..run.stages.common import run_logged
    from ..run.stages.superres import _active_spans,_model_pair,_run_msst,_seg_output
    source=Path(source).resolve(); info=sf.info(source)
    if info.channels!=2: raise ValueError('This renderer expects stereo input')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    ckpt,config=MODELS/'drumsep/six.ckpt',MODELS/'drumsep/six.yaml'
    if sha(ckpt)!='d2a4aa53eb584d21eead358a4e66d1882ad182911be018f052b5da73be9096d0' or sha(config)!='17d1649a227f841165bdb4c11a42082898192a1ea3ceab7e7e0b9293d6589dd6':
        raise ValueError('DrumSep provenance mismatch')
    root=RUNTIME_ROOT/'jobs'/('drum-full-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    inputs,outputs=root/'in',root/'out'; inputs.mkdir(parents=True); outputs.mkdir()
    raw=root/'raw'; final=root/'delivery'; raw.mkdir(); final.mkdir()
    def convert(x,a,b):
        if a==b:return x
        g=math.gcd(a,b); return resample_poly(x,b//g,a//g).astype(np.float32)
    x,rate=sf.read(source,dtype='float32',always_2d=True); sr=44100
    x=convert(x,rate,sr); sf.write(inputs/'drums.wav',x,sr,subtype='FLOAT')
    print(f'Job: {root}\nSeparating full drum stem',flush=True); started=time.monotonic()
    run_logged([venv_python('msst'),MSST_DIR/'inference.py','--model_type','mdx23c','--config_path',config,'--start_check_point',ckpt,'--input_folder',inputs,'--store_dir',outputs,'--pcm_type','FLOAT'],log_path=root/'separation.log',cwd=MSST_DIR)
    parts={}
    for s in STEMS:
        y,r=sf.read(outputs/'drums'/(s+'.wav'),dtype='float32',always_2d=True)
        if r!=sr or y.shape!=x.shape or not np.isfinite(y).all(): raise ValueError('Invalid separated audio')
        parts[s]=y
    hats=parts['hh']; total=len(hats)
    # Pad a final partial detector frame rather than silently ignoring its tail.
    energy=np.sqrt(np.mean(hats**2,axis=1)); hop=round(sr*.05)
    padded=np.pad(energy,(0,(-len(energy))%hop))
    spans=[(a,min(b,total)) for a,b in _active_spans(padded,sr,-55)]
    ain,aout=root/'apollo-in',root/'apollo-out'; ain.mkdir(); aout.mkdir()
    contexts=[]
    for i,(a,b) in enumerate(spans):
        lo,hi=max(0,a-2*sr),min(total,b+2*sr)
        sf.write(ain/f'seg_{i:03d}.wav',hats[lo:hi],sr,subtype='FLOAT'); contexts.append((lo,hi))
    fraction=sum(b-a for a,b in spans)/total
    print(f'Apollo hh: {len(spans)} spans; {fraction:.1%} active including pads; quiet audio retained',flush=True)
    ac,acon,label=_model_pair('universal')
    if spans:_run_msst(ac,acon,ain,aout,root/'apollo.log')
    restored=hats.copy(); changed=np.zeros(total,dtype=bool); fade=round(.1*sr)
    for i,((a,b),(lo,hi)) in enumerate(zip(spans,contexts)):
        y,r=sf.read(_seg_output(aout,f'seg_{i:03d}'),dtype='float32',always_2d=True)
        if r!=sr or y.shape!=(hi-lo,2) or not np.isfinite(y).all(): raise ValueError('Apollo length/finite check failed')
        y=y[a-lo:b-lo]; weight=np.ones((b-a,1),np.float32); f=min(fade,(b-a)//2)
        if a>0:weight[:f,0]=np.arange(f)/f
        if b<total:weight[-f:,0]=1-np.arange(f)/f
        restored[a:b]=hats[a:b]*(1-weight)+y*weight; changed[a:b]=True
    if not np.array_equal(restored[~changed],hats[~changed]):raise ValueError('Skipped samples changed')
    labels={'kick':'Kick','snare':'Snare','toms':'Percussion','hh':'Hi-hat Shaker','ride':'Ride','crash':'Crash'}
    files={}; hashes={}
    for s in STEMS:
        # Export raw and delivery through the identical rate conversion.
        y=convert(parts[s],sr,info.samplerate)[:info.frames]
        if y.shape!=(info.frames,2):raise ValueError('Export duration mismatch')
        sf.write(raw/(labels[s]+' - untreated.wav'),y,info.samplerate,subtype='FLOAT')
        if s=='hh':y=convert(restored,sr,info.samplerate)[:info.frames]
        if not np.isfinite(y).all():raise ValueError('Nonfinite delivery')
        name=labels[s]+(' - Apollo' if s=='hh' else ' - Separated')+'.wav'
        path=final/name; sf.write(path,y,info.samplerate,subtype='FLOAT'); files[s]=str(path); hashes[s]=sha(path)
        print(path,flush=True)
    m=dict(source=str(source),source_sha256=sha(source),frames=info.frames,sample_rate=info.samplerate,
           drumsep_sha256=sha(ckpt),apollo_sha256=sha(ac),apollo_config_sha256=sha(acon),
           engine_revision=subprocess.check_output(['git','-C',str(MSST_DIR),'rev-parse','HEAD'],text=True).strip(),
           active_fraction=fraction,spans_samples=spans,contexts_samples=contexts,processing_rate=sr,
           skipped_samples_unchanged=True,files=files,hashes=hashes,seconds=time.monotonic()-started,
           method='full separation; stereo-energy -55dB activity, 1s pads/3s merge/2s context, 100ms fades; no gating')
    (root/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8');print(root/'manifest.json',flush=True)
    return root

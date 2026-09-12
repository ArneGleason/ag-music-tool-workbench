"""Restore contextual segments, not a montage with artificial joins.

Both reference and processed audio share resampling to Apollo's 48 kHz. Only
snare and hh are replaced in the recombined kit; every other part is identical.
"""
import hashlib
import json
import math
import time
from pathlib import Path
import uuid
from ...core.paths import RUNTIME_ROOT


def render(jobs):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from ..run.stages.superres import _model_pair, _run_msst, _seg_output
    from ..stem_audition.audition import metrics
    from ..drum_audition.audition import STEMS
    if not jobs:
        raise ValueError('Select at least one separation manifest')
    root=RUNTIME_ROOT/'jobs'/('drum-restore-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    inputs, outputs=root/'in',root/'out'
    inputs.mkdir(parents=True); outputs.mkdir()
    refs=[]
    def read48(path):
        x,sr=sf.read(path,dtype='float32',always_2d=True)
        if sr!=48000:
            g=math.gcd(sr,48000)
            x=resample_poly(x,48000//g,sr//g).astype(np.float32)
        if x.shape[1]!=2 or not np.isfinite(x).all():
            raise ValueError(f'Invalid stereo audio: {path}')
        return x
    for job in jobs:
        job=Path(job).resolve()
        manifest=json.loads(job.read_text(encoding='utf-8'))
        for i,e in enumerate(manifest['excerpts']):
            idx=len(refs)
            parts={s:read48(job.parent/'out'/f'seg_{i:03d}'/(s+'.wav')) for s in STEMS}
            offset=round(min(3,e['source_start'])*48000)
            n=round(manifest['duration']*48000)
            for s in ['snare','hh']:
                sf.write(inputs/f'{idx:03d}_{s}.wav',parts[s],48000,subtype='FLOAT')
            refs.append((parts,offset,n,e['source_start'],str(job)))
    ckpt,config,label=_model_pair('universal')
    print(f'Job: {root}\nApollo universal: {len(refs)*2} contextual parts',flush=True)
    t=time.monotonic()
    _run_msst(ckpt,config,inputs,outputs,root/'apollo.log')
    collections={k:[] for k in ['snare_untreated','snare_apollo','hh_untreated','hh_apollo','kit_untreated','kit_apollo','snare_difference','hh_difference']}
    diagnostics=[]; cursor=0
    for idx,(parts,offset,n,start,job) in enumerate(refs):
        dry={s:x[offset:offset+n] for s,x in parts.items()}
        wet={s:read48(_seg_output(outputs,f'{idx:03d}_{s}'))[offset:offset+n] for s in ['snare','hh']}
        if any(x.shape!=(n,2) for x in [*dry.values(),*wet.values()]):
            raise ValueError('Audio length mismatch; no silent padding allowed')
        kit=np.sum(list(dry.values()),axis=0)
        changed=kit-dry['snare']-dry['hh']+wet['snare']+wet['hh']
        values={'kit_untreated':kit,'kit_apollo':changed}
        for s in ['snare','hh']:
            values[s+'_untreated']=dry[s]; values[s+'_apollo']=wet[s]
            values[s+'_difference']=dry[s]-wet[s]
        diagnostics.append(dict(source_start=start,audition_start=cursor/48000,duration=n/48000,
                                separation_manifest=job,metrics={s:metrics(wet[s],dry[s]) for s in wet}))
        for k,v in values.items():
            collections[k].append(v)
            if idx<len(refs)-1: collections[k].append(np.zeros((48000,2),np.float32))
        cursor+=n+(48000 if idx<len(refs)-1 else 0)
    files={}; peaks={}
    for k,segments in collections.items():
        path=root/(k+'.wav'); x=np.concatenate(segments)
        if not np.isfinite(x).all(): raise ValueError('Nonfinite output')
        peaks[k]=float(np.abs(x).max())
        sf.write(path,x,48000,subtype='FLOAT'); files[k]=str(path)
        print(path,flush=True)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=dict(model=label,model_sha256=sha(ckpt),config_sha256=sha(config),sample_rate=48000,
                  frames=cursor,seconds=time.monotonic()-t,excerpts=diagnostics,files=files,peaks=peaks,
                  method='Apollo universal on contextual snare/hh; other kit parts untouched; no gate, gain matching or lag shift')
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(root/'manifest.json',flush=True)
    return root

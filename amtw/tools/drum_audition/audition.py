"""Contextual excerpts keep joins out of the evaluated drum passages.

The model's parts need not sum to the input. Keep that discrepancy audible,
not hidden by normalization or by forcing the residual into a drum class.
The original comparison shares the model's 44.1 kHz resampling path.
"""
import hashlib
import json
import math
import subprocess
import time
import uuid
from pathlib import Path
from ...core.paths import RUNTIME_ROOT, MODELS, MSST_DIR, venv_python

STEMS = ["kick", "snare", "toms", "hh", "ride", "crash"]


def render(source, starts, duration):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from ..run.stages.common import run_logged
    source = Path(source).resolve()
    info = sf.info(source)
    starts = list(map(float, starts))
    if not starts or len(starts) > 8 or not math.isfinite(duration) or not 2 <= duration <= 30:
        raise ValueError("Use 1–8 excerpts of 2–30 seconds.")
    if info.channels not in (1, 2) or any(not math.isfinite(s) or s < 0 or s+duration > info.duration for s in starts):
        raise ValueError("Excerpts must fit within a mono/stereo file.")
    ckpt, config = MODELS / "drumsep/six.ckpt", MODELS / "drumsep/six.yaml"
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(ckpt) != "d2a4aa53eb584d21eead358a4e66d1882ad182911be018f052b5da73be9096d0":
        raise ValueError("DrumSep checkpoint hash mismatch; see docs/drum-audition.md")
    if sha(config) != "17d1649a227f841165bdb4c11a42082898192a1ea3ceab7e7e0b9293d6589dd6":
        raise ValueError("DrumSep config hash mismatch; see docs/drum-audition.md")
    root = RUNTIME_ROOT / "jobs" / ("drum-audition-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    inputs, outputs = root / "in", root / "out"
    inputs.mkdir(parents=True)
    outputs.mkdir()
    sr = 44100
    count = round(duration*sr)
    refs, offsets = [], []
    for i, start in enumerate(starts):
        lo, hi = max(0, start-3), min(info.duration, start+duration+3)
        x, rate = sf.read(source, start=round(lo*info.samplerate), stop=round(hi*info.samplerate), dtype="float32", always_2d=True)
        if rate != sr:
            g = math.gcd(rate, sr)
            x = resample_poly(x, sr//g, rate//g).astype(np.float32)
        if x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        offset = round((start-lo)*sr)
        sf.write(inputs / f"seg_{i:03d}.wav", x, sr, subtype="FLOAT")
        refs.append(x[offset:offset+count]); offsets.append(offset)
    print(f"Job: {root}\nSeparating {len(starts)} contextual excerpts", flush=True)
    began = time.monotonic()
    run_logged([venv_python("msst"), MSST_DIR / "inference.py", "--model_type", "mdx23c",
                "--config_path", config, "--start_check_point", ckpt,
                "--input_folder", inputs, "--store_dir", outputs, "--pcm_type", "FLOAT"],
               log_path=root / "separation.log", cwd=MSST_DIR)
    collections = {k: [] for k in ["original", "recombined", "difference"]+STEMS}
    metrics = []
    for i, (ref, offset) in enumerate(zip(refs, offsets)):
        parts = {}
        for stem in STEMS:
            x, rate = sf.read(outputs / f"seg_{i:03d}" / f"{stem}.wav", dtype="float32", always_2d=True)
            part = x[offset:offset+count]
            if rate != sr or part.shape != ref.shape or len(part) != count or not np.isfinite(part).all():
                raise RuntimeError(f"Invalid output {i}/{stem}")
            parts[stem] = part
        summed = np.sum(list(parts.values()), axis=0)
        diff = ref-summed
        parts.update(original=ref, recombined=summed, difference=diff)
        metrics.append({"source_start": starts[i], "audition_start": i*(duration+1),
                        "difference_rms_relative_db": float(10*np.log10(max(float(np.mean(diff**2)),1e-20)/max(float(np.mean(ref**2)),1e-20)))})
        for key, part in parts.items():
            collections[key].append(part)
            if i < len(starts)-1:
                collections[key].append(np.zeros((sr,2),np.float32))
    files = {}
    for number,(key,parts) in enumerate(collections.items(),1):
        path = root / f"{number:02d}_{key}.wav"
        sf.write(path,np.concatenate(parts),sr,subtype="FLOAT")
        files[key] = str(path)
        print(path,flush=True)
    manifest = dict(source=str(source),source_sha256=sha(source),model_sha256=sha(ckpt),config_sha256=sha(config),
                    engine_revision=subprocess.check_output(["git","-C",str(MSST_DIR),"rev-parse","HEAD"],text=True).strip(),
                    sample_rate=sr,frames=len(starts)*count+(len(starts)-1)*sr,excerpts=metrics,
                    duration=duration,files=files,seconds=time.monotonic()-began,
                    method="six-stem MDX23C; 3s context; no cleanup, normalization, lag correction or sum correction")
    (root / "manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(root / "manifest.json",flush=True)
    return root

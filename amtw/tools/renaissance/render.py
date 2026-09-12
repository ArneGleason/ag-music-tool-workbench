"""Bounded-memory full-song restoration with contextual, overlapping chunks.

The audition established independent L/R Renaissance as a useful core vocal.
Keep that inference path, but overlap cores by two seconds to avoid hard joins
between model predictions. Context is excluded before blending; sum-normalized
ramps preserve unity gain even at the first/last block. Never trim silence,
stretch audio or shift individual channels to force correlation with the source.
"""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import uuid

from ...core.paths import RUNTIME_ROOT, THIRD_PARTY, MODELS


def render(source):
    import numpy as np
    import soundfile as sf
    import torch
    from scipy.signal import resample_poly
    from ..stem_audition.audition import renaissance

    source = Path(source).resolve()
    x, source_rate = sf.read(source, dtype="float32", always_2d=True)
    source_frames = len(x)
    if x.shape[1] not in (1, 2) or source_frames < source_rate:
        raise ValueError("Expected at least one second of mono or stereo audio.")
    if not np.isfinite(x).all():
        raise ValueError("Source contains non-finite samples.")
    if not torch.cuda.is_available():
        raise RuntimeError("This adapter requires CUDA.")
    sr = 48000
    if source_rate != sr:
        g = math.gcd(source_rate, sr)
        x = resample_poly(x, sr//g, source_rate//g).astype(np.float32)
    engine = THIRD_PARTY / "smule-renaissance"
    weights = MODELS / "renaissance/smule-renaissance-small.pt"
    sys.path.insert(0, str(engine))
    from model import Renaissance
    model = Renaissance().cuda().eval()
    model.load_state_dict(torch.load(weights, map_location="cuda", weights_only=True))
    root = RUNTIME_ROOT / "jobs" / ("renaissance-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    root.mkdir(parents=True)
    out = np.zeros_like(x)
    weight = np.zeros(len(x), dtype=np.float32)
    core, step, context = 12*sr, 10*sr, 2*sr
    overlap = core-step
    blocks = []
    started = time.monotonic()
    for start in range(0, len(x), step):
        end = min(start+core, len(x))
        lo, hi = max(0, start-context), min(len(x), end+context)
        restored = renaissance(x[lo:hi], model)[start-lo:end-lo]
        if restored.shape != x[start:end].shape or not np.isfinite(restored).all():
            raise RuntimeError("Invalid model output; no final file written.")
        w = np.ones(end-start, dtype=np.float32)
        if start:
            n = min(overlap, len(w))
            w[:n] *= np.linspace(0, 1, overlap, dtype=np.float32)[:n]
        if end < len(x):
            w[-overlap:] *= np.linspace(1, 0, overlap, dtype=np.float32)
        out[start:end] += restored*w[:, None]
        weight[start:end] += w
        blocks.append({"start_sample": start, "end_sample": end})
        print(f"Renaissance {end/sr:.1f}/{len(x)/sr:.1f}s", flush=True)
        if end == len(x):
            break
    if np.min(weight) <= 0:
        raise RuntimeError("Overlap coverage failed.")
    out /= weight[:, None]
    # Return to the source sample rate/count so replacing a clip cannot move
    # its end. Float WAV avoids hidden clipping or an extra quantization pass.
    if source_rate != sr:
        g = math.gcd(source_rate, sr)
        out = resample_poly(out, source_rate//g, sr//g)[:source_frames]
    if len(out) != source_frames or not np.isfinite(out).all():
        raise RuntimeError("Final sample-count/finite validation failed.")
    final = root / (source.stem + " - Renaissance.wav")
    sf.write(final, out, source_rate, subtype="FLOAT")
    info = sf.info(final)
    assert info.frames == source_frames and info.channels == x.shape[1]
    manifest = {"source": str(source), "output": str(final), "frames": source_frames,
                "sample_rate": source_rate, "channels": info.channels,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
                "model_sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
                "engine_revision": subprocess.check_output(["git", "-C", str(engine), "rev-parse", "HEAD"], text=True).strip(),
                "method": "independent L/R; shared per-context peak; 60 Hz high-pass; 12s cores/2s overlap/2s context; no gain matching",
                "seconds": time.monotonic()-started, "peak": float(abs(out).max()),
                "blocks": blocks}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(final, flush=True)
    print(root / "manifest.json", flush=True)
    return final

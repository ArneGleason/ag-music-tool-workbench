"""Audition-only restoration, with context trimmed after inference.

Renaissance's upstream runner averages stereo to mono and its iSTFT can shorten
the file. Neither is acceptable for a lockstep comparison. Keep L/R independent,
use one normalization gain, and request the exact iSTFT length. This preserves
channel count, not necessarily perceived width: record width and lag per channel
and let the listener judge. No inferred lag is silently corrected.
"""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import sys
import time
import uuid

from ...core.paths import RUNTIME_ROOT, THIRD_PARTY, MODELS


def renaissance(x, model):
    import numpy as np
    import torch
    import torchaudio
    # Shared peak avoids independently expanding quiet L/R channels. Keep the
    # upstream 60 Hz high-pass; the manifest makes this transformation explicit.
    wave = torch.from_numpy(x.T.copy()).float().cuda()
    wave = torchaudio.functional.highpass_biquad(wave, 48000, cutoff_freq=60)
    peak = wave.abs().max()
    if peak == 0:
        return np.zeros_like(x)
    wave /= peak
    window = torch.hann_window(4096, device=wave.device)
    result = []
    with torch.inference_mode():
        for channel in wave:
            spectrum = torch.stft(channel[None], 4096, 2048, 4096, window,
                                  return_complex=True, center=True)
            with torch.autocast("cuda", dtype=torch.float16):
                enhanced = model(torch.view_as_real(spectrum))
            restored = torch.istft(torch.view_as_complex(enhanced.float().contiguous()),
                                   4096, 2048, 4096, window, center=True,
                                   length=len(x))
            result.append((restored[0] * peak).cpu().numpy())
    return np.stack(result, axis=1)


def metrics(x, reference):
    import numpy as np
    from scipy.signal import correlate, correlation_lags
    lags = []
    for ch in range(x.shape[1]):
        correlation = correlate(x[:, ch], reference[:, ch], method="fft")
        lag = correlation_lags(len(x), len(reference))
        mask = abs(lag) <= 2400
        lags.append(int(lag[mask][np.argmax(correlation[mask])]))
    mid = x.mean(axis=1)
    side = (x[:, 0] - x[:, -1]) / 2
    return {"lag_samples_per_channel": lags,
            "rms_dbfs": float(10 * np.log10(np.mean(x*x) + 1e-20)),
            "side_mid_db": float(10 * np.log10((np.mean(side*side)+1e-20)/(np.mean(mid*mid)+1e-20))),
            "peak": float(abs(x).max())}


def prepare(source, starts, duration):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from ..run.stages.superres import _model_pair, _run_msst, _seg_output

    starts = [float(s) for s in starts]
    if not starts or len(starts) > 8 or not 1 <= duration <= 30:
        raise ValueError("Use 1–8 excerpts, each 1–30 seconds.")
    source = Path(source).resolve()
    info = sf.info(source)
    if any(not math.isfinite(s) or s < 0 or s + duration > info.duration for s in starts):
        raise ValueError("An excerpt falls outside the source audio.")
    engine = THIRD_PARTY / "smule-renaissance"
    weights = MODELS / "renaissance/smule-renaissance-small.pt"
    if not (engine / "model.py").exists() or not weights.exists():
        raise RuntimeError("Install Renaissance in the shared runtime; see docs/renaissance-audition.md")
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("This audition adapter currently requires CUDA.")
    root = RUNTIME_ROOT / "jobs" / ("vocal-audition-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    inputs, outputs = root / "apollo-in", root / "apollo-out"
    inputs.mkdir(parents=True)
    outputs.mkdir()
    segments = []
    sr = 48000
    for i, start in enumerate(starts):
        # Two seconds of real surrounding context, including after the excerpt,
        # keeps model boundary effects out of the portion the listener compares.
        lo, hi = max(0, start-2), min(info.duration, start+duration+2)
        x, rate = sf.read(source, start=round(lo*info.samplerate),
                          stop=round(hi*info.samplerate), dtype="float32", always_2d=True)
        if x.shape[1] not in (1, 2):
            raise ValueError("Only mono and stereo stems are supported.")
        if rate != sr:
            g = math.gcd(rate, sr)
            x = resample_poly(x, sr//g, rate//g).astype(np.float32)
        sf.write(inputs / f"seg_{i:03d}.wav", x, sr, subtype="FLOAT")
        segments.append((x, round((start-lo)*sr)))
    ckpt, config, label = _model_pair("vocal")
    print(f"Job: {root}\nApollo: {len(segments)} contextual excerpts", flush=True)
    begin = time.monotonic()
    _run_msst(ckpt, config, inputs, outputs, root / "apollo.log")
    apollo_seconds = time.monotonic()-begin
    sys.path.insert(0, str(engine))
    from model import Renaissance
    model = Renaissance().cuda().eval()
    model.load_state_dict(torch.load(weights, map_location="cuda", weights_only=True))
    variants = [[], [], [], []]
    manifest = {"source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "apollo": label, "renaissance_sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
                "renaissance_revision": subprocess.check_output(["git", "-C", str(engine), "rev-parse", "HEAD"], text=True).strip(),
                "stereo_method": "independent L/R; shared peak; 60 Hz high-pass; exact-length iSTFT",
                "sample_rate": sr, "apollo_seconds": apollo_seconds, "excerpts": []}
    begin = time.monotonic()
    for i, (x, offset) in enumerate(segments):
        print(f"Renaissance excerpt {i+1}/{len(segments)}", flush=True)
        restored = renaissance(x, model)
        apollo, rate = sf.read(_seg_output(outputs, f"seg_{i:03d}"), dtype="float32", always_2d=True)
        if rate != sr:
            g = math.gcd(rate, sr)
            apollo = resample_poly(apollo, sr//g, rate//g).astype(np.float32)
        n = round(duration*sr)
        parts = [v[offset:offset+n] for v in (x, apollo, restored)]
        if any(v.shape != (n, x.shape[1]) or not np.isfinite(v).all() for v in parts):
            raise RuntimeError("Output shape or finite-sample validation failed.")
        parts.append(parts[0]-parts[2])
        manifest["excerpts"].append({"source_start": starts[i], "audition_start": i*(duration+1),
                                     "duration": duration, "metrics": [metrics(v, parts[0]) for v in parts[:3]]})
        for collection, part in zip(variants, parts):
            collection.append(part)
            if i < len(segments)-1:
                collection.append(np.zeros((sr, x.shape[1]), dtype=np.float32))
    names = ["1_original.wav", "2_apollo.wav", "3_renaissance_LR.wav", "4_renaissance_difference.wav"]
    for name, pieces in zip(names, variants):
        sf.write(root / name, np.concatenate(pieces), sr, subtype="FLOAT")
        print(root / name, flush=True)
    manifest["renaissance_seconds"] = time.monotonic()-begin
    manifest["files"] = [str(root / name) for name in names]
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(root / "manifest.json", flush=True)
    return root

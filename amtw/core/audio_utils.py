"""Audio IO helpers shared across stages."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

PIPELINE_SR = 44100  # Apollo and seed-vc's f0 singing model both run at 44.1k


def ffmpeg_to_wav(src: Path, dst: Path, sr: int = PIPELINE_SR) -> Path:
    """Decode any input (mp3/m4a/flac/wav...) to PCM wav at the pipeline rate."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-ar", str(sr), "-acodec", "pcm_s16le", str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst


def load(path: Path) -> tuple[np.ndarray, int]:
    """Load audio as float32, shape (samples,) mono or (samples, channels)."""
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    return data, sr


def save(path: Path, data: np.ndarray, sr: int) -> Path:
    # NaN/Inf written to a PCM file turns into a constant sample value, which
    # reads back as a plausible-looking DC offset instead of an obvious
    # failure. Catch it here rather than debugging it downstream.
    if not np.all(np.isfinite(data)):
        bad = int((~np.isfinite(data)).sum())
        raise ValueError(f"refusing to write {path.name}: {bad} non-finite samples")
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, sr)
    return path


def to_mono(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return data
    return data.mean(axis=1)


def duration_seconds(path: Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate


def measure_lufs(path: Path) -> float:
    import pyloudnorm as pyln

    data, sr = load(path)
    meter = pyln.Meter(sr)
    return float(meter.integrated_loudness(data))


def resample_array(data: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """High-quality resample. Handles mono (n,) and interleaved (n, ch)."""
    if sr_in == sr_out:
        return data
    import soxr

    return soxr.resample(data, sr_in, sr_out, quality="VHQ")


def resample_file(in_path: Path, out_path: Path, target_sr: int) -> Path:
    data, sr = load(in_path)
    data = resample_array(data, sr, target_sr)
    return save(out_path, data.astype(np.float32), target_sr)


def match_lufs(in_path: Path, out_path: Path, target_lufs: float,
               target_sr: int | None = None) -> Path:
    """Gain-match to target LUFS with a hard peak guard at -0.5 dBFS.

    If target_sr is given, resample first so the peak guard applies to the
    final delivered rate (resampling can introduce small interpolation peaks).
    """
    import pyloudnorm as pyln

    data, sr = load(in_path)
    if target_sr and target_sr != sr:
        data = resample_array(data, sr, target_sr)
        sr = target_sr
    meter = pyln.Meter(sr)
    current = meter.integrated_loudness(data)
    gain_db = target_lufs - current
    gained = data * (10.0 ** (gain_db / 20.0))
    peak = np.max(np.abs(gained))
    ceiling = 10.0 ** (-0.5 / 20.0)
    if peak > ceiling:
        gained = gained * (ceiling / peak)
    return save(out_path, gained.astype(np.float32), sr)

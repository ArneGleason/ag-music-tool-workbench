"""Progress report: side-by-side spectrograms, loudness stats, and audio
players for every pipeline stage, written as a single self-contained
report.html inside the job directory. This is how we chart whether each
stage actually improved things."""
from __future__ import annotations

import html
from pathlib import Path

import numpy as np

from . import audio_utils
from .job import Job, STAGE_DIRS

STAGE_LABELS = [
    ("input", "00 · Original stem"),
    ("cleanup", "10 · De-reverb"),
    ("superres", "20 · Apollo restore"),
    ("resynth", "30 · Re-synthesis"),
    ("final", "40 · Final"),
]


def _spectrogram_png(wav: Path, png: Path, title: str) -> None:
    import librosa
    import librosa.display
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    y, sr = librosa.load(str(wav), sr=None, mono=True)
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), constrained_layout=True)

    S = librosa.amplitude_to_db(
        np.abs(librosa.stft(y, n_fft=2048, hop_length=512)), ref=np.max
    )
    librosa.display.specshow(
        S, sr=sr, hop_length=512, x_axis="time", y_axis="log", ax=axes[0],
        cmap="magma",
    )
    axes[0].set_title(f"{title} — log spectrogram", fontsize=10)

    # High-frequency zoom (4k+): where separation mush and codec artifacts live
    librosa.display.specshow(
        S, sr=sr, hop_length=512, x_axis="time", y_axis="linear", ax=axes[1],
        cmap="magma",
    )
    axes[1].set_ylim(4000, sr / 2)
    axes[1].set_title("4 kHz → Nyquist (artifact zone)", fontsize=10)

    fig.savefig(str(png), dpi=90)
    plt.close(fig)


def _stage_wav(job: Job, stage: str) -> Path | None:
    if stage == "input":
        candidates = sorted(job.dir("input").glob("*.wav"))
        return candidates[0] if candidates else None
    info = job.manifest["stages"].get(stage)
    if not info or "out" not in info:
        return None
    p = Path(info["out"])
    return p if p.exists() else None


def build(job: Job) -> Path:
    report_dir = job.dir("report")
    rows = []
    for stage, label in STAGE_LABELS:
        wav = _stage_wav(job, stage)
        if wav is None:
            continue
        png = report_dir / f"{STAGE_DIRS[stage]}.png"
        _spectrogram_png(wav, png, label)
        try:
            lufs = f"{audio_utils.measure_lufs(wav):.1f} LUFS"
        except Exception:
            lufs = "n/a"
        dur = f"{audio_utils.duration_seconds(wav):.1f}s"
        rel_wav = wav.relative_to(job.root).as_posix()
        rows.append(
            f"""
    <section>
      <h2>{html.escape(label)}</h2>
      <p class="meta">{html.escape(wav.name)} &middot; {dur} &middot; {lufs}</p>
      <audio controls preload="none" src="../{rel_wav}"></audio>
      <img src="{png.name}" alt="{html.escape(label)}">
    </section>"""
        )

    doc = f"""<!doctype html>
<meta charset="utf-8">
<title>AG Music Tool Workbench — {html.escape(job.root.name)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 1000px;
         background:#111; color:#eee; }}
  h1 {{ font-size: 1.3rem; }} h2 {{ font-size: 1.05rem; margin-bottom: .2rem; }}
  .meta {{ color:#999; font-size:.85rem; margin-top:0; }}
  img {{ width: 100%; border-radius: 6px; margin-top:.5rem; }}
  audio {{ width: 100%; }}
  section {{ margin-bottom: 2.2rem; }}
</style>
<h1>AG Music Tool Workbench — {html.escape(job.root.name)}</h1>
<p class="meta">Listen top-to-bottom; the spectrograms' lower panel zooms the 4kHz+ band where
separation artifacts and codec mush live.</p>
{''.join(rows)}
"""
    out = report_dir / "report.html"
    out.write_text(doc, encoding="utf-8")
    return out

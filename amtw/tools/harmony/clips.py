"""Short audio clips embedded straight into the map page.

The map was silent, which made it a document about music rather than a tool for
hearing it. Two kinds of clip fix that:

**Bar clips** — the actual notes, sliced from the source with its tempo map
intact, so you hear the passage as played rather than a quantised
approximation.

**Reading clips** — the *interpretation*, voiced as a plain block chord. This
is the one that matters: clicking `Gm7/C` and then `C11` on the same bar plays
two different chords built from the same sounding notes, and the difference is
the thing the whole tool is arguing about.

Clips are base64 data URIs inside the HTML rather than files beside it, so the
page stays one portable thing you can move, mail or keep — the same reason the
workbench and A/B pages have no build step.
"""
from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

import mido

from ...core.paths import subprocess_env
from . import render as R

# mono, 64 kbps: a chord clip is ~2 s and a bar ~7 s at this tempo, so the whole
# page lands well under a megabyte. Fidelity beyond this tells you nothing
# extra about a voicing.
BITRATE = "64k"


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def voice_reading(root_pc: int, quality: str, low: int = 48) -> list[int]:
    """Chord tones of a reading, stacked upward from around C3."""
    from .analysis import QUALITIES

    shape = dict(QUALITIES).get(quality)
    if not shape:
        return []
    return sorted(low + root_pc + i for i in shape)


def chord_midi(pitches: list[int], out: Path, beats: float = 3.0,
               ppq: int = 480, velocity: int = 78) -> None:
    mf = mido.MidiFile(type=1, ticks_per_beat=ppq)
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(90), time=0))
    for p in pitches:
        tr.append(mido.Message("note_on", note=p, velocity=velocity, time=0))
    dur = int(beats * ppq)
    for i, p in enumerate(pitches):
        tr.append(mido.Message("note_off", note=p, velocity=0,
                               time=dur if i == 0 else 0))
    mf.tracks.append(tr)
    mf.save(str(out))


def to_data_uri(wav: Path) -> str | None:
    """wav -> loudness-matched mp3 -> base64 data URI. None if ffmpeg fails.

    Loudness matching is not cosmetic. A block chord rendered at fixed velocity
    lands around -20 LUFS while a played bar is far louder, and A/B-ing two
    readings across a level difference measures the level, not the reading —
    the same reason the A/B tool loudness-matches by default.
    """
    mp3 = wav.with_suffix(".mp3")
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav),
         "-af", "loudnorm=I=-18:TP=-1.5:LRA=11",
         "-ac", "1", "-b:a", BITRATE, str(mp3)],
        capture_output=True, text=True, env=subprocess_env())
    if r.returncode != 0 or not mp3.exists():
        return None
    uri = "data:audio/mpeg;base64," + base64.b64encode(mp3.read_bytes()).decode()
    mp3.unlink(missing_ok=True)
    return uri


def build(src: Path, out_rows: list[dict], bar_ticks: int,
          tracks: list[int] | None, soundfont: str | None = None,
          log=print) -> tuple[int, int]:
    """Attach an `audio` data URI to each bar and each reading, in place.

    Returns (clips made, bytes of audio embedded). Silently does nothing if
    fluidsynth, a soundfont or ffmpeg is missing — a map without sound is still
    a map, and refusing to build one would be worse.
    """
    sf, exe = R.find_soundfont(soundfont), R.find_fluidsynth()
    if not (sf and exe and have_ffmpeg()):
        return 0, 0

    made = total = 0
    seen: dict[str, str] = {}          # reading name -> uri, so repeats reuse
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for row in out_rows:
            bar = row["bar"]
            mid, wav = tmp / f"b{bar}.mid", tmp / f"b{bar}.wav"
            R.write_slice(src, mid, (bar - 1) * bar_ticks, bar * bar_ticks, tracks)
            if R.render_fluidsynth(mid, wav, sf):
                uri = to_data_uri(wav)
                if uri:
                    row["audio"] = uri
                    made += 1
                    total += len(uri)

            for rd in row["readings"]:
                key = rd["name"]
                if key in seen:
                    rd["audio"] = seen[key]
                    continue
                from .analysis import PCS

                pitches = voice_reading(PCS.index(rd["root"]), rd["quality"])
                if not pitches:
                    continue
                cmid, cwav = tmp / "c.mid", tmp / "c.wav"
                chord_midi(pitches, cmid)
                if R.render_fluidsynth(cmid, cwav, sf):
                    uri = to_data_uri(cwav)
                    if uri:
                        rd["audio"] = seen[key] = uri
                        made += 1
                        total += len(uri)
            log(f"  bar {bar}: {1 if 'audio' in row else 0} bar clip, "
                f"{sum(1 for r in row['readings'] if 'audio' in r)} reading clips")
    return made, total

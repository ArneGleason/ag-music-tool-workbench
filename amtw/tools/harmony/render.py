"""Turn a bar range of MIDI into audio you can actually judge.

Two backends:

**FluidSynth + a soundfont**, when one is installed in the runtime root. This is
the one worth having — a real sampled instrument, so what you hear is the music
rather than the renderer.

**A built-in synth**, otherwise. Not a placeholder for lack of effort: a chord
tool has to make a sound on a machine with nothing installed, or the audible
third of the workflow is gated behind a download. It is a detuned-partial
electric-piano-ish tone with a long release, chosen because sustained, slightly
inharmonic chords are the easiest thing to hear voicing and tension in. It will
not pass for an instrument and is not trying to.

Tempo matters here. The reference material carries 637 tempo events swinging
35-70 bpm, so ticks are walked through the tempo map rather than assuming a
constant — rendering a rubato passage at a flat tempo would misrepresent
exactly the thing being auditioned.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import mido

from ...core import audio_utils
from ...core.paths import RUNTIME_ROOT, subprocess_env

SR = 44100
SOUNDFONT_DIR = RUNTIME_ROOT / "soundfonts"
FLUIDSYNTH_DIR = RUNTIME_ROOT / "fluidsynth"


@dataclass
class Sounding:
    start: float          # seconds
    end: float
    pitch: int
    velocity: int
    track: int


def timeline(path) -> tuple[list[Sounding], list[float], int]:
    """-> (notes in seconds, seconds at the start of each bar, bar count).

    Walks the merged tempo map so a rubato passage renders at its real speed.
    """
    mf = mido.MidiFile(str(path))
    ppq = mf.ticks_per_beat
    num, den = 4, 4
    for tr in mf.tracks:
        t = 0
        for m in tr:
            t += m.time
            if m.type == "time_signature" and t == 0:
                num, den = m.numerator, m.denominator
    bar_ticks = ppq * num * 4 // den

    # tick -> seconds over the whole tempo map
    tempo_at: list[tuple[int, int]] = []
    for tr in mf.tracks:
        t = 0
        for m in tr:
            t += m.time
            if m.type == "set_tempo":
                tempo_at.append((t, m.tempo))
    tempo_at.sort()
    if not tempo_at or tempo_at[0][0] > 0:
        tempo_at.insert(0, (0, 500_000))

    def seconds(tick: int) -> float:
        s, prev_tick, prev_tempo = 0.0, 0, tempo_at[0][1]
        for at, tempo in tempo_at:
            if at >= tick:
                break
            s += mido.tick2second(at - prev_tick, ppq, prev_tempo)
            prev_tick, prev_tempo = at, tempo
        return s + mido.tick2second(tick - prev_tick, ppq, prev_tempo)

    notes: list[Sounding] = []
    for i, tr in enumerate(mf.tracks):
        t, open_n = 0, {}
        for m in tr:
            t += m.time
            if m.type == "note_on" and m.velocity > 0:
                open_n.setdefault(m.note, []).append((t, m.velocity))
            elif m.type == "note_off" or (m.type == "note_on" and m.velocity == 0):
                if open_n.get(m.note):
                    s, vel = open_n[m.note].pop(0)
                    notes.append(Sounding(seconds(s), seconds(t), m.note, vel, i))

    last_tick = max((n for tr in mf.tracks for n in [sum(m.time for m in tr)]),
                    default=0)
    n_bars = last_tick // bar_ticks + 2
    bar_starts = [seconds(b * bar_ticks) for b in range(n_bars)]
    return notes, bar_starts, bar_ticks


# --------------------------------------------------------------------------- #
# built-in synth
# --------------------------------------------------------------------------- #

# (harmonic, gain, detune in cents). A touch of detune on the octave and the
# fifth is what stops a sustained chord sounding like an organ test tone; the
# ear reads the slow beating as "instrument" rather than "oscillator".
PARTIALS = [(1.0, 1.00, 0.0), (1.0, 0.55, 6.0), (2.0, 0.42, -4.0),
            (3.0, 0.16, 3.0), (4.0, 0.09, 0.0), (6.0, 0.04, 5.0)]


def _voice(freq: float, dur: float, vel: int) -> np.ndarray:
    """One note: detuned partial stack, percussive attack, long release."""
    n = int((dur + 1.2) * SR)                       # room for the tail
    t = np.arange(n) / SR
    out = np.zeros(n)
    for mult, gain, cents in PARTIALS:
        f = freq * mult * (2 ** (cents / 1200.0))
        if f > SR / 2.2:
            continue
        # higher partials decay faster, like a struck string
        out += gain * np.sin(2 * np.pi * f * t) * np.exp(-t * (1.1 + 0.55 * mult))

    attack = 1.0 - np.exp(-t / 0.006)
    hold = np.ones(n)
    rel_start = int(dur * SR)
    tail = np.arange(n - rel_start) / SR
    hold[rel_start:] = np.exp(-tail / 0.32)
    env = attack * hold

    sig = out * env * (0.25 + 0.75 * (vel / 127.0))
    return np.tanh(sig * 1.25) * 0.42                # soft saturation for body


def synth(notes: list[Sounding], t0: float, t1: float) -> np.ndarray:
    length = int((t1 - t0 + 1.6) * SR)
    buf = np.zeros(length)
    for nt in notes:
        if nt.end <= t0 or nt.start >= t1:
            continue
        start = max(0.0, nt.start - t0)
        dur = max(0.05, min(nt.end, t1) - max(nt.start, t0))
        v = _voice(440.0 * 2 ** ((nt.pitch - 69) / 12.0), dur, nt.velocity)
        at = int(start * SR)
        end = min(length, at + len(v))
        if end > at:
            buf[at:end] += v[:end - at]
    peak = float(np.abs(buf).max())
    if peak > 0:
        buf *= 10 ** (-1.0 / 20) / peak              # -1 dBFS
    return buf.astype(np.float32)


# --------------------------------------------------------------------------- #
# fluidsynth
# --------------------------------------------------------------------------- #


def find_fluidsynth() -> Path | None:
    on_path = shutil.which("fluidsynth")
    if on_path:
        return Path(on_path)
    for c in FLUIDSYNTH_DIR.rglob("fluidsynth.exe"):
        return c
    for c in FLUIDSYNTH_DIR.rglob("fluidsynth"):
        if c.is_file():
            return c
    return None


def find_soundfont(preferred: str | None = None) -> Path | None:
    if preferred:
        p = Path(preferred)
        if p.exists():
            return p
    if not SOUNDFONT_DIR.exists():
        return None
    fonts = sorted(list(SOUNDFONT_DIR.glob("*.sf2")) + list(SOUNDFONT_DIR.glob("*.sf3")))
    return fonts[0] if fonts else None


def render_fluidsynth(midi: Path, out: Path, soundfont: Path,
                      gain: float = 0.7) -> bool:
    exe = find_fluidsynth()
    if not exe:
        return False
    cmd = [str(exe), "-ni", "-F", str(out), "-r", str(SR), "-g", str(gain),
           str(soundfont), str(midi)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=subprocess_env())
    if r.returncode != 0 or not out.exists():
        print(r.stderr.strip()[:400] or "fluidsynth failed", file=sys.stderr)
        return False
    return True


def write_slice(src: Path, out_midi: Path, t0_tick: int, t1_tick: int) -> None:
    """A new MIDI file holding only the chosen bar span, tempo map intact."""
    mf = mido.MidiFile(str(src))
    new = mido.MidiFile(type=1, ticks_per_beat=mf.ticks_per_beat)
    for tr in mf.tracks:
        keep = mido.MidiTrack()
        t, last = 0, 0
        for m in tr:
            t += m.time
            if m.is_meta or t <= t1_tick:
                # meta (tempo, time sig) is kept from the top so the slice
                # inherits the map it was written against
                if m.is_meta or t >= t0_tick:
                    msg = m.copy(time=max(0, t - max(last, t0_tick)))
                    keep.append(msg)
                    last = max(t, t0_tick)
        new.tracks.append(keep)
    new.save(str(out_midi))


def render(src: Path, out_wav: Path, bar_lo: int, bar_hi: int,
           soundfont: str | None = None, tracks: list[int] | None = None,
           log=print) -> tuple[Path, str]:
    """-> (wav path, which backend was used)."""
    notes, bar_starts, bar_ticks = timeline(src)
    if tracks is not None:
        notes = [n for n in notes if n.track in set(tracks)]

    lo = max(1, bar_lo) - 1
    hi = min(bar_hi, len(bar_starts) - 1)
    t0 = bar_starts[lo]
    t1 = bar_starts[hi] if hi < len(bar_starts) else max(n.end for n in notes)

    sf = find_soundfont(soundfont)
    exe = find_fluidsynth()
    if sf and exe and tracks is None:
        tmp = out_wav.with_suffix(".slice.mid")
        write_slice(src, tmp, lo * bar_ticks, hi * bar_ticks)
        if render_fluidsynth(tmp, out_wav, sf):
            tmp.unlink(missing_ok=True)
            log(f"  rendered with fluidsynth + {sf.name}")
            return out_wav, f"fluidsynth ({sf.name})"
        tmp.unlink(missing_ok=True)
        log("  fluidsynth failed — falling back to the built-in synth")

    audio = synth(notes, t0, t1)
    audio_utils.save(out_wav, audio, SR)
    why = "no soundfont installed" if not sf else "fluidsynth not found"
    log(f"  rendered with the built-in synth ({why})")
    return out_wav, "built-in synth"

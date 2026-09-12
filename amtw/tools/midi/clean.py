"""Instrument-aware cleanup of a Suno per-stem MIDI export.

What the exports actually contain was measured over 200 files (85k notes) —
see docs/findings.md "What a Suno per-stem MIDI export actually contains".
The short version: no pitch bend, one velocity value, 7.7% of notes under
30 ms, thousands of same-pitch overlaps, and polyphony up to 95 voices on a
guitar. Everything here is a rule for one of those, applied in an order that
matters:

1. fold every note track into one (the two-tracks-per-instrument split that
   `midi-merge` was written for), collapsing duplicates and truncating
   same-pitch restrikes
2. tail re-detections — a flicker at the SAME pitch right after that pitch
   ended is the decay being heard as a new onset; extend the note over it
   rather than dropping it, because the instrument's tail is what the
   transcriber was actually hearing
3. other flickers (different pitch, shorter than the threshold) are dropped
4. a per-instrument voice cap, enforced as voice stealing: the oldest
   sounding note ends where the new one starts. Cap 1 is legato monophony.

Drums are different on purpose. Every hit in a drum export is a 1–2 ms
trigger — that is the convention, not a defect — so flicker removal would
delete the whole kit. Drums get only a double-trigger collapse (two hits of
the same piece inside 15 ms cannot be played) and an optional minimum length
for instruments whose envelopes need a real gate.

Instrument is inferred from the "(Name)" Suno puts in the filename and can be
overridden. All time thresholds are in milliseconds and are converted per
note through the file's tempo map, so a tempo change mid-song does not move
the goalposts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .midi import (Note, Source, merge_notes, parse_duration, read_tracks,
                   seconds_to_ticks, ticks_to_seconds, write_midi)

# --------------------------------------------------------------------------- #
# instrument profiles
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Profile:
    name: str
    voices: int           # 0 = unlimited
    drums: bool = False
    flicker_ms: float = 30.0
    tail_gap_ms: float = 100.0


PROFILES: dict[str, Profile] = {
    "lead":    Profile("lead", voices=1),
    "backing": Profile("backing", voices=4),
    "bass":    Profile("bass", voices=2),     # octave doubles are real on synth bass
    "guitar":  Profile("guitar", voices=6),
    "keys":    Profile("keys", voices=12),
    # FX stems are drum-style triggers (67 of 85 notes under 10 ms on the
    # first one measured), so they get the drum treatment, not flicker removal
    "fx":      Profile("fx", voices=0, drums=True, flicker_ms=0.0),
    "drums":   Profile("drums", voices=0, drums=True, flicker_ms=0.0),
}

# order matters: "synth bass" must hit bass before synth hits keys
_NAME_RULES: list[tuple[str, str]] = [
    (r"lead vocal", "lead"),
    (r"backing vocal", "backing"),
    (r"\bvocals?\b", "lead"),
    (r"bass", "bass"),
    (r"guitar", "guitar"),
    (r"drum|percussion|kick|snare|hi-?hat|clap|tom|cymbal|ride|crash", "drums"),
    (r"keyboard|piano|synth|brass|woodwind|strings|organ|pad", "keys"),
    (r"\bfx\b|sound effects", "fx"),
]


def infer_profile(path: Path) -> str:
    m = re.search(r"\(([^)]*)\)\s*$", path.stem)
    label = (m.group(1) if m else path.stem).lower()
    for pattern, prof in _NAME_RULES:
        if re.search(pattern, label):
            return prof
    return "keys"   # polyphonic and permissive is the safe unknown


# --------------------------------------------------------------------------- #
# alignment to the audio stem
# --------------------------------------------------------------------------- #
#
# Measured 2026-08-22: every Suno per-stem MIDI sits EARLY relative to its
# own wav by a per-song constant — 0.53 s on one song, 0.25 on another, 0.09
# on a third — identical across all the stems of a song to within ~25 ms.
# Pitch-matching confirmed it on mono stems (28% of notes on the sung pitch
# unshifted, 86% shifted). Dropped at bar 1 next to the wav in a DAW, the
# notes play ahead of the audio; this is probably most of the hand cleanup
# the exports used to need.
#
# The estimate is instrument-agnostic: cross-correlate a MIDI onset impulse
# train against the wav's onset-strength envelope and take the peak lag.
# Per-song agreement is what makes it trustworthy, so the bench tool takes
# the median across every stem it is given from the same folder.

_ALIGN_WINDOW_S = 1.5


def estimate_offset(mid: Path, wav: Path) -> tuple[float, float]:
    """Seconds to ADD to every MIDI time so onsets land on the audio, plus a
    crude prominence (peak over the 80th-percentile lag) — under ~1.5 means
    the peak was not convincing."""
    import librosa
    import numpy as np
    import soundfile as sf

    hop = 256
    y, sr = sf.read(str(wav), always_2d=True)
    y = y.mean(axis=1).astype(np.float32)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    env = env - env.mean()
    fps = sr / hop

    imp = np.zeros_like(env)
    for src in read_tracks(mid, None):
        for n in src.notes:
            i = int(round(ticks_to_seconds(n.start, src.ppq, src.tempo_map) * fps))
            if 0 <= i < len(imp):
                imp[i] += 1.0
    k = np.hanning(int(0.03 * fps) | 1)          # transcriber jitter ~10–20 ms
    imp = np.convolve(imp, k, "same")

    L = 1 << int(np.ceil(np.log2(2 * len(env))))
    cc = np.fft.irfft(np.fft.rfft(env, L) * np.conj(np.fft.rfft(imp, L)), L)
    mx = int(_ALIGN_WINDOW_S * fps)
    lags = np.concatenate([cc[-mx:], cc[:mx + 1]])
    best = int(np.argmax(lags)) - mx
    floor = np.percentile(lags, 80)
    return best / fps, float(lags.max() / (abs(floor) + 1e-9))


def shift_notes(notes: list[Note], seconds: float, ppq: int, tempo_map) -> None:
    """Move every note by `seconds`, converted through the tempo map so the
    shift is exact even where the tempo changes every beat (Suno's maps do)."""
    for n in notes:
        s = ticks_to_seconds(n.start, ppq, tempo_map) + seconds
        e = ticks_to_seconds(n.end, ppq, tempo_map) + seconds
        n.start = max(0.0, seconds_to_ticks(s, ppq, tempo_map))
        n.end = max(n.start + 1, seconds_to_ticks(e, ppq, tempo_map))


# --------------------------------------------------------------------------- #
# rules
# --------------------------------------------------------------------------- #


def _seconds(s: Source):
    def f(tick: float) -> float:
        return ticks_to_seconds(tick, s.ppq, s.tempo_map)
    return f


def extend_tails(notes: list[Note], sec, flicker_s: float, gap_s: float) -> tuple[list[Note], int]:
    """Same-pitch flicker right after the pitch ended: absorb it into the
    previous note. Returns the new list and how many were absorbed."""
    by_pitch: dict[int, list[Note]] = {}
    for n in notes:
        by_pitch.setdefault(n.pitch, []).append(n)
    out: list[Note] = []
    absorbed = 0
    for group in by_pitch.values():
        group.sort(key=lambda n: n.start)
        cur = group[0]
        for nxt in group[1:]:
            d = sec(nxt.end) - sec(nxt.start)
            lag = sec(nxt.start) - sec(cur.end)
            if d < flicker_s and 0 <= lag <= gap_s:
                cur = Note(cur.start, max(cur.end, nxt.end), cur.pitch, cur.velocity, cur.source)
                absorbed += 1
            else:
                out.append(cur)
                cur = nxt
        out.append(cur)
    out.sort(key=lambda n: (n.start, n.pitch))
    return out, absorbed


def drop_flickers(notes: list[Note], sec, flicker_s: float) -> tuple[list[Note], int]:
    kept = [n for n in notes if sec(n.end) - sec(n.start) >= flicker_s]
    return kept, len(notes) - len(kept)


def cap_voices(notes: list[Note], voices: int, gap_ticks: int) -> tuple[list[Note], int, int]:
    """Voice stealing: when an onset would exceed the cap, the oldest sounding
    note ends just before it. Cap 1 is plain legato monophony.

    A note that starts at (or within the gap of) the new onset cannot be
    shortened to make room — it would become a 1-tick stub that still counts
    as a voice. Those are simultaneous onsets the transcriber heard as a
    chord in a part that cannot play one, so the shorter of the two goes.
    Returns (notes, stolen, dropped)."""
    if voices <= 0:
        return notes, 0, 0
    notes = sorted(notes, key=lambda n: (n.start, -n.dur, n.pitch))
    sounding: list[Note] = []
    out: list[Note] = []
    stolen = dropped = 0
    for n in notes:
        sounding = [s for s in sounding if s.end > n.start]
        keep = True
        while keep and len(sounding) >= voices:
            victim = min(sounding, key=lambda s: (s.start, s.dur))
            cut = n.start - gap_ticks
            if cut > victim.start:
                victim.end = cut
                sounding.remove(victim)
                stolen += 1
            elif victim.dur >= n.dur:
                keep = False                      # the newcomer is the stub
                dropped += 1
            else:
                sounding.remove(victim)
                out.remove(victim)
                dropped += 1
        if keep:
            out.append(n)
            sounding.append(n)
    out.sort(key=lambda n: (n.start, n.pitch))
    return out, stolen, dropped


def stretch_short(notes: list[Note], sec, min_s: float, ppq: int) -> tuple[list[Note], int]:
    """Drums only: give 1 ms triggers a real gate, without crossing the next
    hit of the same piece."""
    if min_s <= 0:
        return notes, 0
    by_pitch: dict[int, list[Note]] = {}
    for n in notes:
        by_pitch.setdefault(n.pitch, []).append(n)
    changed = 0
    for group in by_pitch.values():
        group.sort(key=lambda n: n.start)
        for i, n in enumerate(group):
            if sec(n.end) - sec(n.start) >= min_s:
                continue
            # ticks per second at this note's tempo: one beat (ppq ticks) in seconds
            tps = ppq / max(1e-9, sec(n.start + ppq) - sec(n.start))
            want = n.start + int(round(min_s * tps))
            limit = group[i + 1].start - 1 if i + 1 < len(group) else want
            n.end = max(n.end, min(want, limit))
            changed += 1
    return notes, changed


# --------------------------------------------------------------------------- #
# top level
# --------------------------------------------------------------------------- #


def _max_poly(notes: list[Note]) -> int:
    ev = sorted([(n.start, 1) for n in notes] + [(n.end, -1) for n in notes],
                key=lambda e: (e[0], e[1]))
    cur = mx = 0
    for _, d in ev:
        cur += d
        mx = max(mx, cur)
    return mx


@dataclass
class Cleaned:
    notes: list[Note]
    ppq: int
    tempo_map: list[tuple[int, int]]
    ccs: list[tuple[int, int, int]]
    program: int | None
    profile: str
    stats: dict


def clean_notes(path: str | Path, profile: str | None = None,
                flicker_ms: float | None = None, tail_gap_ms: float | None = None,
                voices: int | None = None, drum_len_ms: float = 0.0,
                gap: str = "1/128", shift_s: float = 0.0) -> Cleaned:
    """The rules, without the file write — for callers that want the notes
    (the project builder). `shift_s` is applied to every note (see
    estimate_offset); the bench tool measures it per folder and passes it in."""
    path = Path(path)
    prof_name = profile or infer_profile(path)
    prof = PROFILES[prof_name]
    flicker_s = (prof.flicker_ms if flicker_ms is None else flicker_ms) / 1000.0
    tail_s = (prof.tail_gap_ms if tail_gap_ms is None else tail_gap_ms) / 1000.0
    cap = prof.voices if voices is None else voices

    sources = read_tracks(path, None)
    if not sources:
        raise ValueError(f"no note tracks in {path.name}")
    base = sources[0]
    ppq, tempo_map = base.ppq, base.tempo_map
    sec = _seconds(base)
    gap_ticks = parse_duration(gap, ppq)

    notes = [n for s in sources for n in s.notes]
    n_in, poly_in = len(notes), _max_poly(notes)
    stats = {"file": path.name, "profile": prof_name, "in": n_in, "poly_in": poly_in}

    # 1. fold tracks; duplicates collapse, same-pitch restrikes truncate.
    #    Drums collapse only inside 15 ms (a double-trigger, not a roll);
    #    pitched parts use the merge tool's 1/16 window.
    dup_ticks = parse_duration("1/16", ppq)
    if prof.drums:
        tps = ppq / max(1e-9, sec(ppq) - sec(0))
        dup_ticks = max(1, int(round(0.015 * tps)))
    notes, m = merge_notes(notes, dup_ticks, gap_ticks, 1, "max")
    stats["collapsed"] = m["collapsed"]
    stats["restrikes"] = m["truncated"]

    # 2./3. flickers
    if flicker_s > 0:
        notes, stats["tails_extended"] = extend_tails(notes, sec, flicker_s, tail_s)
        notes, stats["flickers_dropped"] = drop_flickers(notes, sec, flicker_s)
    else:
        stats["tails_extended"] = stats["flickers_dropped"] = 0

    # 4. voices
    notes, stats["voices_stolen"], stats["chord_dropped"] = cap_voices(notes, cap, gap_ticks)

    # drums: optional gate length
    if prof.drums and drum_len_ms > 0:
        notes, stats["stretched"] = stretch_short(notes, sec, drum_len_ms / 1000.0, ppq)

    if shift_s:
        shift_notes(notes, shift_s, ppq, tempo_map)
        stats["shift_s"] = round(shift_s, 3)

    for n in notes:
        n.start, n.end = int(round(n.start)), max(int(round(n.end)), int(round(n.start)) + 1)
    notes.sort(key=lambda n: (n.start, n.pitch))
    stats["out"], stats["poly_out"] = len(notes), _max_poly(notes)

    ccs = sorted({(int(round(t)), c, v) for s in sources for t, c, v in s.ccs})
    program = next((s.program for s in sources if s.program is not None), None)
    return Cleaned(notes, ppq, tempo_map, ccs, program, prof_name, stats)


def clean(path: str | Path, out: str | Path | None = None, profile: str | None = None,
          flicker_ms: float | None = None, tail_gap_ms: float | None = None,
          voices: int | None = None, drum_len_ms: float = 0.0,
          gap: str = "1/128", shift_s: float = 0.0, log=print) -> dict:
    path = Path(path)
    c = clean_notes(path, profile, flicker_ms, tail_gap_ms, voices, drum_len_ms, gap, shift_s)
    notes, stats, prof_name, n_in, poly_in = c.notes, c.stats, c.profile, c.stats["in"], c.stats["poly_in"]
    out_path = Path(out).resolve() if out else path.with_name(path.stem + ".clean.mid")
    write_midi(out_path, notes, c.ccs, c.ppq, c.tempo_map, 0, c.program, out_path.stem)
    stats["out_path"] = str(out_path)

    log(f"{path.name}  [{prof_name}]  {n_in} -> {len(notes)} notes, "
        f"poly {poly_in} -> {stats['poly_out']}  |  "
        f"{stats['collapsed']} dup, {stats['restrikes']} restrike, "
        f"{stats['tails_extended']} tail-extended, {stats['flickers_dropped']} flicker, "
        f"{stats['voices_stolen']} voice-stolen, {stats['chord_dropped']} chord-dropped"
        + (f", {stats['stretched']} stretched" if "stretched" in stats else "")
        + (f"  | shifted {shift_s:+.3f}s" if shift_s else ""))
    log(f"  -> {out_path}")
    return stats

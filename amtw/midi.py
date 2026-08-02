"""MIDI repair for stem-to-MIDI exports.

Suno's stem-to-MIDI regularly splits one instrument across two tracks — bass
notes on one, upper voicing on the other — and then, partway through a song,
starts writing the *same* notes to both. Played into one instrument that
double-triggers and overloads it.

`merge()` folds any number of tracks into one where no two notes of the same
pitch ever overlap:

  * two notes of the same pitch starting within `dup` of each other are one
    note heard twice -> collapsed, longest tail wins
  * a later note starting more than `dup` after an overlapping held note is a
    real restrike -> the held note is truncated to end `gap` before it, and any
    tail it had beyond the new note's end is donated to the new note

Suno also writes illegal key signatures ("14 sharps") that make standard MIDI
parsers hard-fail, so the reader patches mido to tolerate them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import mido
from mido.midifiles.meta import MetaSpec_key_signature, add_meta_spec

DEFAULT_TEMPO = 500_000  # µs per beat == 120 bpm, the MIDI default

VELOCITY_POLICIES = ["max", "min", "first", "avg", "longest"]


def _install_tolerant_key_signature() -> None:
    class TolerantKeySignature(MetaSpec_key_signature):
        def decode(self, message, data):
            try:
                super().decode(message, data)
            except Exception:  # noqa: BLE001 - any malformed key becomes C
                message.key = "C"

    add_meta_spec(TolerantKeySignature)


_install_tolerant_key_signature()


@dataclass
class Note:
    start: float
    end: float
    pitch: int
    velocity: int
    source: int

    @property
    def dur(self) -> float:
        return self.end - self.start


@dataclass
class Source:
    label: str
    notes: list[Note] = field(default_factory=list)
    ccs: list[tuple[float, int, int]] = field(default_factory=list)
    ppq: int = 480
    tempo_map: list[tuple[int, int]] = field(default_factory=list)
    program: int | None = None


def parse_duration(text: str | float, ppq: int) -> int:
    """'1/16' (a sixteenth note) | '0.25' (beats) | '48t' (raw ticks) -> ticks."""
    text = str(text).strip().lower()
    if text.endswith("t"):
        return int(round(float(text[:-1])))
    beats = Fraction(text) * 4 if "/" in text else Fraction(text)
    return int(round(float(beats) * ppq))


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #


def describe(path: str | Path) -> dict:
    """Track listing for a MIDI file, for pickers and `--inspect`."""
    mf = mido.MidiFile(str(path))
    tracks = []
    for idx, track in enumerate(mf.tracks):
        t = 0
        starts: list[int] = []
        pitches: list[int] = []
        tempos = 0
        for msg in track:
            t += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                starts.append(t)
                pitches.append(msg.note)
            elif msg.type == "set_tempo":
                tempos += 1
        tracks.append({
            "index": idx,
            "name": track.name or "",
            "notes": len(pitches),
            "low": min(pitches) if pitches else None,
            "high": max(pitches) if pitches else None,
            "first_tick": starts[0] if starts else None,
            "last_tick": starts[-1] if starts else None,
            "tempo_events": tempos,
        })
    return {
        "path": str(path),
        "type": mf.type,
        "ppq": mf.ticks_per_beat,
        "length": mf.length,
        "tracks": tracks,
    }


def read_tracks(path: str | Path, wanted: list[int] | None) -> list[Source]:
    mf = mido.MidiFile(str(path))

    # the tempo map is file-global in a type-1 file: gather it from every track
    tempo_map: list[tuple[int, int]] = []
    for track in mf.tracks:
        t = 0
        for msg in track:
            t += msg.time
            if msg.type == "set_tempo":
                tempo_map.append((t, msg.tempo))
    tempo_map.sort()
    if not tempo_map or tempo_map[0][0] != 0:
        tempo_map.insert(0, (0, DEFAULT_TEMPO))

    sources: list[Source] = []
    for idx, track in enumerate(mf.tracks):
        if wanted is not None and idx not in wanted:
            continue

        t = 0
        pending: dict[int, list[tuple[int, int]]] = {}
        notes: list[Note] = []
        ccs: list[tuple[float, int, int]] = []
        program: int | None = None

        for msg in track:
            t += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                pending.setdefault(msg.note, []).append((t, msg.velocity))
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                stack = pending.get(msg.note)
                if stack:
                    start, vel = stack.pop(0)
                    if t > start:
                        notes.append(Note(start, t, msg.note, vel, idx))
            elif msg.type == "control_change":
                ccs.append((t, msg.control, msg.value))
            elif msg.type == "program_change" and program is None:
                program = msg.program

        for pitch, stack in pending.items():  # never-released notes run to the end
            for start, vel in stack:
                notes.append(Note(start, max(t, start + 1), pitch, vel, idx))

        if wanted is None and not notes:
            continue  # skip meta-only tracks when auto-selecting

        notes.sort(key=lambda n: (n.start, n.pitch))
        label = f"{Path(path).name}#{idx}" + (f" ({track.name})" if track.name else "")
        sources.append(Source(label, notes, ccs, mf.ticks_per_beat, tempo_map, program))

    return sources


def ticks_to_seconds(tick: float, ppq: int, tempo_map: list[tuple[int, int]]) -> float:
    secs = 0.0
    prev_tick, prev_tempo = tempo_map[0]
    for change_tick, tempo in tempo_map[1:]:
        if change_tick >= tick:
            break
        secs += (change_tick - prev_tick) / ppq * (prev_tempo / 1e6)
        prev_tick, prev_tempo = change_tick, tempo
    return secs + (tick - prev_tick) / ppq * (prev_tempo / 1e6)


# --------------------------------------------------------------------------- #
# merging
# --------------------------------------------------------------------------- #


def pick_velocity(a: Note, b: Note, policy: str) -> int:
    if policy == "max":
        return max(a.velocity, b.velocity)
    if policy == "min":
        return min(a.velocity, b.velocity)
    if policy == "first":
        return a.velocity
    if policy == "avg":
        return (a.velocity + b.velocity) // 2
    if policy == "longest":
        return a.velocity if a.dur >= b.dur else b.velocity
    raise ValueError(f"unknown velocity policy: {policy}")


def merge_notes(notes: list[Note], dup: int, gap: int, min_len: int,
                velocity: str) -> tuple[list[Note], dict[str, int]]:
    stats = {"in": len(notes), "collapsed": 0, "truncated": 0, "dropped": 0}
    by_pitch: dict[int, list[Note]] = {}
    for n in notes:
        by_pitch.setdefault(n.pitch, []).append(n)

    out: list[Note] = []
    for pitch, group in by_pitch.items():
        # longest first at equal starts, so the held note absorbs the stab
        group.sort(key=lambda n: (n.start, -n.dur))
        cur = group[0]
        for nxt in group[1:]:
            if nxt.start >= cur.end:
                out.append(cur)
                cur = nxt
                continue

            if nxt.start - cur.start <= dup:
                # the same note heard twice
                cur = Note(cur.start, max(cur.end, nxt.end), pitch,
                           pick_velocity(cur, nxt, velocity), cur.source)
                stats["collapsed"] += 1
            else:
                # a real restrike: truncate the held note, donate its tail
                old_end = cur.end
                cur = Note(cur.start, nxt.start - gap, pitch, cur.velocity, cur.source)
                stats["truncated"] += 1
                if old_end > nxt.end:
                    nxt = Note(nxt.start, old_end, pitch, nxt.velocity, nxt.source)
                if cur.dur >= min_len:
                    out.append(cur)
                else:
                    stats["dropped"] += 1
                cur = nxt
        if cur.dur >= min_len:
            out.append(cur)
        else:
            stats["dropped"] += 1

    out.sort(key=lambda n: (n.start, n.pitch))
    stats["out"] = len(out)
    return out, stats


# --------------------------------------------------------------------------- #
# writing
# --------------------------------------------------------------------------- #


def write_midi(path: Path, notes: list[Note], ccs: list[tuple[int, int, int]],
               ppq: int, tempo_map: list[tuple[int, int]], channel: int,
               program: int | None, name: str) -> None:
    mf = mido.MidiFile(type=1, ticks_per_beat=ppq)

    meta = mido.MidiTrack()
    meta.name = name
    last = 0
    for tick, tempo in tempo_map:
        meta.append(mido.MetaMessage("set_tempo", tempo=tempo, time=int(tick) - last))
        last = int(tick)
    mf.tracks.append(meta)

    track = mido.MidiTrack()
    track.name = name
    if program is not None:
        track.append(mido.Message("program_change", channel=channel, program=program, time=0))

    events: list[tuple[int, int, mido.Message]] = []  # (tick, order) — note_off first
    for n in notes:
        events.append((int(n.start), 1, mido.Message(
            "note_on", channel=channel, note=n.pitch, velocity=int(n.velocity), time=0)))
        events.append((int(n.end), 0, mido.Message(
            "note_off", channel=channel, note=n.pitch, velocity=0, time=0)))
    for tick, control, value in ccs:
        events.append((int(tick), 0, mido.Message(
            "control_change", channel=channel, control=control, value=value, time=0)))
    events.sort(key=lambda e: (e[0], e[1]))

    last = 0
    for tick, _order, msg in events:
        msg.time = tick - last
        track.append(msg)
        last = tick
    mf.tracks.append(track)

    path.parent.mkdir(parents=True, exist_ok=True)
    mf.save(str(path))


# --------------------------------------------------------------------------- #
# top level
# --------------------------------------------------------------------------- #


def merge(inputs: list[str | Path], out: str | Path | None = None,
          tracks: list[int] | None = None, dup: str = "1/16", gap: str = "1/128",
          min_len: str = "1/64", velocity: str = "max", align: str = "auto",
          bpm: float | None = None, ppq: int | None = None, channel: int = 0,
          keep_cc: bool = True, log=print) -> dict:
    """Merge tracks from one or more MIDI files into a single clean track."""
    sources: list[Source] = []
    for path in inputs:
        wanted = tracks if (len(inputs) == 1 and tracks) else None
        sources.extend(read_tracks(path, wanted))
    if not sources:
        raise ValueError("no note tracks found in the input")

    ppq = ppq or sources[0].ppq
    if align == "auto":
        same_grid = (len({tuple(s.tempo_map) for s in sources}) == 1
                     and len({s.ppq for s in sources}) == 1)
        align = "ticks" if same_grid else "time"
        if align == "time":
            log("! sources disagree on tempo map or ppq — aligning in seconds instead "
                "of ticks (tick positions would not mean the same moment)")

    if align == "ticks":
        out_tempo_map = [(int(t * ppq / sources[0].ppq), v) for t, v in sources[0].tempo_map]
        for s in sources:
            scale = ppq / s.ppq
            for n in s.notes:
                n.start *= scale
                n.end *= scale
            s.ccs = [(t * scale, c, v) for t, c, v in s.ccs]
    else:
        bpm = bpm or (60_000_000 / sources[0].tempo_map[0][1])
        tps = ppq * bpm / 60.0  # output ticks per second
        out_tempo_map = [(0, int(round(60_000_000 / bpm)))]
        for s in sources:
            for n in s.notes:
                n.start = ticks_to_seconds(n.start, s.ppq, s.tempo_map) * tps
                n.end = ticks_to_seconds(n.end, s.ppq, s.tempo_map) * tps
            s.ccs = [(ticks_to_seconds(t, s.ppq, s.tempo_map) * tps, c, v) for t, c, v in s.ccs]

    dup_t = parse_duration(dup, ppq)
    gap_t = parse_duration(gap, ppq)
    min_t = parse_duration(min_len, ppq)

    all_notes = [n for s in sources for n in s.notes]
    for n in all_notes:
        n.start = int(round(n.start))
        n.end = max(int(round(n.end)), int(n.start) + 1)
    merged, stats = merge_notes(all_notes, dup_t, gap_t, min_t, velocity)

    ccs: list[tuple[int, int, int]] = []
    if keep_cc:
        seen = set()
        for s in sources:
            for t, c, v in s.ccs:
                key = (int(round(t)), c, v)
                if key not in seen:
                    seen.add(key)
                    ccs.append(key)
        ccs.sort()

    out_path = Path(out).resolve() if out else \
        Path(inputs[0]).resolve().with_suffix("").with_name(
            Path(inputs[0]).stem + ".merged.mid")
    program = next((s.program for s in sources if s.program is not None), None)
    write_midi(out_path, merged, ccs, ppq, out_tempo_map, channel, program, out_path.stem)

    log(f"sources ({align}-aligned, ppq {ppq}):")
    for s in sources:
        log(f"  {len(s.notes):5d} notes  {s.label}")
    log(f"merged: {stats['in']} -> {stats['out']} notes  "
        f"({stats['collapsed']} collapsed as duplicates, "
        f"{stats['truncated']} truncated at a restrike, "
        f"{stats['dropped']} dropped as too short)")
    log(f"wrote {out_path}")

    stats["out_path"] = str(out_path)
    return stats

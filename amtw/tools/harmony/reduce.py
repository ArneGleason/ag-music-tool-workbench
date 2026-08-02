"""Reduce a block of chords to one monophonic line.

The inverse of how this user writes. Chords get built by stacking independent
lines; this pulls one line back out, so a progression can be re-recorded,
re-voiced or handed to an instrument that only plays one note at a time.

The interesting mode is `smooth`. Taking the top note of every chord is easy
and often lands on a jumpy line that nobody would have played. Choosing, at
each chord, the note nearest the one before it produces a line that moves the
way a player moves — and because it is picked per chord rather than per voice,
it will happily cross between "voices" when that is the shorter path, which is
usually what an ear wants and a voice-leading rule forbids.

Nothing here quantises or repairs timing: onsets come from the source, so a
rubato passage reduces to a line with the same rubato.
"""
from __future__ import annotations

from dataclasses import dataclass

MODES = ["top", "bottom", "smooth", "nth"]


@dataclass
class Pick:
    start: float          # in the source's own tick domain
    end: float
    pitch: int
    velocity: int
    n_sounding: int       # how many notes were sounding here (1 = already mono)


def segments(notes: list[tuple[float, float, int, int]]) -> list[tuple[float, float, list]]:
    """Split into spans where the set of sounding notes does not change.

    Boundaries are every onset AND every release: a chord that loses a note
    without gaining one is a different chord, and reducing across that boundary
    would hold a pitch that has stopped sounding underneath.
    """
    if not notes:
        return []
    edges = sorted({t for s, e, _, _ in notes for t in (s, e)})
    out = []
    for a, b in zip(edges, edges[1:]):
        if b <= a:
            continue
        live = [(p, v) for s, e, p, v in notes if s <= a and e > a]
        if live:
            out.append((a, b, sorted(live)))
    return out


def reduce_line(notes: list[tuple[float, float, int, int]], mode: str = "top",
                index: int = 1, min_len: float = 0.0) -> list[Pick]:
    """notes = [(start, end, pitch, velocity)] -> one pick per segment."""
    segs = segments(notes)
    picks: list[Pick] = []
    prev: int | None = None

    for a, b, live in segs:
        pitches = [p for p, _ in live]
        if mode == "top":
            chosen = pitches[-1]
        elif mode == "bottom":
            chosen = pitches[0]
        elif mode == "nth":
            i = max(1, index)
            chosen = pitches[-i] if i <= len(pitches) else pitches[0]
        else:                                    # smooth
            chosen = (pitches[-1] if prev is None
                      else min(pitches, key=lambda p: (abs(p - prev), -p)))
        vel = next(v for p, v in live if p == chosen)
        picks.append(Pick(a, b, chosen, vel, len(live)))
        prev = chosen

    # merge neighbouring segments that chose the same pitch, so a note held
    # under a changing chord stays one note instead of being re-struck
    merged: list[Pick] = []
    for p in picks:
        if merged and merged[-1].pitch == p.pitch and merged[-1].end >= p.start:
            merged[-1].end = p.end
            merged[-1].n_sounding = max(merged[-1].n_sounding, p.n_sounding)
        else:
            merged.append(p)

    if min_len > 0:
        merged = [p for p in merged if p.end - p.start >= min_len]
    return merged


def describe(picks: list[Pick]) -> dict:
    if not picks:
        return {"notes": 0}
    leaps = [abs(b.pitch - a.pitch) for a, b in zip(picks, picks[1:])]
    return {
        "notes": len(picks),
        "range": (min(p.pitch for p in picks), max(p.pitch for p in picks)),
        "biggest_leap": max(leaps) if leaps else 0,
        "mean_leap": round(sum(leaps) / len(leaps), 2) if leaps else 0.0,
        "steps_or_less": sum(1 for l in leaps if l <= 2),
        "total_moves": len(leaps),
    }

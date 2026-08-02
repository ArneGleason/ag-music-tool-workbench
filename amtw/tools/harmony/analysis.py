"""Harmonic analysis of independent lines.

Every chord tool on the market answers "what chord comes next". This answers
the opposite question: *what did these lines just make, and what is it still
free to become*. That inversion is the whole point — the user writes one line,
then a second, then a third, and the chords are a consequence rather than an
input.

Two consequences for the design:

**Tracks are voices, not a pile of notes.** A MIDI track is a line with a name,
and the interesting question is usually "which line is doing this to me" —
so `narrowing_voices()` reports, per bar, which single voice is responsible for
killing a key that would otherwise still fit. That is the thing you cannot see
by looking at a chord symbol.

**The output is a distribution, not an answer.** "The key is C" is the wrong
shape of answer for music that deliberately refuses to confirm a key. So
`key_fits()` returns every major collection that contains the bar, and the
*width* of that set is the useful number. On the reference material (an 8-bar
loop) the width swings from 2 to 5, and bars 1 and 8 share no key at all.

Note on modes: a mode is its parent collection, so C Mixolydian shows up here
as "F major fits". Pass a tonic to `modal_name()` to read it back that way.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import mido

# Importing the merge tool's reader installs its tolerant key-signature patch.
# Suno writes illegal key signatures ("14 sharps") that make mido hard-fail,
# and the same files land here. See docs/findings.md.
from ..midi import midi as _midi_reader  # noqa: F401

PCS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MAJOR = (0, 2, 4, 5, 7, 9, 11)
MODES = ["Ionian", "Dorian", "Phrygian", "Lydian", "Mixolydian", "Aeolian", "Locrian"]

# Circle-of-fifths order, so a printed ribbon reads flat-side to sharp-side and
# a modulation looks like movement rather than a reshuffle.
KEY_ORDER = ["Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#"]


def pc(name: str) -> int:
    """'Bb' / 'A#' / 'b' -> pitch class."""
    n = name.strip().capitalize()
    alias = {"A#": "Bb", "C#": "C#", "D#": "Eb", "F#": "F#", "G#": "Ab",
             "Db": "C#", "Gb": "F#"}
    n = alias.get(n, n)
    if n not in PCS:
        raise ValueError(f"unknown pitch name: {name!r}")
    return PCS.index(n)


def collection(tonic: str) -> set[int]:
    return {(pc(tonic) + i) % 12 for i in MAJOR}


@dataclass
class Note:
    start: int
    end: int
    pitch: int

    @property
    def klass(self) -> int:
        return self.pitch % 12


@dataclass
class Voice:
    index: int
    name: str
    notes: list[Note] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.name or f"track {self.index}"


@dataclass
class Bar:
    number: int                       # 1-based, as the DAW shows it
    voices: dict[int, list[Note]]     # voice index -> notes sounding in this bar

    @property
    def notes(self) -> list[Note]:
        return [n for ns in self.voices.values() for n in ns]

    @property
    def pcs(self) -> set[int]:
        return {n.klass for n in self.notes}

    @property
    def bass(self) -> int | None:
        ns = self.notes
        return min(ns, key=lambda n: n.pitch).klass if ns else None


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #


def read(path) -> tuple[list[Voice], int, dict]:
    """-> (voices, ticks per bar, meta). Only tracks with notes become voices."""
    mf = mido.MidiFile(str(path))
    ppq = mf.ticks_per_beat

    num, den, tempos = 4, 4, []
    for tr in mf.tracks:
        t = 0
        for m in tr:
            t += m.time
            if m.type == "time_signature" and t == 0:
                num, den = m.numerator, m.denominator
            elif m.type == "set_tempo":
                tempos.append(60_000_000 / m.tempo)

    voices: list[Voice] = []
    for i, tr in enumerate(mf.tracks):
        t, name, open_notes, notes = 0, "", {}, []
        for m in tr:
            t += m.time
            if m.type == "track_name" and not name:
                name = m.name
            elif m.type == "note_on" and m.velocity > 0:
                open_notes.setdefault(m.note, []).append(t)
            elif m.type == "note_off" or (m.type == "note_on" and m.velocity == 0):
                if open_notes.get(m.note):
                    notes.append(Note(open_notes[m.note].pop(0), t, m.note))
        if notes:
            voices.append(Voice(i, name, sorted(notes, key=lambda n: (n.start, n.pitch))))

    meta = {
        "ppq": ppq, "time_signature": f"{num}/{den}",
        "tempo_events": len(tempos),
        "bpm_min": round(min(tempos), 1) if tempos else None,
        "bpm_max": round(max(tempos), 1) if tempos else None,
    }
    return voices, ppq * num * 4 // den, meta


def bars(voices: list[Voice], bar_ticks: int,
         lo: int | None = None, hi: int | None = None) -> list[Bar]:
    """Slice into bars. `lo`/`hi` are 1-based and inclusive, like the DAW ruler."""
    if not any(v.notes for v in voices):
        return []
    first = min(n.start for v in voices for n in v.notes) // bar_ticks + 1
    last = max(n.end - 1 for v in voices for n in v.notes) // bar_ticks + 1
    lo = max(lo or first, 1)
    hi = min(hi or last, last)

    out = []
    for b in range(lo, hi + 1):
        t0, t1 = (b - 1) * bar_ticks, b * bar_ticks
        per_voice = {}
        for v in voices:
            # a note counts if it is sounding at any point inside the bar
            got = [n for n in v.notes if n.start < t1 and n.end > t0]
            if got:
                per_voice[v.index] = got
        out.append(Bar(b, per_voice))
    return out


# --------------------------------------------------------------------------- #
# naming
# --------------------------------------------------------------------------- #

# ordered longest-first so a 7th wins over the triad hiding inside it
QUALITIES: list[tuple[str, set[int]]] = [
    ("maj9", {0, 4, 7, 11, 2}), ("9", {0, 4, 7, 10, 2}), ("m9", {0, 3, 7, 10, 2}),
    ("11", {0, 7, 10, 2, 5}),
    ("maj7", {0, 4, 7, 11}), ("7", {0, 4, 7, 10}), ("m7", {0, 3, 7, 10}),
    ("m7b5", {0, 3, 6, 10}), ("dim7", {0, 3, 6, 9}), ("mMaj7", {0, 3, 7, 11}),
    ("6", {0, 4, 7, 9}), ("m6", {0, 3, 7, 9}),
    ("add9", {0, 4, 7, 2}), ("m(add9)", {0, 3, 7, 2}),
    ("7sus4", {0, 5, 7, 10}), ("sus4", {0, 5, 7}), ("sus2", {0, 2, 7}),
    ("maj", {0, 4, 7}), ("m", {0, 3, 7}), ("dim", {0, 3, 6}), ("aug", {0, 4, 8}),
    ("5", {0, 7}),
]


@dataclass
class Reading:
    """One defensible interpretation of a set of sounding notes.

    Not "the chord". A reading claims some of the notes as chord tones and
    leaves the rest over — and the leftovers are the interesting part, because
    that is where colour, anticipation and passing motion live. C-D-F-G-Bb is
    C11 with nothing left over, *and* Bb6 with C as an added 9th, *and* Gm7
    with F as an 11th. Which one is true depends on what the music is doing,
    which is a judgement the tool must not make on your behalf.
    """
    root: int
    quality: str
    chord_tones: set[int]
    leftover: set[int]          # sounding, but not part of this chord
    missing: set[int]           # in the chord shape but not sounding
    root_sounding: bool
    is_bass_root: bool

    @property
    def name(self) -> str:
        return f"{PCS[self.root]}{self.quality}"

    @property
    def explains(self) -> int:
        return len(self.chord_tones)

    def label(self, bass: int | None = None) -> str:
        n = self.name
        if bass is not None and bass != self.root:
            n += f"/{PCS[bass]}"
        # the slash already says the bass is not a chord tone; repeating it in
        # the leftovers reads as two different notes ("Gm7/C +C")
        extra = self.leftover - ({bass} if bass is not None else set())
        if extra:
            n += " +" + "".join(PCS[p] for p in sorted(extra))
        return n


def readings(pcs: set[int], bass: int | None = None,
             allow_rootless: bool = True) -> list[Reading]:
    """Every defensible reading of these notes, best-explaining first.

    Deliberately does NOT pick a winner. A bass note is only one hypothesis
    about function — it may equally be colour, a pedal, or an anticipation of
    the next chord — so `is_bass_root` is reported as a *property* of each
    reading rather than used to eliminate the others.

    Ordering is by how much each reading explains, then by whether its root is
    actually sounding, then by conventionality (bass-rooted). That ordering is
    a convenience, not a verdict; the caller gets the whole list.
    """
    out: list[Reading] = []
    for root in range(12):
        root_sounding = root in pcs
        if not root_sounding and not allow_rootless:
            continue
        iv = {(p - root) % 12 for p in pcs}
        for quality, shape in QUALITIES:
            if not shape <= iv:
                continue
            tones = {(root + i) % 12 for i in shape}
            out.append(Reading(
                root=root, quality=quality,
                chord_tones=tones & pcs,
                leftover=pcs - tones,
                missing=tones - pcs,
                root_sounding=root_sounding,
                is_bass_root=(bass is not None and root == bass),
            ))
    # drop readings whose shape is entirely contained in a better one at the
    # same root -- "Csus4 inside C7sus4" is noise, not an alternative lens
    keep: list[Reading] = []
    for r in out:
        if any(o.root == r.root and o.chord_tones > r.chord_tones for o in out):
            continue
        keep.append(r)

    keep.sort(key=lambda r: (-r.explains, len(r.missing), not r.root_sounding,
                             not r.is_bass_root, r.root))
    return keep


def interpretive_spread(rs: list[Reading]) -> list[int]:
    """Distinct roots among the *best-explaining* readings.

    This is the "does the lens matter here" number, and it is orthogonal to key
    ambiguity. One root means every reasonable reading agrees and the bar is
    what it looks like. Three roots means the bar is a genuine fork, and which
    branch you take changes the functional story downstream.
    """
    if not rs:
        return []
    top = rs[0].explains
    return sorted({r.root for r in rs if r.explains == top})


def name_chord(pcs: set[int], bass: int | None = None) -> str:
    """Best-effort name. Falls back to the raw pitch-class set rather than
    inventing a root — an honest '{C D F G}' beats a confident wrong symbol."""
    if not pcs:
        return "-"
    # (completeness, rooted on the bass, name). The bass tie-break matters:
    # C-D-G is equally Csus2 and Gsus4, but with G underneath it is heard as
    # Gsus4, and A-C-E-G is Am7 rather than C6/A. Without it the answer is
    # decided by pitch-class order, which is musically arbitrary.
    best: tuple[int, int, str] | None = None
    for root in range(12):
        iv = {(p - root) % 12 for p in pcs}
        for label, shape in QUALITIES:
            if iv == shape:
                cand = (len(shape), 1 if root == bass else 0, f"{PCS[root]}{label}")
                if best is None or cand[:2] > best[:2]:
                    best = cand
    if not best:
        return "{" + " ".join(PCS[p] for p in sorted(pcs)) + "}"

    name = best[2]
    root_name = name[:2] if len(name) > 1 and name[1] in "#b" else name[:1]
    if bass is not None and PCS[bass] != root_name:
        name += f"/{PCS[bass]}"
    return name


def modal_name(key: str, tonic: str) -> str | None:
    """'F' major collection heard from tonic C -> 'C Mixolydian'.

    The degrees must be generated from the KEY's root, not sorted numerically.
    Sorting gives [C D E F G A Bb] for F major, which puts C at index 0 and
    calls everything Ionian.
    """
    root = pc(key)
    degrees = [(root + i) % 12 for i in MAJOR]
    t = pc(tonic)
    if t not in degrees:
        return None
    return f"{PCS[t]} {MODES[degrees.index(t)]}"


# --------------------------------------------------------------------------- #
# the questions worth asking
# --------------------------------------------------------------------------- #


def key_fits(pcs: set[int], candidates: list[str] | None = None) -> list[str]:
    """Every major collection containing ALL of these pitch classes.

    Deliberately strict containment, not a weighted best guess. The width of
    this list is the ambiguity, and a weighted score would smear exactly the
    distinction being measured.
    """
    return [k for k in (candidates or KEY_ORDER) if pcs <= collection(k)]


def narrowing_voices(bar: Bar, voices: list[Voice],
                     candidates: list[str] | None = None) -> dict[int, list[str]]:
    """Per voice: which keys would still fit if this voice were silent.

    This is the line-level question — "which of my lines is closing the door" —
    and it is invisible in a chord symbol. Only voices that actually narrow
    anything are returned.
    """
    full = set(key_fits(bar.pcs, candidates))
    out: dict[int, list[str]] = {}
    for v in voices:
        if v.index not in bar.voices:
            continue
        others = {n.klass for i, ns in bar.voices.items() if i != v.index for n in ns}
        without = set(key_fits(others, candidates)) if others else set()
        gained = without - full
        if gained:
            out[v.index] = sorted(gained, key=KEY_ORDER.index)
    return out


def readings_without_voice(bar: Bar, voices: list[Voice]
                           ) -> dict[int, list[Reading]]:
    """Per voice: how the bar reads if that line is NOT a chord tone.

    The lens the bass most often needs. A bass note may be defining the chord,
    or it may be a pedal, a passing tone, or an anticipation of where the music
    is about to go — and in the last three cases the real chord is what the
    *other* voices are spelling. Same question for a melody sitting on a 9th.

    Only returns voices whose removal actually changes the best reading; a line
    that is doubling the others tells you nothing by leaving.
    """
    full = readings(bar.pcs, bar.bass)
    full_best = {r.name for r in full if r.explains == (full[0].explains if full else 0)}

    out: dict[int, list[Reading]] = {}
    for v in voices:
        if v.index not in bar.voices or len(bar.voices) < 2:
            continue
        rest = {n.klass for i, ns in bar.voices.items() if i != v.index for n in ns}
        if not rest or rest == bar.pcs:
            continue
        low = [n for i, ns in bar.voices.items() if i != v.index for n in ns]
        rest_bass = min(low, key=lambda n: n.pitch).klass if low else None
        alt = readings(rest, rest_bass)
        if alt and {r.name for r in alt if r.explains == alt[0].explains} != full_best:
            out[v.index] = alt
    return out


def sounds_together(voices: list[Voice], a: int, b: int,
                    ppq: int) -> list[tuple[int, float, str, str]]:
    """Every moment pitch classes `a` and `b` overlap -> (tick, beats, who, who).

    Duration matters more than count. A tritone crossing for 0.01 beats is a
    note-boundary artifact; one held for 2 beats is a statement of key. The
    caller decides the threshold, so both are reported.
    """
    A = [(n, v) for v in voices for n in v.notes if n.klass == a]
    B = [(n, v) for v in voices for n in v.notes if n.klass == b]
    out = []
    for na, va in A:
        for nb, vb in B:
            s, e = max(na.start, nb.start), min(na.end, nb.end)
            if s < e:
                out.append((s, (e - s) / ppq, va.label, vb.label))
    return sorted(out)


def where_is(voices: list[Voice], klass: int, bar_ticks: int,
             ppq: int) -> list[tuple[int, float, float, str]]:
    """Every occurrence of a pitch class -> (bar, beat, length in beats, voice)."""
    out = []
    for v in voices:
        for n in v.notes:
            if n.klass == klass:
                out.append((n.start // bar_ticks + 1,
                            (n.start % bar_ticks) / ppq + 1,
                            (n.end - n.start) / ppq, v.label))
    return sorted(out)


def one_note_away(pcs: set[int], candidates: list[str] | None = None
                  ) -> list[tuple[str, str, str]]:
    """Single-semitone moves that relocate this whole set into another key.

    The pivot search that matters for a line-writer: not "what chord bridges
    these keys" but "which one note do I move, in which line". Returns
    (from, to, key).
    """
    out = []
    for k in (candidates or KEY_ORDER):
        col = collection(k)
        outside = pcs - col
        if len(outside) != 1:
            continue
        p = next(iter(outside))
        for delta in (-1, 1):
            if (p + delta) % 12 in col and (p + delta) % 12 not in pcs:
                out.append((PCS[p], PCS[(p + delta) % 12], k))
    return out

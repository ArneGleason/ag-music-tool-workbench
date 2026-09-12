"""suno-project: a Suno Stems folder → a Bitwig starter project.

One folder of paired `<song> (Instrument).wav/.mid` in, one light
`.dawproject` out: a performance-following tempo lane, one cleaned note
track per stem with velocities and (for mono stems) per-note pitch curves
read off the audio, and an empty audio track per stem to drop the wav onto.
Every convention in it is the user's own, measured from their projects:

- two bars of count-in; MIDI starts on bar 3 (beat 8)
- the audio is dropped a few 16ths before bar 3 so that Suno's grid origin
  (which sits `offset` seconds into the wav — 0.1–0.55 s, per song) lands
  on bar 3; the count-in stays flat and the last few 16ths absorb the
  difference. The drop position is computed and printed as bar.beat.16th.
- the tempo lane is Suno's per-beat map refined by the drum hits, so the
  grid sits on the performance (the tempo-map tool, verified by the user)

Verification that matters: open it, drop the stems where it says, and look
at the grid against the hats; play a note track against its stem.
"""
from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
from pathlib import Path

from ...spec import Field, Tool


def _song_key(path: Path) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", path.stem)


def _instrument(path: Path) -> str:
    m = re.search(r"\(([^)]*)\)\s*$", path.stem)
    return m.group(1) if m else path.stem


def run(args: argparse.Namespace) -> int:
    import numpy as np
    import soundfile as sf

    from ...core import audio_utils
    from ..midi import clean as clean_mod
    from ..midi.midi import read_tracks, ticks_to_seconds
    from ..tempomap import render, solve
    from . import express, project

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"not a folder: {folder}", file=sys.stderr)
        return 2
    pairs = [(m, m.with_suffix(".wav")) for m in sorted(folder.glob("*.mid"))
             if ".clean" not in m.stem and m.with_suffix(".wav").exists()]
    if not pairs:
        print("no <name>.mid with a matching <name>.wav in that folder", file=sys.stderr)
        return 2
    song = _song_key(pairs[0][0])
    print(f"song: {song}  ({len(pairs)} stems)")

    # ---- 1. offset: MIDI beat 0 sits this many seconds into every wav ----
    measured = []
    for mid, wav in pairs:
        off, prom = clean_mod.estimate_offset(mid, wav)
        measured.append((mid, off, prom))
    offset = statistics.median(o for _, o, _ in measured)
    for mid, off, prom in measured:
        flag = "   <- outlier, using the median" if abs(off - offset) > 0.1 or prom < 1.5 else ""
        print(f"  offset {off:+.3f}s  {_instrument(mid)}{flag}")
    print(f"  song offset {offset:+.3f}s (median)")

    # ---- 2. prior grid from Suno's per-beat tempo map ----
    drum = next(((m, w) for m, w in pairs if re.search(r"drum|percussion", m.stem, re.I)), None)
    src_mid = drum[0] if drum else pairs[0][0]
    srcs = read_tracks(src_mid, None)
    ppq, tmap = srcs[0].ppq, srcs[0].tempo_map
    B0 = 4.0 * args.count_in
    prior = [(B0 + tick / ppq, 60e6 / tempo) for tick, tempo in tmap]
    T0 = prior[0][1]
    if prior[0][0] > 0:
        prior.insert(0, (0.0, T0))

    # ---- 3. audio drop position: whole 16ths before bar 3 that cover the offset ----
    sixteenth_s = 60.0 / T0 / 4
    n16 = max(0, math.ceil(max(0.0, offset) / sixteenth_s - 1e-6))
    clip_beat = B0 - 0.25 * n16
    pos = f"{int(clip_beat // 4) + 1}.{int(clip_beat % 4) + 1}.{int((clip_beat % 1) / 0.25) + 1}.00"

    # ---- 4. tempo lane: prior + drum anchors + the downbeat pinned to the offset ----
    wav_for_tempo = drum[1] if drum else pairs[0][1]
    y, sr = sf.read(str(wav_for_tempo), always_2d=True, dtype="float32")
    y = y.mean(axis=1)
    length_s = len(y) / sr
    last_beat = B0
    while solve.lane_seconds(prior, clip_beat, last_beat + 1) < length_s:
        last_beat += 1
    anchors = []
    if drum:
        hit_t, hit_w = solve.onsets(y, sr)
        anchors = [a for a in solve.assign_anchors(prior, clip_beat, B0, last_beat, hit_t, hit_w,
                                                   sub=args.sub, tolerance=args.tolerance)
                   if abs(a.beat - B0) > 1e-6]
        print(f"  tempo from {_instrument(drum[0])}: {len(hit_t)} hits, {len(anchors)} anchored")
    else:
        hit_t = np.array([])
        print("  no drum stem — tempo lane is Suno's map with the lead-in solved only")
    anchors.insert(0, solve.Anchor(B0, max(0.0, offset), 1.0,
                                   solve.lane_seconds(prior, clip_beat, B0)))
    sol = solve.solve(prior, clip_beat, anchors, last_beat, first_beat=B0, sub=args.sub,
                      max_dev=args.max_dev / 100.0)
    pts = solve.thin(sol.grid, sol.tempo)
    if clip_beat > 0:
        pts = [(0.0, pts[0][1])] + pts
    lane_b = np.array([p[0] for p in pts]); lane_t = np.array([p[1] for p in pts])
    # audio seconds -> arrangement beat, inverted through the written lane on a
    # 1/64 table, so a note sits where it SOUNDS even where the drums moved the
    # grid under it (Suno's note times are unquantised tick positions on its
    # own grid; the grid just changed shape)
    fine = np.arange(clip_beat, last_beat + 8.0, 1 / 64)
    fine_t = np.interp(fine, lane_b, lane_t)
    fine_s = np.concatenate([[0.0], np.cumsum(solve.seg_seconds(np.diff(fine), fine_t[:-1], fine_t[1:]))])

    def beat_at(seconds: np.ndarray) -> np.ndarray:
        return np.interp(seconds, fine_s, fine)

    err = np.abs(sol.residual_ms)
    print(f"  lane: {len(pts)} points, {sol.tempo.min():.1f}–{sol.tempo.max():.1f} bpm, "
          f"anchor error median {np.median(err):.1f} ms / 95% {np.percentile(err, 95):.1f} ms; "
          f"lead-in {solve.lane_seconds(pts, clip_beat, B0):.3f}s for a {offset:.3f}s offset")

    # ---- 5. each stem: clean, then read expression off its wav ----
    note_tracks: list[project.NoteTrack] = []
    audio_tracks: list[project.AudioTrack] = []
    for mid, wav in pairs:
        inst = _instrument(mid)
        c = clean_mod.clean_notes(mid)                 # no shift: alignment is by audio placement
        prof = clean_mod.PROFILES[c.profile]
        notes = c.notes
        beats = np.array([n.start / c.ppq for n in notes])
        durs = np.array([(n.end - n.start) / c.ppq for n in notes])
        keys = np.array([n.pitch for n in notes])
        on_s = np.array([ticks_to_seconds(n.start, c.ppq, c.tempo_map) + offset for n in notes])
        off_s = np.array([ticks_to_seconds(n.end, c.ppq, c.tempo_map) + offset for n in notes])

        ys, ssr = sf.read(str(wav), always_2d=True, dtype="float32")
        ys = ys.mean(axis=1)
        vel = express.velocities(ys, ssr, on_s, keys, drums=prof.drums,
                                 vel_lo=args.vel_lo, vel_hi=args.vel_hi,
                                 range_db=args.range_db) if args.velocity else \
            np.full(len(notes), 100, dtype=int)

        bends: list[list[tuple[float, float]]] = [[] for _ in notes]
        n_bent = 0
        if args.bends and c.profile in express.PITCH_RANGE and len(notes):
            fmin, fmax = express.PITCH_RANGE[c.profile]
            tt, tm = express.pitch_track(ys, ssr, fmin, fmax)
            for i, n in enumerate(notes):
                curve = express.bend_curve(tt, tm, on_s[i], off_s[i], int(keys[i]))
                if curve:
                    bps = float(np.interp(B0 + beats[i], lane_b, lane_t)) / 60.0
                    bends[i] = [(t * bps, v) for t, v in curve]
                    n_bent += 1

        nb_start = beat_at(on_s) - B0                  # clip-relative beats, audio-true
        nb_dur = np.maximum(beat_at(off_s) - beat_at(on_s), 0.01)
        pnotes = [project.PNote(float(nb_start[i]), float(nb_dur[i]), int(keys[i]),
                                int(vel[i]), bends[i]) for i in range(len(notes))]
        note_tracks.append(project.NoteTrack(f"{inst} MIDI", B0, pnotes))
        audio_tracks.append(project.AudioTrack(inst))
        st = c.stats
        print(f"  {inst:<16} [{c.profile}] {st['in']} -> {st['out']} notes, "
              f"vel {vel.min() if len(vel) else '-'}–{vel.max() if len(vel) else '-'}, "
              f"{n_bent} with pitch curves")

    # ---- 6. write ----
    out_dir = Path(args.out_dir) if args.out_dir else folder
    xml = project.build_xml(T0, pts, note_tracks, audio_tracks)
    out = project.write(out_dir / f"{song}.dawproject", xml, song,
                        comment=f"drop audio stems at {pos} (beat {clip_beat:g}), raw; "
                                f"MIDI starts at bar {args.count_in + 1}")
    print(f"wrote {out}")
    print(f"  -> drop every stem at position {pos} (beat {clip_beat:g}), raw/unstretched")

    if drum:
        click = render.click_track(pts, clip_beat, B0, last_beat, len(y), sr, sub=args.sub)
        mix = np.clip(y * 0.7 + click * 0.6, -1, 1).astype(np.float32)
        audio_utils.save(out_dir / f"{song}.drums+click.wav", mix, sr)
        render.picture(sol, pts, hit_t, out_dir / f"{song}.tempo.png", f"{song} — tempo lane")
        print(f"  review: {song}.drums+click.wav, {song}.tempo.png")
    return 0


TOOL = Tool(
    name="suno-project", title="Suno stems → Bitwig project", group="Bitwig", run=run, order=20,
    help="build a light .dawproject from a Suno Stems folder: tempo lane, cleaned expressive MIDI, empty audio tracks",
    blurb="Point it at a Suno Stems folder (wav + mid pairs). Out comes a small "
          ".dawproject: the tempo lane bent to the drums, one cleaned note track "
          "per stem with velocities read off the audio and pitch curves on the "
          "mono stems, and an empty audio track per stem. Open it, drop the wavs "
          "where it says, and the grid, the notes and the audio line up.",
    note="Velocities come from each note's own harmonic band in the stem, mapped "
         "through the stem's loudness range with a floor — stems softened by the "
         "split still sound. Pitch curves only on lead vocal / bass (mono). No "
         "per-note gain envelopes, by request. The drop position is printed as "
         "bar.beat.16th; drop raw, not stretched.",
    fields=[
        Field("folder", "Suno Stems folder", "text", required=True,
              help="folder holding <song> (Instrument).wav and .mid pairs"),
        Field("out_dir", "Output folder", "text", flag="--out-dir",
              help="blank = the Stems folder itself"),
        Field("count_in", "Count-in bars", "int", flag="--count-in", default=2,
              min=0, max=8, step=1, help="MIDI starts on the bar after these"),
        Field("velocity", "Velocities from audio", "bool", flag="--velocity", default=True),
        Field("bends", "Pitch curves on mono stems", "bool", flag="--bends", default=True),
        Field("vel_lo", "Velocity floor", "int", flag="--vel-lo", default=30, min=1, max=127,
              step=1, advanced=True, help="nothing goes below this, so split-softened notes still sound"),
        Field("vel_hi", "Velocity ceiling", "int", flag="--vel-hi", default=120, min=1, max=127,
              step=1, advanced=True, help="the loudest 10% land here"),
        Field("range_db", "Dynamic range dB", "float", flag="--range-db", default=24.0,
              min=6.0, max=60.0, step=1.0, advanced=True,
              help="notes this far below the loud reference reach the floor"),
        Field("max_dev", "Max tempo deviation %", "float", flag="--max-dev", default=12.0,
              min=1.0, max=40.0, step=1.0, advanced=True),
        Field("tolerance", "Anchor window", "float", flag="--tolerance", default=0.4,
              min=0.1, max=0.5, step=0.05, advanced=True),
        Field("sub", "Grid per beat", "int", flag="--sub", default=4, min=2, max=8, step=1,
              advanced=True),
    ],
)

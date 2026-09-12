"""tempo-map: bend a Bitwig project's tempo lane to the drum performance.

Reads a .dawproject, follows the drum stem inside it, and writes a copy with
a ramped tempo lane in which every anchored 16th lands on its hit. Never
overwrites the input. Also writes a click track rendered from the new lane
(mixed with the drums for the A/B tool) and a picture of where the map
strained — the review the user does by hand today, 2–3 hours a song.

Conventions it leans on, all from the user's own projects:
- the audio clip starts a little before a whole beat and the song's first
  downbeat sits on that beat (clip at 7.25, downbeat at 8 after a two-bar
  count-in); the count-in keeps the tempo flat
- the existing tempo lane (Suno's per-beat map, imported) is the prior grid;
  the solve only moves things inside the beat
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ...spec import Field, Tool


def run(args: argparse.Namespace) -> int:
    import math

    import numpy as np

    from ...core import audio_utils
    from . import dawproject, render, solve

    src = Path(args.project)
    if not src.exists():
        print(f"project not found: {src}", file=sys.stderr)
        return 2
    proj = dawproject.load(src)
    if not proj.clips:
        print("no audio clips found in the arrangement", file=sys.stderr)
        return 2

    want = args.track.lower()
    cands = [c for c in proj.clips if want in c.track.lower() or want in c.path.lower()]
    if not cands:
        print(f"no audio clip matching {args.track!r}; clips are:", file=sys.stderr)
        for c in proj.clips:
            print(f"  [{c.track}] {c.path}", file=sys.stderr)
        return 2
    clip = min(cands, key=lambda c: c.time)          # the earliest placed instance
    print(f"following: [{clip.track}] {Path(clip.path).name}")
    print(f"  clip at beat {clip.time}, plays {clip.play_start:.2f}–{clip.play_stop:.2f} s")

    prior = proj.tempo_points or [(0.0, proj.tempo)]
    if not proj.tempo_points:
        print(f"  no tempo lane in the project — using a flat {proj.tempo:.2f} bpm as the prior "
              "(beat tracking will have to carry the drift alone)")

    first_beat = float(args.downbeat) if args.downbeat >= 0 else float(math.ceil(clip.time - 1e-9))
    audio, sr = proj.read_audio(clip.path)
    mono = audio.mean(axis=1)
    a0 = int(clip.play_start * sr)
    a1 = int(clip.play_stop * sr) if clip.play_stop > 0 else len(mono)
    mono = mono[a0:a1]
    length_s = len(mono) / sr

    # last beat the audio reaches under the prior
    last_beat = first_beat
    while solve.lane_seconds(prior, clip.time, last_beat + 1) < length_s:
        last_beat += 1
    print(f"  first downbeat at beat {first_beat:g}, audio reaches beat {last_beat:g} "
          f"({(last_beat - first_beat) / 4:.0f} bars)")

    hit_t, hit_w = solve.onsets(mono, sr)
    anchors = solve.assign_anchors(prior, clip.time, first_beat, last_beat, hit_t, hit_w,
                                   sub=args.sub, tolerance=args.tolerance)
    # the downbeat itself: the hit nearest the prior's beat-`first_beat` time
    print(f"  {len(hit_t)} drum hits, {len(anchors)} anchored to a 1/{args.sub * 4} grid "
          f"({len(anchors) / max(1, len(hit_t)) * 100:.0f}%)")

    sol = solve.solve(prior, clip.time, anchors, last_beat, first_beat=first_beat,
                      sub=args.sub, max_dev=args.max_dev / 100.0)
    pts = solve.thin(sol.grid, sol.tempo)
    # count-in: flat from the project start to the clip start (the solve
    # pinned the clip-start point to the song's median tempo)
    if clip.time > 0:
        pts = [(0.0, pts[0][1])] + [(p[0], p[1]) for p in pts]
    # hold the last value to the end of the project's lane
    if proj.tempo_points and proj.tempo_points[-1][0] > pts[-1][0]:
        pts.append((proj.tempo_points[-1][0], pts[-1][1]))

    err = np.abs(sol.residual_ms)
    dev = (sol.tempo / sol.baseline - 1) * 100
    print(f"  anchor error after solve: median {np.median(err):.1f} ms, 95% {np.percentile(err, 95):.1f} ms, "
          f"max {err.max():.1f} ms")
    print(f"  tempo range {sol.tempo.min():.1f}–{sol.tempo.max():.1f} bpm "
          f"(deviation from prior {dev.min():+.1f}% … {dev.max():+.1f}%; bound ±{args.max_dev:g}%)")
    strained = int((np.abs(dev) > args.max_dev * 0.95).sum())
    if strained:
        print(f"  ! {strained} points sit at the deviation bound — hits the rule could not reach; "
              "look at the picture")
    print(f"  lane: {len(pts)} points after thinning ({len(sol.grid)} solved)")

    # outer clip durations must still cover the audio under the new lane
    durations = {}
    for i, c in enumerate(proj.clips):
        secs = (c.play_stop - c.play_start) if c.play_stop > 0 else length_s
        b = c.time
        while solve.lane_seconds(pts, c.time, b) < secs:
            b += 0.25
        durations[i] = (b - c.time) + 0.25
    out_dir = Path(args.out_dir) if args.out_dir else src.parent
    stem = src.stem + ".tempo"
    out_proj = dawproject.write(proj, out_dir / f"{stem}.dawproject", pts, durations)
    print(f"wrote {out_proj}")
    if args.light:
        light = dawproject.write(proj, out_dir / f"{stem}.light.dawproject", pts, durations,
                                 light=True)
        # Bitwig shows positions as bar.beat.sixteenth.tick, 1-based
        b = clip.time
        pos = f"{int(b // 4) + 1}.{int(b % 4) + 1}.{int((b % 1) / 0.25) + 1}.00"
        print(f"wrote {light}  (no audio: drop the stems at beat {b:g} = position {pos}, "
              "raw/unstretched, and they should sit on the lane)")

    # review artefacts from the WRITTEN points
    click = render.click_track(pts, clip.time, first_beat, last_beat, len(mono), sr, sub=args.sub)
    audio_utils.save(out_dir / f"{stem}.click.wav", click, sr)
    mix = np.clip(mono * 0.7 + click * 0.6, -1, 1).astype(np.float32)
    audio_utils.save(out_dir / f"{stem}.drums+click.wav", mix, sr)
    png = render.picture(sol, pts, hit_t, out_dir / f"{stem}.png", f"{src.name} — {clip.track}")
    print(f"wrote {out_dir / (stem + '.drums+click.wav')}  (A/B this against the drum stem)")
    print(f"wrote {png}")
    return 0


TOOL = Tool(
    name="tempo-map", title="Tempo map from drums", group="Bitwig", run=run, order=30,
    help="bend a .dawproject's tempo lane to the drum performance (ramps, 16th grid)",
    blurb="Export the project as .dawproject, point this at it. It follows the "
          "drum stem, anchors every 16th it can to a hit, solves linear tempo "
          "ramps so the grid sits on the performance, and writes a copy of the "
          "project with the new lane — plus a drums+click mix to A/B and a picture "
          "of where it strained.",
    note="Needs the audio placed the way you already do it: clip a little before "
         "a whole beat, first downbeat on that beat, count-in before. The existing "
         "lane (Suno's per-beat map) is the prior; only sub-beat timing moves. Its "
         "anchor choice is a bounded rule, not your judgment — check the picture "
         "and the click mix before trusting a section.",
    fields=[
        Field("project", "Project (.dawproject)", "file", accept=["dawproject"],
              root="bitwig", required=True),
        Field("track", "Follow track", "text", flag="--track", default="Drum Kit",
              help="substring of the audio track or file name to follow"),
        Field("out_dir", "Output folder", "text", flag="--out-dir",
              help="blank = next to the project; writes <name>.tempo.dawproject"),
        Field("light", "Also write a light copy (no audio)", "bool", flag="--light",
              default=True,
              help="<name>.tempo.light.dawproject: tempo lane + note tracks, audio "
                   "tracks left empty - a few hundred KB to open and drop stems into"),
        Field("max_dev", "Max tempo deviation %", "float", flag="--max-dev", default=12.0,
              min=1.0, max=40.0, step=1.0,
              help="how far a ramp may leave the prior tempo to reach a hit"),
        Field("tolerance", "Anchor window", "float", flag="--tolerance", default=0.4,
              min=0.1, max=0.5, step=0.05, advanced=True,
              help="fraction of a grid step a hit may sit from the slot and still anchor it"),
        Field("sub", "Grid per beat", "int", flag="--sub", default=4, min=2, max=8, step=1,
              advanced=True, help="4 = 16ths, 3 = triplets, 6 = both-ish"),
        Field("downbeat", "First downbeat beat", "float", flag="--downbeat", default=-1.0,
              min=-1.0, max=64.0, step=0.25, advanced=True,
              help="-1 = first whole beat after the clip start"),
    ],
)

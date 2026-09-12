"""Preserve source performance times while changing the musical grid.

Changing tempo without inverse-mapping every note would change its audible
timing a second time. Notes are cleaned in source MIDI ticks, converted through
the ORIGINAL step-tempo map into seconds, then inverted through the WRITTEN
linear tempo lane. The shared audio offset is handled by moving all raw clips
earlier in the flat count-in, keeping the musical downbeat at the user's bar.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET


def fingerprint(notes):
    return Counter((round(t, 3), int(k)) for t, k in notes)


def process(project_path, stems_path, output_path, work_path):
    import numpy as np
    import soundfile as sf
    from threadpoolctl import threadpool_limits
    from ..midi.midi import read_tracks, ticks_to_seconds
    from ..midi.clean import clean_notes, estimate_offset
    from ..tempomap import solve, render

    if not output_path or not work_path:
        raise ValueError("Output project and review folder are required")
    src, folder, out, work = map(Path, (project_path, stems_path, output_path, work_path))
    if out.resolve() == src.resolve() or out.exists():
        raise ValueError("Choose a new output filename; existing projects are never overwritten")
    work.mkdir(parents=True, exist_ok=True)
    report = {"source": str(src), "output": str(out), "groups": [], "offsets": {}}
    with zipfile.ZipFile(src) as zin:
        root = ET.fromstring(zin.read("project.xml"))
    structure = root.find("Structure")
    arrangement = root.find("Arrangement")
    lanes = arrangement.find("Lanes")
    lane_by_id = {l.get("track"): l for l in lanes.findall("Lanes")}
    signature = root.find("Transport/TimeSignature")
    if signature.get("numerator") != "4" or signature.get("denominator") != "4":
        raise ValueError("This workflow currently requires 4/4")

    sources = {}
    for mid in sorted(folder.glob("*.mid")):
        wav = mid.with_suffix(".wav")
        if not wav.exists():
            continue
        tracks = read_tracks(mid, None)
        if not tracks:
            continue
        s = tracks[0]
        fp = fingerprint((n.start / s.ppq, n.pitch) for t in tracks for n in t.notes)
        sources[mid.stem] = (mid, wav, tracks, fp)

    matched = []
    starts = set()
    for tr in list(structure.findall("Track")):
        children = tr.findall("Track") or [tr]
        note_children = [c for c in children if c.get("contentType") == "notes"]
        if not note_children:
            continue
        notes = []
        for child in note_children:
            lane = lane_by_id[child.get("id")]
            clips = lane.findall("Clips/Clip")
            if len(clips) != 1 or float(clips[0].get("playStart", 0)) != 0:
                raise ValueError("Expected one untrimmed source MIDI clip per child")
            clip = clips[0]
            starts.add(float(clip.get("time")))
            notes.extend((float(n.get("time")), int(n.get("key"))) for n in clip.findall("Notes/Note"))
            if any(list(n) for n in clip.findall("Notes/Note")):
                raise ValueError("Expressive edited notes need a different preservation workflow")
        fp = fingerprint(notes)
        names = [name for name, (_, _, _, candidate) in sources.items() if fp == candidate]
        if len(names) != 1:
            raise ValueError(f"Cannot identify {tr.get('name')} exactly from original MIDI")
        name = names[0]
        matched.append((tr, note_children, name))
        print(f"Matched {tr.get('name')}: {name}, {len(note_children)} tracks / {len(notes)} notes", flush=True)
    if len(starts) != 1 or len({m[2] for m in matched}) != len(matched):
        raise ValueError("Expected a common clip start and one project part per source instrument")
    B0 = starts.pop()
    if B0 < 4 or B0 % 4:
        raise ValueError("Need at least one count-in bar and a whole-bar start")
    audio_lanes = [l for l in lanes.findall("Lanes") if l.find(".//Audio") is not None]
    for l in audio_lanes:
        clips = l.findall("Clips/Clip")
        if len(clips) != 1 or float(clips[0].get("time")) != B0:
            raise ValueError("Audio clips must share the MIDI start")
        audio = l.find(".//Audio")
        if audio.get("algorithm") != "raw":
            raise ValueError("Expected raw audio; refusing to reinterpret stretched clips")
        inner = clips[0].find("Clips/Clip")
        if float(inner.get("playStart", 0)) != 0:
            raise ValueError("Trimmed source audio is unsupported")
        entry = audio.find("File").get("path")
        source_wav = folder / Path(entry).name
        with zipfile.ZipFile(src) as zin:
            if not source_wav.exists() or hashlib.sha256(zin.read(entry)).digest() != hashlib.sha256(source_wav.read_bytes()).digest():
                raise ValueError("Embedded WAV does not match the source used for timing analysis")

    # Cache measured onsets/offsets by file content, not name or an old song's
    # offset. A retry after a writer failure should not re-analyse eight WAVs.
    cache_path = work / "source-analysis.json"
    signature_hash = hashlib.sha256()
    for name in sorted(sources):
        for p in sources[name][:2]:
            signature_hash.update(p.read_bytes())
    digest = signature_hash.hexdigest()
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if cache.get("digest") != digest:
        cache = {"digest": digest, "stems": {}}
    audio_data = {}
    for _, _, name in matched:
        mid, wav, _, _ = sources[name]
        y, sr = sf.read(wav, always_2d=True, dtype="float32")
        y = y.mean(axis=1)
        audio_data[name] = (y, sr)
        if name not in cache["stems"]:
            offset, prominence = estimate_offset(mid, wav)
            ht, hw = solve.onsets(y, sr)
            cache["stems"][name] = {"offset": offset, "prominence": prominence,
                                    "times": ht.tolist(), "weights": hw.tolist()}
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
        v = cache["stems"][name]
        report["offsets"][name] = {k: v[k] for k in ("offset", "prominence")}
        print(f"Offset {name}: {v['offset']:+.4f}s (prominence {v['prominence']:.2f})", flush=True)

    # Vocal anticipation is not a timing reference. Reject inconsistent
    # rhythmic estimates before taking the shared median (banjo can alias).
    rhythm = [n for _, _, n in matched if "vocal" not in n.lower()]
    offsets = [cache["stems"][n]["offset"] for n in rhythm
               if cache["stems"][n]["prominence"] >= 1.5]
    median = float(np.median(offsets))
    agreed = [o for o in offsets if abs(o - median) < .1]
    if len(agreed) < 3:
        raise ValueError("Fewer than three rhythmic stems agree on the shared offset")
    offset = float(np.median(agreed))
    if offset < 0 or offset > 1.5:
        raise ValueError("Offset falls outside this count-in placement workflow")
    report["shared_offset_s"] = offset
    drum_name = next(n for n in rhythm if re.search("drum|percussion", n, re.I))
    original = sources[drum_name][2][0]
    for _, _, ss, _ in sources.values():
        if ss[0].tempo_map != original.tempo_map or ss[0].ppq != original.ppq:
            raise ValueError("Source files must agree on the prior tempo map")
    prior = [(B0 + t / original.ppq, 60e6 / v) for t, v in original.tempo_map]
    duration = max(len(y) / sr for y, sr in audio_data.values())
    last = prior[-1][0]
    while solve.lane_seconds(prior, B0, last) < duration - offset:
        last += 1
    anchors_by_name = {}
    for name in rhythm:
        c = cache["stems"][name]
        anchors_by_name[name] = solve.assign_anchors(prior, B0, B0, last,
            np.array(c["times"]) - offset, np.array(c["weights"]))
    anchors = list(anchors_by_name[drum_name])
    drum_beats = np.array([a.beat for a in anchors])
    fallbacks = []
    # Do not turn a missing hat into a bass-led grid while drums are playing.
    # Only fill gaps at least a beat away from ANY drum anchor. Require two
    # non-vocal instruments within 25 ms, and down-weight their consensus.
    slots = {}
    for name, aa in anchors_by_name.items():
        if name == drum_name:
            continue
        for a in aa:
            if np.min(np.abs(drum_beats - a.beat)) <= 1:
                continue
            slots.setdefault(a.beat, []).append((name, a))
    for beat, candidates in sorted(slots.items()):
        best = max(([c for c in candidates if abs(c[1].seconds - pivot[1].seconds) <= .025]
                    for pivot in candidates), key=len)
        if len(best) < 2:
            continue
        sec = float(np.median([a.seconds for _, a in best]))
        weight = .6 * float(np.mean([a.weight for _, a in best]))
        anchors.append(solve.Anchor(beat, sec, weight, best[0][1].predicted))
        fallbacks.append({"beat": beat, "seconds": sec, "instruments": [n for n, _ in best]})
    anchors.sort(key=lambda a: a.beat)
    print(f"Solving {len(anchors)} anchors ({len(fallbacks)} instrument-consensus fallbacks)", flush=True)
    with threadpool_limits(limits=2):
        sol = solve.solve(prior, B0, anchors, last, first_beat=B0)
    # Check error on the written lane, not only the dense optimisation grid.
    dense_seconds = np.r_[0., np.cumsum(solve.seg_seconds(np.diff(sol.grid), sol.tempo[:-1], sol.tempo[1:]))]
    tolerance = .1
    while True:
        pts = [(round(b, 6), round(t, 6)) for b, t in solve.thin(sol.grid, sol.tempo, tol_bpm=tolerance)]
        sampled = np.interp(sol.grid, [p[0] for p in pts], [p[1] for p in pts])
        sparse_seconds = np.r_[0., np.cumsum(solve.seg_seconds(np.diff(sol.grid), sampled[:-1], sampled[1:]))]
        thinning_error = float(max(abs(sparse_seconds - dense_seconds)))
        if thinning_error <= .001:
            break
        tolerance /= 2
        if tolerance < 1e-6:
            raise ValueError("Could not thin the lane without introducing timing drift")
    report["max_thinning_drift_ms"] = thinning_error * 1000
    pts.insert(0, (0., pts[0][1]))
    bs, ts = np.array(pts).T
    elapsed = np.r_[0., np.cumsum(solve.seg_seconds(np.diff(bs), ts[:-1], ts[1:]))]

    def seconds_at(beats):
        b = np.asarray(beats, dtype=float)
        idx = np.clip(np.searchsorted(bs, b, side="right") - 1, 0, len(bs) - 1)
        end = np.minimum(idx + 1, len(bs) - 1)
        slope = np.divide(ts[end] - ts[idx], bs[end] - bs[idx],
                          out=np.zeros_like(b), where=bs[end] != bs[idx])
        at = ts[idx] + slope * (b - bs[idx])
        return elapsed[idx] + solve.seg_seconds(b - bs[idx], ts[idx], at)

    def beats_at(seconds):
        s = np.asarray(seconds, dtype=float)
        idx = np.clip(np.searchsorted(elapsed, s, side="right") - 1, 0, len(bs) - 1)
        end = np.minimum(idx + 1, len(bs) - 1)
        slope = np.divide(ts[end] - ts[idx], bs[end] - bs[idx],
                          out=np.zeros_like(s), where=bs[end] != bs[idx])
        dt = s - elapsed[idx]
        db = np.where(abs(slope) < 1e-10, dt * ts[idx] / 60,
                      ts[idx] * np.expm1(slope * dt / 60) / np.where(abs(slope) < 1e-10, 1, slope))
        return bs[idx] + db

    start_seconds = float(seconds_at(np.array([B0]))[0])
    audio_beat = float(beats_at(np.array([start_seconds - offset]))[0])
    report.update(audio_start_beat=audio_beat, musical_start_beat=B0,
                  tempo_points=len(pts), bpm_range=[float(min(ts)), float(max(ts))],
                  fallback_anchors=fallbacks)
    errors = np.array([float(seconds_at(np.array([a.beat]))[0]) - start_seconds - a.seconds
                       for a in anchors]) * 1000
    report["anchor_error_ms"] = {"median": float(np.median(abs(errors))),
        "p95": float(np.percentile(abs(errors), 95)), "max": float(max(abs(errors)))}
    report["anchors"] = [dict(beat=a.beat, seconds=a.seconds, weight=a.weight,
                               error_ms=float(e)) for a, e in zip(anchors, errors)]
    if np.percentile(abs(errors), 95) > 25:
        raise ValueError(f"Tempo fit needs review: {report['anchor_error_ms']}")

    # Convert each group into its first child, keeping that instrument and
    # routing. Suno imports in this workflow have neutral group mixers.
    removed_ids = set()
    max_timing_error = 0.
    for tr, children, name in matched:
        kept = children[0]
        if tr is not kept:
            gc = tr.find("Channel")
            if float(gc.find("Volume").get("value")) != 1 or float(gc.find("Pan").get("value")) != .5:
                raise ValueError("Non-neutral group mixing cannot be flattened safely")
            if gc.find("Devices") is not None:
                raise ValueError("Group effects require explicit routing preservation")
            kept.find("Channel").set("destination", gc.get("destination"))
            index = list(structure).index(tr)
            tr.remove(kept)
            structure.remove(tr)
            structure.insert(index, kept)
            removed_ids.update(e.get("id") for e in tr.iter() if e.get("id"))
        kept.set("name", name + " MIDI")
        if tr.get("color"):
            kept.set("color", tr.get("color"))
        for child in children[1:]:
            lane = lane_by_id[child.get("id")]
            removed_ids.update(e.get("id") for e in lane.iter() if e.get("id"))
            lanes.remove(lane)
        if tr is not kept and tr.get("id") in lane_by_id:
            lanes.remove(lane_by_id[tr.get("id")])
        lane = lane_by_id[kept.get("id")]
        # The only source CCs are a terminal CC7=100. Bitwig interpolates
        # these into a spurious track-long volume fade. They are exporter
        # bookkeeping, not expression; fail rather than discard other CCs.
        for s in sources[name][2]:
            if any(cc != 7 or val != 100 for _, cc, val in s.ccs):
                raise ValueError("Unexpected MIDI controllers require preservation")
        for points in list(lane.findall("Points")):
            target = points.find("Target")
            if target is None or target.get("controller") != "7":
                raise ValueError("Unexpected MIDI automation requires preservation")
            lane.remove(points)
        clip = lane.find("Clips/Clip")
        notes_element = clip.find("Notes")
        notes_element[:] = []
        # Banjo/Koto are polyphonic plucked parts, not monophonic bass.
        cleaned = clean_notes(sources[name][0])
        source = sources[name][2][0]
        expected = []
        actual = []
        for n in cleaned.notes:
            times = np.array([ticks_to_seconds(n.start, source.ppq, source.tempo_map),
                              ticks_to_seconds(n.end, source.ppq, source.tempo_map)])
            b = beats_at(start_seconds + times)
            start, dur = round(float(b[0] - B0), 9), round(float(b[1] - b[0]), 9)
            ET.SubElement(notes_element, "Note", time=str(start), duration=str(dur),
                          key=str(n.pitch), channel="0", vel=f"{n.velocity / 127:.9f}", rel="0.787402")
            expected.extend(times)
            actual.extend(seconds_at(np.array([B0 + start, B0 + start + dur])) - start_seconds)
        if expected:
            max_timing_error = max(max_timing_error, float(np.max(abs(np.array(expected) - actual))))
        length = max(float(beats_at(np.array([start_seconds + duration - offset]))[0]) - B0,
                     max((float(n.get("time")) + float(n.get("duration")) for n in notes_element), default=0))
        for key in ("duration", "loopEnd"):
            clip.set(key, f"{length:.9f}")
        clip.set("name", name + " MIDI")
        st = dict(cleaned.stats, tracks_before=len(children), tracks_after=1)
        report["groups"].append(st)
        print(f"Cleaned {name}: {st['in']} -> {st['out']} notes", flush=True)

    # Clip slots referring to removed child/group tracks must go too.
    for parent in root.iter():
        for child in list(parent):
            if child.get("track") in removed_ids:
                parent.remove(child)
    for lane in audio_lanes:
        outer = lane.find("Clips/Clip")
        inner = outer.find("Clips/Clip")
        end_s = float(inner.get("playStop"))
        length = float(beats_at(np.array([start_seconds - offset + end_s]))[0]) - audio_beat
        outer.set("time", f"{audio_beat:.9f}")
        outer.set("duration", f"{length:.9f}")
        inner.set("duration", f"{length:.9f}")
    tempo = arrangement.find("TempoAutomation")
    if tempo is None:
        raise ValueError("Expected imported tempo automation")
    for c in list(tempo):
        if c.tag != "Target":
            tempo.remove(c)
    for b, t in pts:
        ET.SubElement(tempo, "RealPoint", value=f"{t:.6f}", time=f"{b:.6f}", interpolation="linear")
    root.find("Transport/Tempo").set("value", f"{pts[0][1]:.6f}")
    # Exported loop/marker times outside track lanes describe arrangement beats.
    # Preserve them: this task changes the grid, not the user's navigation.
    ids = [e.get("id") for e in root.iter() if e.get("id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate XML IDs")
    refs = {"track", "destination", "parameter", "content"}
    for e in root.iter():
        for k, v in e.attrib.items():
            if k in refs and v.startswith("id") and v not in ids:
                raise ValueError(f"Dangling reference {k}={v}")
    if max_timing_error > .000001:
        raise ValueError("Note remapping lost source timing precision")
    report["max_note_time_roundtrip_error_s"] = max_timing_error
    report["removed_terminal_cc7_lanes"] = True
    report["drum_anchors"] = len(drum_beats)
    report["limitations"] = ["Instrument consensus is not independent ground truth when stems share bleed.",
        "Bitwig import and listening still require user review.", "No vocals used as tempo anchors."]
    ET.indent(root, space="    ")
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item, xml if item.filename == "project.xml" else zin.read(item.filename))
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out) as zout:
        assert zout.testzip() is None
        report["unchanged_zip_entries"] = []
        for name in zin.namelist():
            if name != "project.xml":
                assert hashlib.sha256(zin.read(name)).digest() == hashlib.sha256(zout.read(name)).digest()
                report["unchanged_zip_entries"].append(name)
    report_path = work / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    drums, sr = audio_data[drum_name]
    click = render.click_track(pts, audio_beat, B0, last, len(drums), sr)
    mix = sum(y for y, s in audio_data.values() if s == sr) / 4
    sf.write(work / "Drums-and-grid.wav", np.clip(drums * .7 + click * .35, -1, 1), sr, subtype="PCM_24")
    sf.write(work / "All-stems-and-grid.wav", np.clip(mix * .7 + click * .35, -1, 1), sr, subtype="PCM_24")
    render.picture(sol, pts, np.array(cache["stems"][drum_name]["times"]), work / "Tempo-review.png", out.stem)
    for name in ("Drums-and-grid.wav", "All-stems-and-grid.wav", "Tempo-review.png"):
        print(f"Review {work / name}", flush=True)
    print(f"Written {out}\nReview {report_path}\nAnchor errors {report['anchor_error_ms']}\nAudio start beat {audio_beat:.9f}; musical start {B0:g}", flush=True)

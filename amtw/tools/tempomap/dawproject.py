"""Just enough DAWproject to read a tempo lane and audio clips and write a
tempo lane back.

DAWproject (the .dawproject Bitwig exports and opens) is a zip: project.xml
plus audio/ and plugins/. Its `<TempoAutomation unit="bpm" timeUnit="beats">`
holds `<RealPoint value time interpolation="linear"/>` entries — a linear
ramp between points — which is the thing a standard MIDI file cannot carry
and the reason this tool writes DAWproject instead of MIDI.

Editing is string surgery on project.xml rather than an XML round-trip: a
parser would reserialise every attribute and self-closing tag its own way
across 160 kB of plugin state we do not understand, and the only parts we
change are one automation block and some clip durations. Every other zip
entry is copied byte for byte.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

_POINT = re.compile(r'<RealPoint\s+value="([-\d.eE+]+)"\s+interpolation="(\w+)"\s+time="([-\d.eE+]+)"\s*/>')
_CLIP_OPEN = re.compile(r'<Clip\s[^>]*>')
_ATTR = re.compile(r'(\w+)="([^"]*)"')


@dataclass
class AudioClip:
    track: str           # track name the lane belongs to
    path: str            # zip entry, e.g. audio/foo.wav
    time: float          # arrangement position, beats
    duration: float      # arrangement length, beats
    play_start: float    # seconds into the file
    play_stop: float     # seconds into the file
    span: tuple[int, int]  # character span of the OUTER <Clip ...> tag in project.xml


@dataclass
class Project:
    path: Path
    xml: str
    tempo: float
    tempo_points: list[tuple[float, float]]       # (beat, bpm), sorted
    tempo_span: tuple[int, int] | None            # span of the <TempoAutomation> element
    clips: list[AudioClip] = field(default_factory=list)

    def read_audio(self, entry: str) -> tuple:
        import soundfile as sf
        with zipfile.ZipFile(self.path) as z:
            data, sr = sf.read(io.BytesIO(z.read(entry)), always_2d=True, dtype="float32")
        return data, sr


def _attrs(tag: str) -> dict[str, str]:
    return dict(_ATTR.findall(tag))


def load(path: str | Path) -> Project:
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        xml = z.read("project.xml").decode("utf-8")

    m = re.search(r'<Tempo\s[^>]*value="([\d.]+)"', xml)
    tempo = float(m.group(1)) if m else 120.0

    points: list[tuple[float, float]] = []
    span = None
    i = xml.find("<TempoAutomation")
    if i >= 0:
        j = xml.find("</TempoAutomation>", i) + len("</TempoAutomation>")
        span = (i, j)
        for v, _interp, t in _POINT.findall(xml[i:j]):
            points.append((float(t), float(v)))
        points.sort()

    # track names by id, so a clip can say which track it is on
    names = {m.group(2): m.group(1) for m in
             re.finditer(r'<Track\s[^>]*name="([^"]*)"[^>]*id="(id\d+)"', xml)}
    names.update({m.group(1): m.group(2) for m in
                  re.finditer(r'<Track\s[^>]*id="(id\d+)"[^>]*name="([^"]*)"', xml)})

    clips: list[AudioClip] = []
    arr = xml.find("<Arrangement")
    for lane in re.finditer(r'<Lanes\s+track="(id\d+)"[^>]*>', xml[arr:]):
        track = names.get(lane.group(1), lane.group(1))
        start = arr + lane.end()
        end = xml.find("</Lanes>", start)
        body = xml[start:end]
        # outer clips carry time/duration in beats; the nested clip carries the
        # file and its play range in seconds
        for oc in _CLIP_OPEN.finditer(body):
            a = _attrs(oc.group(0))
            if "contentTimeUnit" in a:
                continue                      # that is an inner clip
            inner_start = oc.end()
            inner = _CLIP_OPEN.search(body, inner_start)
            if not inner:
                continue
            ia = _attrs(inner.group(0))
            if ia.get("contentTimeUnit") != "seconds":
                continue
            f = re.search(r'<File\s+path="([^"]*)"', body[inner.end(): inner.end() + 2000])
            if not f:
                continue
            clips.append(AudioClip(
                track=track, path=f.group(1),
                time=float(a.get("time", 0)), duration=float(a.get("duration", 0)),
                play_start=float(ia.get("playStart", 0)), play_stop=float(ia.get("playStop", 0)),
                span=(start + oc.start(), start + oc.end()),
            ))
    return Project(path, xml, tempo, points, span, clips)


def tempo_block(points: list[tuple[float, float]], target_id: str, own_id: str) -> str:
    lines = [f'<TempoAutomation unit="bpm" timeUnit="beats" id="{own_id}">',
             f'            <Target parameter="{target_id}"/>']
    for beat, bpm in points:
        lines.append(f'            <RealPoint value="{bpm:.6f}" interpolation="linear" time="{beat:.6f}"/>')
    lines.append('        </TempoAutomation>')
    return "\n".join(lines)


def _element_end(xml: str, start: int, tag: str) -> int:
    """Index just past the </tag> that closes the element opening at start,
    counting nested elements of the same tag."""
    depth = 0
    i = start
    open_re = re.compile(rf"<{tag}[\s>]")
    close = f"</{tag}>"
    while True:
        o = open_re.search(xml, i)
        c = xml.find(close, i)
        if c < 0:
            raise ValueError(f"unclosed <{tag}> at {start}")
        if o and o.start() < c:
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c + len(close)
            if depth == 0:
                return i


def strip_audio(xml: str) -> str:
    """Remove every arrangement clip that plays an audio file, leaving the
    tracks themselves (empty) and everything else untouched. For the
    'light' project: tempo lane + note clips, no 270 MB of wav."""
    out = xml
    while True:
        a = out.find("<Audio ")
        if a < 0:
            return out
        # walk outward to the outermost <Clip that contains this <Audio
        outer = None
        pos = out.rfind("<Clip ", 0, a)
        while pos >= 0:
            if _element_end(out, pos, "Clip") > a:
                outer = pos
            pos = out.rfind("<Clip ", 0, pos)
        if outer is None:
            raise ValueError("<Audio> outside any <Clip>")
        end = _element_end(out, outer, "Clip")
        ls = out.rfind("\n", 0, outer)      # eat the line the clip sat on
        out = out[:ls] + out[end:]


def write(project: Project, out: Path, points: list[tuple[float, float]],
          clip_durations: dict[int, float] | None = None, light: bool = False) -> Path:
    """Write a copy of the project with a new tempo lane (and, optionally,
    new outer durations for audio clips keyed by clip index). `light` drops
    the audio clips and the audio/ entries — tempo lane and note tracks only."""
    xml = project.xml
    tid = re.search(r'<Tempo\s[^>]*id="(id\d+)"', xml).group(1)

    edits: list[tuple[int, int, str]] = []
    if project.tempo_span:
        old = xml[project.tempo_span[0]: project.tempo_span[1]]
        own = re.search(r'id="(id\d+)"', old).group(1)
        edits.append((*project.tempo_span, tempo_block(points, tid, own)))
    else:
        # no lane yet: put one right after the arrangement's top-level Lanes
        # close, with an id that cannot collide
        ids = [int(x) for x in re.findall(r'id="id(\d+)"', xml)]
        own = f"id{max(ids) + 1}"
        anchor = xml.rfind("</Lanes>", 0, xml.find("</Arrangement>")) + len("</Lanes>")
        edits.append((anchor, anchor, "\n        " + tempo_block(points, tid, own)))

    for idx, dur in (clip_durations or {}).items():
        a, b = project.clips[idx].span
        tag = re.sub(r'duration="[^"]*"', f'duration="{dur:.6f}"', xml[a:b], count=1)
        edits.append((a, b, tag))

    for a, b, rep in sorted(edits, key=lambda e: e[0], reverse=True):
        xml = xml[:a] + rep + xml[b:]
    if light:
        xml = strip_audio(xml)

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(project.path) as zin, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "project.xml":
                zout.writestr(item, xml.encode("utf-8"))
            elif light and item.filename.startswith("audio/"):
                continue
            else:
                zout.writestr(item, zin.read(item.filename))
    return out

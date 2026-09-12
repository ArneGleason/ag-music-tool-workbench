"""Write a DAWproject from scratch: tempo lane, note tracks with per-note
pitch curves, empty audio tracks to drop stems into.

The shape copies what Bitwig itself exports (two of the user's projects were
the reference), attribute for attribute, because a DAW is far more forgiving
of a file that looks like its own than of one that merely satisfies the
schema. Things kept for that reason and no other: a Master track with a
`role="master"` channel that every track's channel points at, Mute/Pan/
Volume parameters on every channel, a Scene with a ClipSlot per track, and
the `vel`/`rel` normalised 0–1 on notes.

Per-note pitch is `<Points unit="semitones"><Target expression="transpose"/>`
inside the `<Note>`, times in beats from the note start — exactly what
Bitwig wrote for the user's hand-drawn note expressions.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape


@dataclass
class PNote:
    time: float            # beats from clip start
    duration: float        # beats
    key: int
    velocity: int          # 1..127
    bend: list[tuple[float, float]] = field(default_factory=list)   # (beats from note start, semitones)


@dataclass
class NoteTrack:
    name: str
    clip_time: float       # arrangement beat
    notes: list[PNote]
    color: str = "#d99d10"


@dataclass
class AudioTrack:
    name: str
    color: str = "#3c8fd9"


class _Ids:
    def __init__(self):
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"id{self.n}"


def _channel(ids: _Ids, role: str, dest: str | None, volume: float = 0.5) -> tuple[str, str]:
    cid = ids()
    dest_attr = f' destination="{dest}"' if dest else ""
    x = (f'            <Channel audioChannels="2"{dest_attr} role="{role}" solo="false" id="{cid}">\n'
         f'                <Mute value="false" id="{ids()}" name="Mute"/>\n'
         f'                <Pan max="1.000000" min="0.000000" unit="normalized" value="0.500000" id="{ids()}" name="Pan"/>\n'
         f'                <Volume max="2.000000" min="0.000000" unit="linear" value="{volume:.6f}" id="{ids()}" name="Volume"/>\n'
         f'            </Channel>\n')
    return cid, x


def build_xml(tempo: float, tempo_points: list[tuple[float, float]],
              note_tracks: list[NoteTrack], audio_tracks: list[AudioTrack],
              app: str = "AG Music Tool Workbench") -> str:
    ids = _Ids()
    tempo_id, ts_id = ids(), ids()
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<Project version="1.0">',
           f'    <Application name="{escape(app)}" version="0"/>',
           '    <Transport>',
           f'        <Tempo max="666.000000" min="20.000000" unit="bpm" value="{tempo:.6f}" id="{tempo_id}" name="Tempo"/>',
           f'        <TimeSignature denominator="4" numerator="4" id="{ts_id}" name="Time Signature"/>',
           '    </Transport>',
           '    <Structure>']

    master_track, (master_ch, master_xml) = ids(), _channel(ids, "master", None, 1.0)
    track_ids: list[tuple[str, str]] = []          # (track id, kind)
    body: list[str] = []
    for t in note_tracks:
        tid = ids()
        cid, cx = _channel(ids, "regular", master_ch)
        body.append(f'        <Track contentType="notes" loaded="true" id="{tid}" name="{escape(t.name)}" '
                    f'color="{t.color}" comment="">\n{cx}        </Track>')
        track_ids.append((tid, "notes"))
    for t in audio_tracks:
        tid = ids()
        cid, cx = _channel(ids, "regular", master_ch)
        body.append(f'        <Track contentType="audio" loaded="true" id="{tid}" name="{escape(t.name)}" '
                    f'color="{t.color}" comment="">\n{cx}        </Track>')
        track_ids.append((tid, "audio"))
    body.append(f'        <Track contentType="audio notes" loaded="true" id="{master_track}" name="Master" comment="">\n'
                f'{master_xml}        </Track>')
    out.extend(body)
    out.append('    </Structure>')

    # arrangement
    out.append(f'    <Arrangement id="{ids()}">')
    out.append(f'        <Lanes timeUnit="beats" id="{ids()}">')
    for (tid, kind), t in zip(track_ids, note_tracks + audio_tracks):
        out.append(f'            <Lanes track="{tid}" id="{ids()}">')
        if kind == "notes" and t.notes:
            end = max(n.time + n.duration for n in t.notes)
            dur = float(int(end / 4 + 1) * 4)           # to the next bar
            out.append(f'                <Clips id="{ids()}">')
            out.append(f'                    <Clip time="{t.clip_time:.6f}" duration="{dur:.6f}" playStart="0.0" '
                       f'loopStart="0.0" loopEnd="{dur:.6f}" enable="true" name="{escape(t.name)}">')
            out.append(f'                        <Notes id="{ids()}">')
            for n in t.notes:
                vel = max(1, min(127, n.velocity)) / 127.0
                head = (f'                            <Note time="{n.time:.6f}" duration="{n.duration:.6f}" '
                        f'channel="0" key="{n.key}" vel="{vel:.6f}" rel="0.787402"')
                if n.bend:
                    out.append(head + '>')
                    out.append(f'                                <Points unit="semitones" id="{ids()}">')
                    out.append('                                    <Target expression="transpose"/>')
                    for bt, st in n.bend:
                        out.append(f'                                    <RealPoint value="{st:.6f}" '
                                   f'interpolation="linear" time="{bt:.6f}"/>')
                    out.append('                                </Points>')
                    out.append('                            </Note>')
                else:
                    out.append(head + '/>')
            out.append('                        </Notes>')
            out.append('                    </Clip>')
            out.append('                </Clips>')
        else:
            out.append(f'                <Clips id="{ids()}"/>')
        out.append('            </Lanes>')
    out.append('        </Lanes>')
    out.append(f'        <TempoAutomation unit="bpm" timeUnit="beats" id="{ids()}">')
    out.append(f'            <Target parameter="{tempo_id}"/>')
    for beat, bpm in tempo_points:
        out.append(f'            <RealPoint value="{bpm:.6f}" interpolation="linear" time="{beat:.6f}"/>')
    out.append('        </TempoAutomation>')
    out.append('    </Arrangement>')

    out.append('    <Scenes>')
    out.append(f'        <Scene id="{ids()}" name="Scene 1" comment="">')
    out.append(f'            <Lanes id="{ids()}">')
    for tid, _ in track_ids:
        out.append(f'                <ClipSlot hasStop="true" track="{tid}" id="{ids()}"/>')
    out.append('            </Lanes>')
    out.append('        </Scene>')
    out.append('    </Scenes>')
    out.append('</Project>')
    return "\n".join(out) + "\n"


_METADATA = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<MetaData>
    <Title>{title}</Title>
    <Artist></Artist>
    <Album></Album>
    <OriginalArtist></OriginalArtist>
    <Songwriter></Songwriter>
    <Producer></Producer>
    <Year></Year>
    <Genre></Genre>
    <Copyright></Copyright>
    <Comment>{comment}</Comment>
</MetaData>
"""


def write(path: Path, xml: str, title: str, comment: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("metadata.xml", _METADATA.format(title=escape(title), comment=escape(comment)))
        z.writestr("project.xml", xml)
    return path

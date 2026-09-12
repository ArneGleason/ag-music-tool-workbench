# MonstersUndone checkpoint — 2026-09-12

## Resume here

Arne is stopping this session with the stem work complete for his current needs.
He made further setup changes after the drum import, saved the native Bitwig
project and closed it. Those latest user changes are authoritative: reopen the
native project, not an earlier DAWproject export or an earlier mixer snapshot.
No further stem processing is planned unless requested.

Next: creative overdubs, then a music video using the music visualizer approach
developed for **Rivers of Mars**, adapted to the monster theme. This is future
direction, not a request to start production during this checkpoint.

## Project and resources

- Native project:
  `C:\Users\arneg\OneDrive\Documents\Bitwig Studio\Projects\MonstersUndone.cleaned-groove\MonstersUndone.cleaned-groove.bwproject`
- File observed at checkpoint: modified 2026-09-12 13:13:49 local time,
  1,650,075 bytes. Not reopened or modified for this checkpoint.
- Canonical tool repository: `C:\code\github\ag-music-tool-workbench`.
- GitHub: `https://github.com/ArneGleason/ag-music-tool-workbench`.
- Shared models, environments and render jobs: `C:\audio\shared\amtw-runtime`.
- Original Suno assets: Downloads / `Set the Monsters Loose Stems`.

GitHub holds code, documentation and reproducibility notes. The Bitwig project,
audio and model weights remain outside Git; this checkpoint does not claim a
GitHub backup of those large files or verification of OneDrive cloud sync.

## Completed and accepted

- MIDI consolidation/cleanup and groove-following tempo map were imported and
  auditioned successfully by Arne. Preserve this timing setup for overdubs.
- Full Renaissance lead and backing vocals were accepted as cleaner starting
  stems. Removal of doubling/effects is welcome; Arne can create those himself.
  Originals were retained and muted. No full Apollo vocal pass was needed.
- Drum separation and Apollo comparisons were auditioned. Keep untreated kick,
  snare and percussion/toms; use Apollo for hi-hat/shaker. Snare Apollo lost
  preferred presence. Hi-hat Apollo reduced distracting scratchiness despite
  softened shaker texture. A real shaker may be added later.
- Six full-length drum files were imported into a Drums group under Group 9.
  At delivery, original drums and optional ride/crash were muted; the four chosen
  parts were active. These are delivery settings, not instructions to reset
  Arne's subsequent mixer edits.
- All six clips were checked together for the original 4.4.3.47 start, zero
  source offset, Raw playback, looping off and full duration. Native Save and
  Collect and Save completed, with all six collected WAV hashes matching renders.
- Full render job: `jobs/drum-full-20260912-115537-f239de`. Retains untreated
  parts, delivery files and provenance manifest. Apollo processed padded active
  hi-hat regions with context, preserving skipped quiet audio rather than gating.

## Reusable work and verification

The workbench includes Renaissance, drum separation auditions, Apollo drum
auditions and full drum delivery. A live Bitwig bridge supports track snapshots
and limited mixer/name actions; clip import still used native UI. Do not assume
the bridge can edit clips, notes or tempo envelopes. See [bridge docs](bitwig-live.md).

Code and delivery notes were pushed in `304da37`. This checkpoint adds the
stopping point and next creative direction. Doctor passed again at checkpoint;
no code changed and no audio was reprocessed.

Details: [measured findings](findings.md), [drum workflow](drum-audition.md),
[Renaissance workflow](renaissance-audition.md), [local layout](local-layout.md).

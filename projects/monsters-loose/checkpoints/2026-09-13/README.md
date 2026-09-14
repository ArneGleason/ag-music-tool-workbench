# Monsters Loose — end-of-day recovery point

Saved 2026-09-13. This is a recovery snapshot, not the active editing directory.
The active job is `C:\audio\shared\amtw-runtime\jobs\monsters-loose-word-timing-20260913`.
The active music project is `C:\Users\arneg\OneDrive\Documents\Bitwig Studio\Projects\MonstersUndone.cleaned-groove`.

## Where we stopped

The complete scene roughout v04 is rendered: 15 scenes, 31 unique stills, 32 holds
(the laboratory anchor returns after the burning-town cutaway), 5290 frames at
24 fps. Two stills per scene, three for scene 11's shrinking/growing/smoke sequence.
These are loose scene/action anchors, not finalized shots or generation start/end frames.
The user liked the scene inspiration and is stopping for the day.

Next: add notes on scenes, then explore shot coverage. Before investing in detailed
start/end-frame images, try a few scene images in the intended video generator
to learn what motion, style and identity continuity it can maintain. Earlier
discussion names Kling; the closing dictation says “Clay.” Confirm the provider
before initiating any generation there. No external video jobs or purchases
were authorized or started by this checkpoint operation.

Blender remains the assembly/render rig. All scenes are nighttime. The saved
MUCF master emblem and approved character references govern consistency.
New roughout monsters and sets remain provisional, not automatically approved.
See `job/animatic/README-scene-roughout-v04.md` for specific continuity gaps.

## Contents

- `job/assets`: all reference versions, source cover, scene stills, prompts,
  catalog approvals/review text, and review history. 50 assets / 65 versions.
- `job`: reconciled word/phrase timing, raw transcription provenance, lyric
  worksheet text, saved narrative and 40 active timeline notes, generation
  manifests and scripts. Browser-only unsaved drafts are not part of this snapshot.
- `job/animatic`: editable Blender files, measured timing/readout data, fonts
  and licenses, review pages, rebuild scripts, still previews and validation.
- `bitwig`: native project files and XML metadata extracted from the large
  DAWproject export, with a complete export member inventory.
- `manifest.json`: SHA-256 checksums for copied files and explicit exclusions.

Excluded: audio, rendered videos, the large audio-bearing DAWproject export,
model/runtime caches, render logs and redundant Blender autosaves. Nothing was
deleted from the active project. User reports the master backed up on SoundCloud
and music project in OneDrive; those external backups were not independently verified.
Native Bitwig files still require their separately backed-up audio/sample media.

## Recover

1. Clone this repository and follow `docs/local-layout.md` to restore the workbench
   runtime. Install Blender separately (this pass used 5.2.1 LTS).
2. Copy this checkpoint's `job` directory to a new, empty runtime job directory.
   Preserve its relative layout. Do not run historical `publish-*` scripts or
   initial transcription/preparation scripts over restored reviews and timings.
3. Restore the exact 220.387-second master WAV from the separate backup to
   `job/master.wav` and `job/animatic/master.wav`. The original master was
   `MonstersLoose 2026-09-12 2155.wav`, 48 kHz stereo, 24-bit. Re-export the locked
   Bitwig loop if necessary; a streaming/transcoded copy is not an exact WAV backup.
4. Open `job/animatic/MonstersLoose-scene-roughout-v04.blend`. Images and fonts
   are saved alongside/relative to the rig; relink the master if Blender requests it.
   Choose an output path in the restored job and render the animation. Existing
   timing/readout data allows this without re-running speech alignment.
5. From the repository run `amtw creative-notes <restored-job> --port 8742`
   with the configured runtime Python/launcher. Open
   `http://127.0.0.1:8742/animatic/notes-roughout.html` or the asset catalog.
   Recreate the named MP4 in `animatic` for browser playback.
6. To revise the image sequence, edit `rough-anchors-v04.json` in the restored
   job and use `animatic/build-rough-anchors.py`; it derives from the included
   native narrative v02 rig and applies current lyric text. Preserve a new version.

Validation at checkpoint: all catalog image versions present; copied files
hash-verified; workbench doctor passed. Blender audit verified continuous image
coverage through the last frame and unchanged audio timing. Full MP4 decoded
without errors. One in-app browser playback tab crashed; reopening restored
short phrase playback. No claim of complete acoustic/lip-sync verification.

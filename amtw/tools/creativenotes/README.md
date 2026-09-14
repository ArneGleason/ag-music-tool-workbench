# Listening notes

## Dictation

Click **Record dictation** beside the note field, allow the browser microphone
prompt, speak, then click **Stop and transcribe**. The song pauses and the note
anchor remains fixed. Whisper appends to existing text; review it and Save note.
Note switching and saving are blocked while recording/transcribing so text
cannot land in a different note. Cancel leaves the text unchanged. A failed
transcription retains the audio Blob in memory for Retry or Discard; closing or
reloading the page loses that recording, with a before-unload warning.

The same-origin `/api/dictation` endpoint accepts at most 25 MB and three minutes
of audio. It runs `dictate.py` in the existing vevo2 environment, using cached
`~/.cache/whisper/large-v3-turbo.pt`; nothing is sent to an external transcription
service. One transcription runs at a time. Uploaded audio and transcript files
live in a temporary runtime directory and are cleaned after success/failure.
The completed transcript is only a browser draft until the user saves the note.
The browser recording is released after successful transcription or discard.

Local Whisper and the handler were tested with a synthesized spoken sentence;
the returned text matched exactly. Silence was rejected and temporary cleanup
and lock release were verified. The actual user's microphone/permission flow
has not been activated during agent testing. If the in-app browser cannot access
the microphone, use the same localhost page in Chrome or Edge.

Launch **Video / Listen and mark creative notes** with the timing job directory.
The server installs its generated `animatic/notes.html` surface and prints its
localhost URL (default port 8742). Requires `timing.json`, plus the Blender
animatic folder's `animatic-data.json`, movie and poster. No new dependencies.

The website is a playback and annotation surface; Blender remains the video rig.
This first version targets the Monsters Loose output filenames. It does not
create shots, generate footage, edit the lyrics or alter the .blend.

- Click the timeline to seek; drag to select a range. Note at playhead or note
  on selection opens the editor. N makes a point note. Start/end fields allow
  approximate corrections; seconds are the canonical loose-note anchors, with
  the DAW bar/beat shown as context. Notes are not snapped production shot cues.
- Zoom is 1–32x and preserves the visible playhead position, or the viewport
  centre if the playhead is outside the visible range. Fit song/selection and a
  whole-song scroll slider provide escape routes. Playback follow never scrolls
  while paused. The canvas is viewport-sized even at maximum zoom.
- Space plays/pauses outside text fields. Phrase controls navigate and audition.
  Enter saves the note; Shift+Enter adds a line. Draft text is retained in local
  browser storage and recovered after a reload. Switching notes saves a nonempty
  dirty draft first; an unsuccessful save leaves the draft intact.
- Addressed notes disappear from the default list and timeline. Show addressed
  reveals them, their resolution notes and the Reopen action. There is no delete
  action. The original note is also recoverable through revision history.

`creative-notes.json` holds the project document with an integer revision.
`POST /api/notes` accepts same-origin JSON, validates times/state/IDs, refuses
missing prior IDs, detects stale revisions (409), snapshots the prior document
under `note-history/`, then atomically replaces the current file. The interface
reports save failures rather than claiming that a browser draft is a disk save.
`GET /api/notes` is uncached. Media uses the existing byte-range handler.

When consuming notes in later agent work, read the current document first.
Treat open notes as the working queue. Mark one addressed only after its
correction/direction is actually incorporated; retain the text and anchor and
record a concise resolution linking the changed artifact when useful. Merely
reading or acknowledging a note does not mean it has been addressed. Use the
revision-aware API for changes while the page is open; do not overwrite other
edits with a stale file snapshot. The broader production brief is separate from
this queue, in `animatic/production-direction.md`.

Validation used an isolated real-song test directory. UI checks cover saving a
phrase range, addressing, hidden default state after reload, showing addressed,
resolution retention, reopening, zoom and a dragged approximate range. API
checks cover stale writes, invalid bounds, attempts to remove notes and foreign
origins; rejected requests leave the document unchanged. Doctor passes.
# Asset references and reviews

The listening server also serves `/assets/assets.html`, linked from the notes
header. `assets/catalog.json` stores immutable asset/version identities, image
paths relative to the assets folder, exact prompts, source IDs and hashes.
Generation adds a new version; it must not overwrite an approved image or copy
approval to its replacement. Review states are awaiting_review, approved,
revise and parked. Source images are read-only references.

The browser submits only the selected ID/version, status, feedback and document
revision. The server validates these against the existing catalog, rejects stale
revisions and writes atomically with snapshots under `assets/history`. It does
not accept new image paths or change asset identity through the review endpoint.
Feedback drafts survive locally per asset/version until Save review; approving
uses the same save path. Dictation reuses `/api/dictation` and local Whisper.

Monsters Loose uses CHAR-001/v001 for the first zookeeper candidate and SRC-001
for the original cover reference. The 15 broad scenes have fixed SCN-001 through
SCN-015 IDs and can be opened via `notes-narrative.html?scene=SCN-006`.
Keep existing IDs when reordering or revising; assign new IDs for new subjects.
No shot records are invented before the shot planning stage. Blender is still
the animation/rendering rig; the web pages review its rendered previews.

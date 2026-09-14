# Performed-word alignment

Input is a reconciled performance JSON: `role`, optional `lyric_source`, and
`phrases` containing stable `id`, source-second `start`/`end`, `text`, optional
`kind` (`lyric`/`vocalization`), `text_status` (`needs_review`/`lyric_reconciled`),
`note`, and original recognition candidates. It is not the unadapted lyric sheet.

Uses existing vevo2 Python/torch/Whisper, plus an isolated alignment-only overlay
at runtime `tools/word-timing`: whisperx 3.8.6, pandas 2.2.3, nltk 3.9.2,
python-dateutil, six, click, pytz, tzdata. Installed with pip `--target --no-deps`
so no existing engine packages are upgraded. This is intentionally not a full
WhisperX ASR/diarization install. Full dependency metadata does not describe this
tested alignment-only route. Model: torchaudio WAV2VEC2_ASR_BASE_960H, under
runtime `models/word-timing`; punkt_tab also stays there.

The added dependencies supply acoustic word boundaries absent from ordinary
Whisper onset estimates. Results include word JSON/CSV, phrase VTT, Markdown
review, and an HTML audition page with a master-offset PCM16 vocal proxy.
The original audio remains untouched. HTML may be opened locally or served
from its output directory. Independent word ends, no grid snapping, no
interpolated missing words. Letter alignment is retained as diagnostic data;
it is not a phoneme/viseme track. All timing is provisional until listening.

Open **Analysis / Open vocal timing review** on the workbench and select the
result directory. CLI equivalent: `amtw word-timing-review RESULT_DIRECTORY`.
Serve a shared parent directory when lead/backing pages reference a common
master. The default localhost port is 8741. Byte-range responses are required
for reliable WAV seeking; a bare Python http.server restarted playback at zero
in the tested in-app browser. The server supports read-only local audition.

Optional `master_preview` in the performance JSON is a URL relative to the
output HTML. The review source selector preserves the master-relative clock.
The waveform-energy extent is a separate diagnostic, never a replacement word
edge: bleed, breath and reverb can extend it. A flag is a review cue, not proof
of error. Unresolved sound events use `kind: "unresolved_event"` and receive no
invented word tokens.

# Using the A/B listening tool (for an agent)

`amtw ab` is how listening verdicts get made in this repo. It plays several
supposedly-aligned audio files in lockstep and switches which one you hear by
crossfading gains, so toggling is instant and sample-aligned rather than a
stop-and-reload. Markers and verdicts save to JSON, which is what turns "it
sounds better" into data a later tool can read.

**You cannot hear anything. The user does the listening.** Your job is to
prepare a comparison worth their time, launch it, and read the JSON back.
[AGENTS.md](../AGENTS.md) rule 5 is the point of this tool: where a listening
verdict and a metric disagree, the verdict wins and the metric is suspect.

## Where things are

- Repo: `C:\code\github\ag-music-tool-workbench` (run commands from here)
- Launcher: `.\amtw.ps1 <command>` — wraps the `main` venv's python
- This tool: `amtw/tools/ab/` — `abtool.py` (server), `ab.html` (the whole UI)
- Notes land in `output/ab_notes/<timestamp>.json` unless you pass `--notes`
- Kept ground truth: `data/labels/` — promote a notes file here when it
  becomes a reference set, and see [findings.md](findings.md) for what has
  already been settled by ear

## Launching it

```powershell
cd "C:\code\github\ag-music-tool-workbench"
.\amtw.ps1 ab "path\to\a.wav" "path\to\b.wav" "path\to\c.wav"
```

It serves on `http://127.0.0.1:8731/` (change with `--port`), opens a browser,
and blocks until Ctrl+C. **Run it in the background** if you want to keep
working — it is a server, not a batch job. It is also on the workbench UI
(group "Listening", `background=True`), which is how the user usually starts
it.

`--notes <path>` writes verdicts to a file you choose. Use it when you want to
read the result back at a known path.

## Preparing a comparison — the part that is actually your job

1. **Files must be time-aligned and the same length.** The tool assumes
   sample alignment; it does not stretch or shift. Different sample rates are
   fine for playback, but the durations must match or the comparison drifts.
2. **Give them distinct filenames.** Verdicts are keyed by full path (a bug
   where two files both called `adaptive.wav` merged their verdicts is fixed),
   but the UI is far easier to read when names differ. Copy stage outputs into
   one folder with names like `1_source.wav`, `2_apollo_only.wav`.
3. **Order matters**: put the reference/original first, then variants.
   Keyboard `1`–`9` select by position.
4. **Include the "what was removed" file when a model subtracts something.**
   The single most decisive check in this repo's history was listening to the
   `(Reverb)` stem a de-reverb pass wrote out — recognisable singing in it
   means a voice was eaten. A null/residual file beats any metric.
5. **Two to five files.** More than that and the user cannot hold them in
   their head.
6. **Tell the user where to listen.** Give timestamps ("jump to 112 s and
   136 s") rather than "have a listen".

## Controls to quote to the user

| key | action |
|---|---|
| Space | play / pause |
| `1`–`9` | switch to that track (instant, gain-crossfaded) |
| `←` / `→` | seek ∓5 s |
| `[` / `]` | set loop start / end |
| `\` | clear the loop |
| `M` | drop a point marker at the playhead |
| `S` | mark the current loop region as a **span** |
| `E` | open the markdown export (paste-ready summary) |

Checkboxes: **match loudness** (on by default — files can differ several dB
and the louder one just "wins" without it) and **blind** (randomises the
order and hides names; a Reveal button un-hides). Both states are recorded in
the exported markdown, which matters when reading a verdict later.

## Reading the result

Notes save automatically ~0.4 s after any edit. The JSON:

```json
{
  "session": "2026-08-23T…",
  "files": [{ "name": "1_source.wav", "path": "C:\\…\\1_source.wav" }],
  "verdicts": { "C:\\…\\1_source.wav": "boxy in the chorus" },
  "markers": [
    { "t": 112.4, "track": 2, "trackName": "3_dereverb.wav", "text": "harmony gone" },
    { "t": 130.0, "t_end": 134.5, "track": 0, "trackName": "1_source.wav", "text": "scratchy" }
  ]
}
```

- `verdicts` is keyed by **full path** (old files may use the basename; the UI
  falls back to that, so keep both in mind when parsing).
- A marker with `t_end` is a span; without it, a point. `amtw harmonic
  --from-notes` treats a point as a 0.3 s span.

**Marked spans beat any detector here.** The fry detector maxes at AUC 0.755
(~17% precision at any threshold); processing only the user's own marked
spans gave 87% of the track untouched, 100% recall, 98% precision. So a tool
that needs to know *where* should read a notes file rather than detect.

## Gotchas that have cost time

- **Never inject test data into a live session.** POSTing to `/api/notes`
  while the page is open clobbers in-memory verdicts, and the page will
  re-save over your file. Wait until the user is done.
- Verdicts and markers were once keyed by basename, silently merging two
  different files with the same name. Fixed, but still prefer distinct names.
- The server writes the whole notes file on every save; treat it as
  read-mostly from your side.
- Loudness matching is **on** by default. A verdict recorded with it off means
  something different — the export records which.

## After a verdict

Write what the user said into [docs/findings.md](findings.md), in their own
words where possible, including negative results. That file exists because
re-running a settled experiment is the most common way a session here is
wasted. If a listening result overturns a finding, edit the entry — do not
quietly contradict it.

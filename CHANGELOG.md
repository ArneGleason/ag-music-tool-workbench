# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning is [semantic](https://semver.org/spec/v2.0.0.html). Every change
should land with its own entry under `[Unreleased]` — that's how the next
session finds out what moved.

## [Unreleased]

### Added
- **`harm-read` — harmonic readout for music written as independent lines.**
  New `Harmony` group. Reads a MIDI file whose tracks are voices and reports,
  per bar, the chord those lines make, *every* major key that still contains
  it, and — the part no chord symbol shows — which single voice is narrowing
  that set. It never suggests a next chord; it says what the lines already made
  and what it is still free to become.

  Query flags, which is where the value actually is: `--together F B` (is the
  key-defining tritone ever *held*, or only crossed in passing — duration is
  reported, because a 0.01-beat overlap is a note-boundary artifact),
  `--where B` (where the leading tone actually lives), `--pivots-from N`
  (which single semitone move relocates a bar into another key), `--tonic C`
  (read the fitting collections back as modes), `--bars` / `--voices` to scope
  it, and `--json` for a visualiser to consume.
- **`harm-map`** — the foundation view. Writes a self-contained HTML page: one
  timeline with every defensible reading of each bar, the key-fit ribbon, and
  a roman-numeral row that rewrites itself from readings you pin. The lens
  selector (most complete / rooted on the bass / root must be sounding /
  functional in the tonic) **reorders** readings and never removes one.
- **`readings()` replaces single-answer chord naming.** A bar now yields every
  defensible interpretation, each declaring which notes it claims as chord
  tones and which it leaves over — because the leftovers are where colour,
  pedals, anticipation and passing motion live. C-D-F-G-B♭ is C11 *and* Gm7
  with C underneath *and* B♭6 with C as an added 9th; the tool lists all three
  rather than letting a bass tie-break decide. `readings_without_voice()` adds
  the lens the bass usually needs: how the bar reads if that line is *not* a
  chord tone. `interpretive_spread()` counts distinct roots among the
  best-explaining readings — a fork worth looking at, and orthogonal to key
  ambiguity.
- **`texts` field type** — a space-separated list of strings, so a tool can
  take `--together F B`. The vocabulary had `ints` and `floats` but no string
  equivalent.

### Changed
- **A tool is now one folder, discovered automatically.** Each package under
  `amtw/tools/` exports `TOOL` (or `TOOLS`); `amtw/registry.py` walks the
  directory and collects them. Adding a tool no longer means editing a central
  catalog or `cli.py` — drop the folder in and it appears on the bench and in
  `--help`.
- **One declaration drives both the form and the CLI.** `amtw/spec.py` turns a
  tool's `fields` into argparse subparsers as well as workbench widgets, so the
  two can no longer disagree. `cli.py` shrank from 488 lines of hand-written
  argparse to 32; only `workbench` is still declared by hand, because it is the
  bench rather than a tool on it.
- **Package split into `core/`, `bench/` and `tools/`.** `core/` holds the
  shared infrastructure (paths, audio IO, job dirs, config, report), `bench/`
  the server and its page, `tools/` one folder per tool. The restore pipeline's
  `stages/` moved under `tools/run/`, where they are used.
- **Extracted `core/dsp.py`.** The STFT/periodicity primitives were living in
  `defizz.py`, so `harmonic`, `detect` and `remod` were importing private
  helpers out of a sibling tool. They are shared vocabulary, not de-fizz's.

### Added
- **`tests/test_roundtrip.py`** — drives every registered tool through
  form-values → argv → argparse, checks required fields raise `ValueError`
  rather than an argparse trace, and checks tool names are unique. Doubles as
  its own runner, so pytest is not a dependency.

### Fixed
- **Starting the workbench twice no longer breaks it.** `allow_reuse_address`
  is on by default, so on Windows a second instance silently bound the same
  port and the two answered unpredictably. It is now off, and a failed bind is
  handled: if a workbench is already there, the browser opens onto it and the
  second instance exits 0; if something else holds the port, you get the reason
  and a suggested `--port`.
- **`Workbench.cmd` no longer starts minimised.** Any startup failure scrolled
  past inside a hidden window, so a double-click that failed looked identical to
  one that did nothing.
- **`detect --marks` now reaches the workbench.** It existed only in the CLI, so
  the bench never offered it — the exact drift the single declaration prevents.
- **`PROJECT_ROOT` no longer depends on a parent count that a file move can
  break.** Moving `paths.py` into `core/` silently repointed it at `amtw/`, and
  every tool the bench launched died with "No module named amtw". Now anchored
  with `parents[2]` and commented.

## [0.3.0] — 2026-07-26

Renamed the project and set it up to be worked on by more than one person.

### Changed
- **Renamed to AG Music Tool Workbench.** Python package `vsr` → `amtw`,
  launcher `vsr.ps1` → `amtw.ps1`. The project is a workbench with tools under
  it, not a single-purpose vocal pipeline.
- The runtime root stays at `%LOCALAPPDATA%\VocalStemRegen` deliberately: four
  venvs have absolute paths baked into their own scripts, so renaming it would
  mean a full re-setup and several GB of re-downloads. `AMTW_RUNTIME` overrides
  it; `VSR_RUNTIME` still works.

### Added
- `AGENTS.md`, `CONTRIBUTING.md`, `docs/adding-a-tool.md`,
  `docs/architecture.md`, and `docs/findings.md` — the last of these collects
  every settled measurement and dead end so they don't get re-run.
- `data/labels/pockets_fry_segments.json` — the 16 ground-truth listening labels
  the fry detector work rests on, committed as a fixture.
- MIT license.

### Deprecated
- `vsr.ps1` still works and forwards to `amtw.ps1` with a warning.

## [0.2.0] — 2026-07-26

The workbench, and the first tool that isn't about audio.

### Added
- **`amtw workbench`** — a local web UI listing every tool with real widgets,
  running them as subprocesses and streaming output back. Results the tool
  produced become clickable chips. Recent runs are re-openable. Last-used values
  persist per tool. Stdlib `http.server`, one HTML file, no build step.
- **`amtw/tools.py`** — declarative tool catalog. Field declarations become
  widgets and then argv; there is no per-tool UI code, so adding a tool to the
  bench is one entry.
- **`Workbench.cmd`** — double-click launcher, the intended entry point.
- **`amtw midi-merge`** — merges duplicate stem-to-MIDI tracks into one track
  with no same-pitch overlaps. Same-pitch notes starting within `--dup` collapse
  (longest tail wins); a later one beyond `--dup` truncates the held note and
  inherits its tail. Handles the illegal key signatures these exports contain,
  and re-times in seconds when two files' tempo maps disagree.
- **`amtw midi-inspect`** — lists a MIDI file's tracks, note counts and ranges.
  The workbench form uses it to show real track choices instead of asking for
  indices.
- `mido` added to the `main` venv.

## [0.1.0] — 2026-07-25

The vocal stem restoration pipeline, as it stood before the rename. Recorded
from git-less history, so this entry is a summary rather than a full log.

### Added
- Staged pipeline: ffmpeg decode → UVR de-reverb cleanup → Apollo spectral
  restoration → seed-vc re-synthesis → loudness match, with a per-job HTML
  report comparing every stage.
- `amtw ab` — lockstep, loudness-matched, optionally blind A/B listening tool.
  Marks and verdicts save as JSON that other tools consume.
- `amtw harmonic` — fry-scrape repair; the first mechanism to pass a listening
  test. `--adaptive` scales strength with severity; `--from-notes` restricts
  processing to user-marked spans and leaves everything else bit-identical.
- `amtw detect` — plots fry-detector features against your marks.
- `amtw defizz`, `amtw remod` — two further fry mechanisms, both still unproven.
- `amtw doctor` — venv, CUDA, clone and checkpoint checks.
- `scripts/setup_runtime.ps1` — rebuilds all four venvs and downloads
  checkpoints; safe to re-run.

[Unreleased]: https://github.com/ArneGleason/ag-music-tool-workbench/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ArneGleason/ag-music-tool-workbench/releases/tag/v0.3.0
[0.2.0]: https://github.com/ArneGleason/ag-music-tool-workbench/releases/tag/v0.2.0
[0.1.0]: https://github.com/ArneGleason/ag-music-tool-workbench/releases/tag/v0.1.0

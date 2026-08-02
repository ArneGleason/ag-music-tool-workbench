# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning is [semantic](https://semver.org/spec/v2.0.0.html). Every change
should land with its own entry under `[Unreleased]` — that's how the next
session finds out what moved.

## [Unreleased]

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

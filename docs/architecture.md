# Architecture

## The two-folder split

**The project folder** (this repo) holds code, `input/`, and `output/` job dirs.
It is OneDrive-synced on the author's machine.

**The runtime root** — `%LOCALAPPDATA%\VocalStemRegen` — holds everything heavy
and regenerable: virtualenvs, model checkpoints, third-party clones, the
HuggingFace cache. Override with `AMTW_RUNTIME`.

This split is load-bearing, not tidiness. Model weights are gigabytes, and a
sync client trying to upload them mid-install locks files and corrupts venvs.
**Never write weights or working audio into the project folder.**

The runtime folder kept its old `VocalStemRegen` name through the rename to
`amtw`, because four venvs have their absolute paths baked into their own
scripts. Renaming it means a full re-setup and several GB of re-downloads for
zero functional gain.

## Four virtualenvs

Engine dependencies genuinely conflict:

| venv | holds | pins |
|---|---|---|
| `main` | orchestrator, audio-separator, workbench, MIDI | torch 2.11+cu128 |
| `msst` | Apollo vocal enhancer host | torch 2.6, numpy ≥2 |
| `seedvc` | seed-vc voice conversion | torch 2.4.0, numpy 1.26.4, transformers 4.46.3 |
| `ymsvc` | YingMusic-SVC | as seedvc + extras |

seed-vc pins numpy 1.26 while MSST wants numpy ≥2 — irreconcilable in one env.
So **stages talk over wav files and subprocesses**, never shared imports, and
each engine gets exactly the environment it wants. Any new tool needing an
incompatible dependency set should follow the same pattern rather than forcing
a resolution.

All four are system Python 3.12. `scripts/setup_runtime.ps1` rebuilds the lot
and is safe to re-run.

Two install gotchas encoded in that script:

- `audio-separator` silently replaces CUDA torch with a CPU build from PyPI.
  Torch must be force-reinstalled from the CUDA index **after** it.
- seed-vc is installed with **filtered** dependencies — no resemblyzer, jiwer,
  gradio, FreeSimpleGUI, or sounddevice. Those are eval/UI only, and
  resemblyzer's `webrtcvad` has no Python 3.12 wheels.

## The workbench

```
browser ──HTTP──> workbench.py ──subprocess──> python -m amtw <tool> ...
                       │
                       ├── /api/catalog     tools.py, serialised
                       ├── /api/browse      file picker, root-restricted
                       ├── /api/run         spawn, then poll for output
                       └── /file            serve a result
```

`http.server` from the stdlib, bound to `127.0.0.1`, one hand-written HTML file,
no build step and no npm. This is deliberate: the thing has to still start in
two years without a toolchain having rotted.

**The UI never bypasses the CLI.** It builds an argv and runs
`python -m amtw ...` as a subprocess, streaming stdout back. So anything the UI
can do is reproducible by hand, the console shows the exact command, and the CLI
stays the single source of truth for behaviour.

`tools.py` is the only place a tool is described. Field declarations become
widgets and then argv; there is no per-tool UI code. See
[adding-a-tool.md](adding-a-tool.md).

**Path safety:** the file browser and `/file` are restricted to a fixed set of
roots (`input`, `output`, `project`, Downloads, Music, Desktop), plus any file a
tool in the current session actually produced. Everything else is refused. The
server binds localhost only.

## The vocal restoration pipeline

| # | stage | engine | venv | what it does |
|---|---|---|---|---|
| 00 | input | ffmpeg | — | decode to 44.1k wav |
| 10 | cleanup | UVR DeEcho-DeReverb via audio-separator | `main` | strip baked-in reverb so later stages see a dry vocal |
| 20 | superres | Apollo vocal enhancer (Lew, ep54) via MSST | `msst` | generative spectral restoration of codec/separation mush |
| 30 | resynth | seed-vc f0-conditioned singing model | `seedvc` | re-synthesis; timbre self-cloned from the stem |
| 40 | final | pyloudnorm | `main` | loudness-match to the original |

Every stage's output stays in the job dir and is compared in
`report/report.html` — spectrograms including a 4 kHz+ artifact-zone zoom, LUFS,
inline players.

Stage 30 is **off by the evidence**; see [findings.md](findings.md). The
restoration-only path (`--stages cleanup,superres`) is what actually ships.

## A/B listening

`amtw ab` serves N supposedly-aligned files to a page that plays them all in
lockstep and switches which one you hear by crossfading gains — so toggling is
instant and sample-aligned, not a stop-and-reload. Loudness-matched by default
(files can differ ~9 dB, which otherwise decides the verdict for you), with a
blind mode.

Marks and verdicts save to `output/ab_notes/<timestamp>.json`. **This is the
project's data-collection mechanism**: listening verdicts become structured data
that `harmonic --from-notes` and `detect --from-notes` consume directly.

Bug worth remembering: verdicts were once keyed by file *basename*, so two files
both called `adaptive.wav` from different run folders silently merged their
verdicts. Keys are full paths now.

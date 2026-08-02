# AG Music Tool Workbench

A local workbench for music-production tools you'd otherwise have to remember
command lines for. Double-click one file, get a browser page listing every tool
with real widgets — file pickers, sliders, checkboxes — that runs the tool and
streams its output back.

The tools that ship with it solve two problems in AI-generated music:
**restoring rough vocal stems**, and **repairing broken stem-to-MIDI exports**.
Nothing about the workbench is specific to either; it's a bench, and tools go
under it.

> Windows-only today (PowerShell launchers, CUDA paths). The Python is portable;
> nobody has done the porting.

## Quick start

```powershell
# one time: build the runtime (venvs, model checkpoints, third-party clones)
.\scripts\setup_runtime.ps1

# then, forever after
.\Workbench.cmd
```

`Workbench.cmd` opens a console window — that window *is* the server,
so close it to stop — and the page at <http://127.0.0.1:8730>.

Everything is runnable by hand too; the UI just builds these command lines:

```powershell
.\amtw.ps1 workbench          # the bench itself
.\amtw.ps1 doctor             # check venvs, CUDA, models
.\amtw.ps1 --help             # every tool
```

## What's on the bench

| Group | Tool | Does |
|---|---|---|
| Pipeline | `run` | full restore + re-synthesis on a vocal stem, into a job folder with a comparison report |
| | `report` | rebuild `report.html` for an existing job |
| | `doctor` | check venvs, CUDA, clones, checkpoints |
| Fry repair | `harmonic` | repair the scratchy "scrape" artifact on vocal fry |
| | `detect` | plot the fry detector's features against your own marks |
| | `defizz` | narrowband spectral smear (unproven — see findings) |
| | `remod` | HF envelope re-modulation (unproven — see findings) |
| Listening | `ab` | play aligned files in lockstep, switch instantly, mark regions |
| MIDI | `midi-merge` | fold duplicate stem-to-MIDI tracks into one clean track |
| | `midi-inspect` | list a MIDI file's tracks |
| Harmony | `harm-read` | bar-by-bar readings, how many keys still fit, and which voice narrows them |
| | `harm-map` | interactive page of every reading and every key, with a lens switch |
| | `harm-render` | render a bar range to audio, one file per voice-set, for A/B |
| | `harm-reduce` | collapse a chord clip into a single line (top / smooth / bottom) |
| Bitwig | `bitwig-install` | build and install the control-surface bridge extension |
| | `bitwig-bridge` | run the workbench end; drives Reduce/Analyse from inside Bitwig |

`harm-render` sounds better with a real instrument. Drop any `.sf2` into
`%LOCALAPPDATA%\VocalStemRegen\soundfonts\` and a FluidSynth build into
`…\fluidsynth\`, and it will find them; `amtw doctor` reports both. Without
them it uses a built-in synth, which is fine for checking a reading and not
for judging a mix.

## Vocal stem restoration

A separated AI-generated vocal is degraded twice: by the generation and by
source separation. The pipeline strips baked-in reverb, then runs generative
spectral restoration over what's left.

```powershell
.\amtw.ps1 run input\my_vocal.wav --stages cleanup,superres
```

There is a re-synthesis stage too — extract the performance, regenerate the
waveform with a voice-conversion decoder cloning timbre from the stem itself.
**It is off by the evidence.** Three engines across two architecture families
all produce modulation instability on sustained notes; see
[docs/findings.md](docs/findings.md) before reopening it. Restoration is what
actually ships.

### The fry "scrape"

These stems bake a scratchy artifact into fry and rasp passages: harmonics
buried in noise, measured HNR 4.6 dB there against 9.0 dB in clean singing. It's
in the source — de-reverb and Apollo don't touch it.

The automatic detector is too blunt to trust alone (AUC 0.755, ~17% precision at
any threshold). Marking the spots yourself gives 98% precision instead, and
everything outside a mark comes back bit-identical:

```powershell
# 1. mark the scratchy spots -- drag a region, press S, type a note
.\amtw.ps1 ab "song (Lead Vocal).wav"

# 2. repair only those regions
.\amtw.ps1 harmonic "song (Lead Vocal).wav" --adaptive `
    --from-notes output\ab_notes\<session>.json

# 3. compare
.\amtw.ps1 ab out\00_ORIGINAL.wav out\adaptive.wav
```

Your marks decide **where**; the detector decides **how much** within them.

## MIDI: fixing stem-to-MIDI exports

Stem-to-MIDI exports split one instrument across two tracks — bass notes on one,
upper voicing on the other — and then, partway through a song, start writing the
*same* notes to both. Played into one instrument, that double-triggers and
overloads it.

```powershell
.\amtw.ps1 midi-inspect "Keyboard (Piano).mid"           # which tracks hold what
.\amtw.ps1 midi-merge "Keyboard (Piano).mid" --tracks 1 2
.\amtw.ps1 midi-merge a.mid b.mid --out merged.mid       # or two separate files
```

The output has no two notes of the same pitch overlapping. Per pitch:

- two notes starting within `--dup` (default a 16th) are **one note heard
  twice** → collapsed, longest tail wins, loudest velocity wins;
- a later note starting *beyond* `--dup` is a **real restrike** → the held note
  is truncated to end `--gap` before it, and any tail it had past the new note's
  end is donated to the new note, so the longest tail still wins.

Two things that bite: these files contain **illegal key signatures** ("14
sharps") that make standard MIDI parsers hard-fail, and merging two *separate*
files whose tempo maps differ means tick positions no longer mean the same
moment — `--align auto` detects that and re-times in seconds instead, warning
when it does.

## Layout

```
amtw/            the package -- workbench, CLI, tools, engines
docs/            architecture, findings, how to add a tool
data/labels/     ground-truth listening labels
scripts/         runtime setup
input/           your source stems       (gitignored)
output/          job dirs and reports    (gitignored, gets large)
```

Heavy, regenerable things — venvs, model weights, third-party clones — live
outside the project at `%LOCALAPPDATA%\VocalStemRegen`, because the project
folder is cloud-synced and a sync client will happily corrupt a venv mid-install.
Details in [docs/architecture.md](docs/architecture.md).

## Contributing

Adding a tool is a recipe, not a refactor: drop one folder into `amtw/tools/`
and it appears on the bench and in `--help`, because both are generated from
the same declaration. See [docs/adding-a-tool.md](docs/adding-a-tool.md).

Much of this repo is written by AI agents working one session at a time with no
memory of the last. [AGENTS.md](AGENTS.md) is the contract that keeps that
coherent, and [docs/findings.md](docs/findings.md) is what stops each new
session re-running experiments that are already settled. Read both.

## License

MIT — see [LICENSE](LICENSE).

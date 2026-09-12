# Drum separation audition

Workbench: **Drums → Drum separation audition**. Choose the original drum WAV,
enter excerpt starts in seconds and a duration. Outputs are placed in shared
runtime `jobs/drum-audition-*`, with provenance in `manifest.json`.

This is separation, not restoration. Six parts are kick, snare, toms, hi-hat,
ride and crash. Claps have no dedicated class. Original, sum and difference WAVs
make any reconstruction discrepancy audible; the difference is not a clean
noise stem. Inputs are resampled to 44.1 kHz; all comparison outputs share that
path and duration. Three seconds of context surrounds each evaluated excerpt.
Do not interpret a close sum as proof of good individual isolation.

## Runtime setup

Uses existing MSST environment and clone; no added Python dependencies.
Create `models/drumsep` in the shared runtime and download these release assets:

- [six.ckpt](https://github.com/openmirlab/mdxnet-infer/releases/download/weights-drumsep-v1/aufr33-jarredou_DrumSep_model_mdx23c_ep_141_sdr_10.8059.ckpt)
- [six.yaml](https://github.com/openmirlab/mdxnet-infer/releases/download/weights-drumsep-v1/aufr33-jarredou_DrumSep_model_mdx23c_ep_141_sdr_10.8059.yaml)

Save using the short filenames above. The tool verifies both SHA-256 values
before running. The checkpoint is 438 MB, outside Git. Source is aufr33/jarredou's
six-stem DrumSep, mirrored by openmirlab; MSST commit used locally is
`ccc011abf7f89dd7922bb2888d48493b575c0289`. Upstream weight licensing is not
clearly established by the mirror; do not represent the weights as MIT merely
because inference code is MIT. See the mirror's README for provenance.

The proposed five-stem release returned 404 on 2026-09-12. Two Hugging Face
checkpoint mirrors returned 429. Six-stem download succeeded and its hash
matched the release documentation. The unused five-stem config remains in the
runtime; no five-stem checkpoint was installed.

## First listening set

MonstersUndone source seconds 40–52, 95–107, 180–192; montage starts 0, 13, 26.
These are distributed sample passages, not verified musical section labels.
Workbench-rendered job: `drum-audition-20260912-105204-d61357`.

- Port 8732: original / recombined / difference.
- Port 8733: original / kick / snare / toms.
- Port 8734: original / hi-hat / ride / crash.

Each is the existing A/B tool with its own notes JSON in the job. Keep loudness
matching off when judging contribution levels and the residual. Matching can
help reveal faint bleed, but then its loudness no longer reflects the mix.
The job-local `serve_auditions.py` launches these views; any can also be launched
through Listening → A/B listening with the corresponding files and port.

Next: listen for lost ghost notes, bleed, altered attacks and cymbal tails.
Only then trial Apollo universal on a selected problem part. Bitwig is unchanged.

## Apollo refinement comparison

**Drums → Apollo drum refinement audition** accepts one or more separation
manifest files. It reuses the contextual `out/seg_*` snare and hh audio, not the
joined montage. Universal Apollo runs in the existing MSST environment. Both
untreated and processed comparisons share resampling to 48 kHz; no gating,
gain matching or lag correction is applied. Each job contains solo comparisons,
untreated-minus-processed difference files, and a kit comparison replacing only
snare/hh. Kick, toms, ride and crash remain identical in that kit comparison.

Per-excerpt lag and width diagnostics are in the manifest. These describe changes,
not improvements. Use the A/B tool with untreated, Apollo and optionally difference
for either instrument, then the two kit files. Additional model downloads or
Python dependencies are not needed.

## Full-song delivery

**Drums → Render separated drums** runs full six-part separation, then applies
Apollo universal only to active hi-hat/shaker spans. Stereo RMS activity uses
-55 dBFS, 1s pads, 3s gap merging and 2s additional context. In-pad 100ms fades
join restored audio to the unchanged quiet material. The tool checks that skipped
samples are bit-identical at processing rate. It exports full-length source-rate
float WAVs and retains all six untreated parts under `raw/` for recovery.

MonstersUndone full job: `drum-full-20260912-115537-f239de`. The activity spans
cover 71.24%; including model context, Apollo receives 184.35s versus 219.48s
for a continuous pass. The initial separation still uses the whole drum stem.
This is selective processing, not a noise gate. No extra brightening is applied.

Delivery is installed in the native `MonstersUndone.cleaned-groove` project,
inside Drums under Group 9. All six clips share the original's 4.4.3.47 start,
Raw playback and full duration. Original Drum Kit, ride and crash are muted.
The four selected parts are active at -10dB each, Drums group at 0dB. Save and
Collect and Save completed; all six collected WAV hashes match the job manifest.

# Findings

Measured results, settled questions, and dead ends. **Read this before
proposing an experiment.** Re-running something settled here is the most common
way a session gets wasted.

Rules for this file: record negative results — they are worth more than the
positive ones. Record measurement *errors* too; three of them below produced
confident wrong answers that survived for days. If a finding is wrong, overturn
it with a measurement and edit the entry. Don't quietly contradict it.

---

## Renaissance accepted as a core vocal; full render (2026-09-12)

Arne's audition verdict: "the Renaissance stuff is amazing at separating all the
extra doubling and effects out" and "Renaissance is a great core track." He likes
the original's doubling and may blend it back or reproduce it. He also identified
the cleaner vocal as a possible Kling lip-sync input (not tested). Apollo is a
subtle improvement preserving the source character, but he explicitly chose to
skip a full Apollo pass and keep original + Renaissance for this song.

Rendered the full Lead Vocal through Renaissance: 10,535,040 frames, 48 kHz stereo,
219.480 seconds, peak 0.5131, finite samples throughout. 22 contextual blocks with
normalized two-second overlaps; same independent-L/R inference as the audition.
Render loop/write/hash took 7.56 seconds, excluding model load. Output hash:
`6c658543745e430ba3626324125263965123454e6a8139f8395b02294a0deb14`.
Runtime job: `jobs/renaissance-20260912-102230-07ccd8`.
Doctor and all 28 tool declaration roundtrips passed. The full-render tool also
completed from its workbench UI on the real 38-second reference montage (four
blocks, five seconds including startup). That smoke-test output was not imported.

Inserted into the running Bitwig project, track index 17 immediately below the
original at index 16, same -10 dB track level. Raw playback, source offset zero,
play stop displayed 3:39.479 (UI precision). The original's actual start is
15.619962250 beats, before bar 5. Selecting it then Down into the empty arranger
lane and pasting the Browser-copied audio retained that exact cursor; bridge
readback after selecting the new clip: 15.619962692260742 beats (float precision).
Do not round the displayed 4.4.3.47 for placement. Pasting with a TRACK HEADER
focused creates a Convolution device instead; that attempt was undone. Native
browser drag attempts produced no clips; copy/paste in arranger focus worked.
The imported clip container is longer than the original, but Raw audio retains
its own play stop; no stretching or looping was enabled.

Original is retained and muted; Renaissance active. Saved native project at
`C:/Users/arneg/OneDrive/Documents/Bitwig Studio/Projects/MonstersUndone.cleaned-groove/MonstersUndone.cleaned-groove.bwproject`.
Collect and Save copied the Renaissance WAV into that project's `samples` folder.
Arne subsequently approved the full-song lead: much cleaner and more legible,
still sounds great, without the blatant synthetic character of past regenerations.
He is using it with the original lead entirely muted.

Live bridge limitation discovered: `set_track` mute failed with
`BooleanValueAtomProxy ... Message not supported` at `.set(value)`. Original
mute was applied through the Bitwig UI and confirmed by a fresh bridge snapshot.
Do not claim Boolean writes have been validated merely because name writes work.

## Renaissance backing vocals rendered and placed (2026-09-12)

Following the successful full lead, Arne requested the same pass on backing vocals
to address spectral scratching. Removing or retaining doubling is acceptable;
cleaner sound is the priority. Subsequent listening verdict: very good; removing
doubling and effects is ideal because Arne prefers to recreate these himself.
Both Renaissance vocals are approved as better starting stems for this song.

Full source: `Downloads/Set the Monsters Loose Stems/Set the Monsters Loose (Backing Vocals).wav`.
Rendered 10,535,040 frames, 48 kHz stereo, 219.480 seconds, peak 0.4750,
22 contextual blocks with the same Renaissance settings as the approved lead.
Render/write/hash took 7.34 seconds excluding model load. Runtime job:
`jobs/renaissance-20260912-103717-6685c4`. Output SHA-256:
`a12d26f96e2f1d1f540b8fd358fa0812a0feab491db9d650d9925bc79a68fb28`.

Inserted immediately below original backing vocals in the open native project,
using Browser Copy, original arranger clip selection, Down into the new empty
lane, then Paste. Inspector confirms start 4.4.3.47, zero source offset, Raw mode,
no loop, play stop 3:39.479. Both tracks remain at -10 dB. Bridge confirms original
index 11 muted, Renaissance index 12 active, neither soloed. Original lead remains
muted and Renaissance lead active. Collect and Save completed; collected sample
hash matches the render. Doctor passes. Audio quality awaits Arne's listening;
successful rendering/placement is not a measurement of scratch reduction.

Stereo follow-up: our wrapper processes L/R independently, unlike upstream's
mono averaging. Full renders have nonidentical channels; whole-file side/mid
energy ratios measured -12.24 dB (lead) and -4.89 dB (backing). Neither is mono.
These figures do not establish spatial fidelity or preservation of original
width. Expect two channels with potentially altered width, not automatic mono.

Next requested experiment is drum-kit separation for mixing control, followed
by selective cleanup. Strategy (not yet run): audition sparse, busy and fill/tail
passages through jarredou's five-stem MDX23C DrumSep (kick/snare/toms/hh/cymbals).
Public configs/weights are listed in
https://github.com/ZFTurbo/Music-Source-Separation-Training/blob/main/docs/pretrained_models.md .
MVSep also lists newer SCNet XL and MelBand Roformer alternatives at
https://mvsep.com/algorithms/29?lang=en ; their public weight availability has not
been established here. No listed model promises a dedicated hand-clap stem.
Compare individual stems AND their unprocessed sum against original, then test
Apollo universal on selected problem parts. Do not apply the vocal Renaissance
model to drums by analogy. Existing drum-clean targets low tonal bleed, not
kit-piece separation; sustained drum energy is not automatically contamination.
No drum model installed or audio/project changed during this strategy review.

## MonstersUndone Apollo / Renaissance audition prepared (2026-09-12)

No listening verdict yet. Ran `stem-audition` from the workbench on the actual
Lead Vocal WAV, using source seconds 6–18, 48–60 and 182–194, with two seconds of
model context on either side. Each of four outputs is exactly 1,824,000 frames,
48 kHz stereo (38 seconds including two one-second gaps). Original samples in
the selected intervals are retained in the reference. Outputs are float WAVs;
all samples finite and peaks below 1. Apollo uses Lew vocal ep54, no cleanup.

Renaissance revision `b80e3a69c347f1290e62dddcb8e069654825aa7b`, model SHA-256
`dd73b487ed058fdea66a25915f9f5a50b3d2dd97c03480f268a1d50a00fe2b06`.
Existing main Torch 2.11/cu128 worked without added dependencies. L/R inference
is independent with a shared peak reference and the upstream 60 Hz high-pass.
Exact-length iSTFT prevents truncation. This does not guarantee spatial fidelity.

Apollo waveform-correlation lag was zero in both channels of all three clips.
Renaissance lags were [9, 8], [4, 4], [4, 0] samples (maximum 0.188 ms). These
can reflect phase changes, not a fixed latency; no shifts were applied. Its
side/mid ratio decreased by 0.50, 1.49 and 0.86 dB respectively. These numbers
are diagnostics, not evidence that the vocal improved or a voice disappeared.
The fourth audition slot is source minus Renaissance at original gain, including
phase differences; do not describe it as a separated noise/reverb stem.

Observed timings: Apollo subprocess 44.0 seconds; Renaissance loop including
diagnostics/output 2.8 seconds, excluding model load. Not a controlled benchmark.
All 27 tool declarations round-tripped; Doctor passed. User notes autosave to
`C:/audio/shared/amtw-runtime/jobs/vocal-audition-20260912-101606-f59e5b/listening-notes.json`.
Job manifest records source hash, provenance, timing and per-excerpt diagnostics.
Audition sections start at 0, 13 and 26 seconds; labels are setup cues only.

## Runtime consolidation and false missing-model diagnosis (2026-09-12)

The apparent missing Apollo/Torch/engines were a **path error**, not missing
assets. Claude's packaged Windows app had redirected LOCALAPPDATA to
`AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Local`, where the complete
48.8 GB runtime still worked. A second ordinary-AppData runtime had only the
lightweight tools. An unnecessary partial MSST install and 341 MB Apollo
download were made before this was discovered; both downloaded checkpoints
and both configs were SHA-256 identical to the existing copies.

Moved the complete runtime to `C:/audio/shared/amtw-runtime`, preserved both old
paths as junctions, merged this session's jobs/tools, and retained the inactive
partial runtime under `C:/audio/archives/amtw-partial-runtime-2026-09-12`.
Doctor then passed all checks: main CUDA Torch 2.11/cu128, MSST 2.6/cu124,
seed-vc 2.4/cu124, model files, audio-separator and FluidSynth. The live Bitwig
bridge reconnected and the consolidated workbench responded on port 8730.
The 26-tool CLI/bench roundtrip and four bridge regression tests passed.

The canonical repo already was `C:/code/github/ag-music-tool-workbench`; the
old OneDrive checkout's commit is an ancestor, with no unique code changes.
Its ground-truth JSON differs only in serialization, not values. Preserved 22
listening-note JSONs (about 30 KB) in versioned `data/listening-notes`, including
four guitar experiment notes that were sitting loose in the repository root.
Model hashes, source revisions and package inventories are also versioned.
See `docs/local-layout.md`; check the user runtime pointer and packaged-app
paths **before** installing allegedly missing assets.

## Resynthesis is closed

Three engines, two architecture families, all fail the same way — modulation
instability on sustained notes:

| engine | result |
|---|---|
| seed-vc | random wobble |
| YingMusic-SVC | wobble becomes structured vibrato — better, still wrong |
| Vevo2 | worse: warbly and unstable, both raw and with an Apollo post-pass |

Don't reopen this without a genuinely new architecture class. **The restoration
path is the product.**

Related, still true: the doubling artifact in seed-vc output was caused by a
subtle near-surface first reflection surviving de-reverb — the model re-renders
"voice + short slap" as a literal second take. `--deecho` fixes it. Raising
diffusion steps to 100 does *not* fix flutter/warble.

## The fry "scrape" artifact

The remaining real target: a fixed-resonance scrape and fizz on vocal fry,
worse on yell-like fry than breathy fry.

**It is in the raw source, not our chain.** Raw 48k, plain-resampled 44.1k,
de-reverbed, and de-reverbed+Apollo all measure identically (±0.1 dB). Band
prominence 10.7–10.9 kHz vs a 9–12.5 kHz baseline: 3.2 dB in the fry region vs
1.5 dB in a control region.

**What it actually is: harmonics buried in noise — low HNR.** Measured 4.6 dB
in marked segments vs 9.0–9.3 dB in unmarked voiced singing.

Feature separations vs unmarked singing / vs an acceptable-saturation stretch:

| feature | vs unmarked | vs saturation | verdict |
|---|---|---|---|
| hnr | −1.02 | −1.23 | dominant |
| aper | 0.92 | 1.05 | collinear with hnr |
| flux | 1.12 | 0.51 | |
| rough | 0.81 | −0.31 | fails the saturation test |
| hfr | 0.81 | 0.61 | |
| flat | 0.79 | 0.73 | |
| cpp | −0.31 | | |
| imp | 0.22 | | useless — was the leading hypothesis |

Logistic regression on the labels, grouped 5-fold CV: **AUC 0.755**. Usable,
not strong. The original periodicity gate was the right feature all along, just
mis-calibrated.

### The gate was the bug

All fry processing was gated on low periodicity with a 0.45–0.75 ramp. But
raspy singing keeps clear pitch: **0.70 measured on the artifact passage vs
0.93 on clean singing**, so the gate was only ~18% open exactly where the user
listens. **Every "no audible difference" result from before this discovery is
uninterpretable** — the processing barely ran. Defaults are now 0.60/0.92
(`--per-lo` / `--per-hi`).

`defizz` and `remod` were both only ever tested through the broken gate. They
are unproven, not disproven. Retest before discarding.

### Marked spans beat the detector

The detector maxes at AUC 0.755, which is ~17% precision at *any* threshold.
Raising the gate floor slides along the ROC curve without improving
selectivity — floors of 0.30/0.45/0.60/0.75 gave 60/66/71/77% of the track
untouched while recall fell 55%→27% and precision stayed stuck at 14–17%.

Marked-span mode instead processes only the user's own marks: **87% untouched,
100% recall, 98% precision.** So `amtw harmonic --from-notes <ab_notes.json>`
is the mode to use. Marks decide *where*, the detector decides *how much*.

The untouched guarantee has two load-bearing parts: a hard `gate_floor` so weak
detections become exactly zero, and a **time-domain** crossfade
`out = x*(1-g) + proc*g`, so untouched samples are the literal originals — an
STFT round-trip alone costs ~38 dB. **Never apply global RMS normalisation in
this command**; it rescales untouched regions and breaks the guarantee.

### What works

`amtw harmonic` is the first mechanism the user approved. Median-filter
harmonic/percussive split, pushing fry-gated frames toward the harmonic
component. Raises marked-segment HNR 4.62 → 5.48 dB at strength 1.0 with clean
singing unchanged.

Optimal strength tracks severity — 0.5 best on subtle scrape, 0.8 best overall,
1.0 best when the scrape is prolonged and pronounced — which is why `--adaptive`
scales between `--min-strength` and `--max-strength` using instantaneous gate
depth (45%) plus a ~600 ms sustained-ness term (55%).

Settled config, by listening test: `--adaptive --from-notes <notes.json>`.
Detector-driven severity won; fixed strength 1.0 was close behind;
span-duration-driven severity overshot on short-but-loud scrape. **Do not go
back to duration-driven severity.**

Note that adaptive closes only ~9% of the HNR gap and is still audibly
worthwhile. **Do not dismiss small metric moves on this artifact.**

### The sibilance trap

The gate keys on aperiodicity, and every "s"/"sh"/"t" is aperiodic. Without a
voicing requirement the harmonic mask strips their noise and de-esses the whole
track — measured −6.4 dB of air, rolloff halved from 9463 to 4875 Hz. Fry is
voiced, sibilants are not, so gating on low-band (<1 kHz) energy share fixes it
(air loss drops to −0.5 dB).

The user heard this before any metric showed it. And part of the pre-fix "HNR
improvement" was illusory: **de-essing raises measured HNR without fixing any
scrape.**

## Restoration chain

- **De-reverb model choice barely matters on these stems.** Four models swept
  on one stem (classic UVR VR / anvuew / anvuew-less-aggressive / bs_roformer
  deverb): tail energy 0.094–0.098 from a raw 0.135, RT60 0.15–0.21 s from a raw
  0.35 s. A 4% spread. The oldest model had the *shortest* RT60.
- **Apollo does real but narrow work.** Null test, gain and lag matched:
  residual −24.7 dB and −25.0 dB on two songs — substantial. But it changes
  nothing in band balance (±0.1 dB), bandwidth rolloff, reverb (RT60 0.35→0.38,
  i.e. none), or transient rise time (21.3→23.2 ms, slightly *slower*). It
  restores fine spectral detail within the envelope. An earlier explanation that
  "Apollo de-smears transients" was wrong; the more-forward quality comes from
  de-reverb removing masking energy.
- Source stems measure RT60 ~0.35–0.50 s — plate or small room, not hall. The
  restore chain roughly thirds it.
- Sucial big / super-big MBR models fail to load in `audio-separator`
  (band-config vs STFT mismatch); they'd need the MSST loader.

### Never de-reverb backing vocals (2026-08-08)

**DeEcho-DeReverb annihilates a stacked harmony.** User's verdict on the first
backing-vocal stem this chain has seen: it "totally annihilates" them. The
model is trained on lead vocals and reads the other harmony voices as the
reverb tail of the loudest one, so it removes them.

For backing vocals, run **`--stages superres`** — Apollo alone. On the same
material that was judged "a good nice tidy".

The null tests hinted at it before the listening did, though they could not
prove it: de-reverb changed the stack far more than the lead (residual
−22.1 dB vs −24.5 dB), which is either "more reverb to find" or "took
something that was not reverb". The two are indistinguishable by that number.

**The check that settles it in one listen: play the `(Reverb)` stem the
cleanup stage writes out.** That file *is* what was removed. Recognisable
singing in it means a voice was eaten. Use that before trusting any metric on
new material — it is a direct answer where everything else is an inference.

Same session, on the lead vocal of the same song: de-reverb removed almost
nothing (tail 0.531 → 0.513, ~3%), because the source was already a "clear
vocals" export. Apollo behaved exactly as recorded above, residual −25.0 dB.

### It is `--deecho` that eats a harmony, not de-reverb (2026-08-22)

On a lead-vocal stem that is a mix of solo and stacked passages
("Synth Groove 2022-09-17 ... (Lead Vocal)", RiversOnMars), the two cleanup
models behave completely differently, and the aggressive one is the *optional*
one:

| pass | removed overall | worst 8 s block |
|---|---|---|
| classic `UVR-DeEcho-DeReverb` | −31.1 dB | −21.2 dB |
| `--deecho` roformer, after it | −15.0 dB | **−2.0 dB** |

−2 dB removed means most of the block left with the "echo". Those blocks
(112 s, 136 s, 160 s) are exactly the ones where the separate Backing Vocals
stem is loudest — backing sits at −0.4 / +0.2 / −2.2 dB relative to the lead
there, i.e. a full stack. **Do not run `--deecho` on a stem with stacked
passages.** The rule from 2026-08-08 is really about the echo model, and it
applies to lead stems too whenever the lead is doubled or harmonised.

Classic de-reverb on the same stem is close to a no-op: band balance flat to
0.1 dB, stereo width down ≤1.3 dB (one block −2.1 dB), level unchanged. Null
test vs source: Apollo alone −24.7 dB — the same number as the two songs
above, so Apollo is doing its usual work — and de-reverb+Apollo −22.2 dB.

**A screen for "was that a tail or a voice", when you cannot listen yet.**
Periodicity does *not* answer it: the reverb of a sung note is a smeared copy
of a periodic signal, so the removed stem measures 0.81–0.89 either way — as
periodic as the source. What does separate them is pitch. A tail lags but does
not transpose; a stolen harmony sings a *different note at the same time*. So
compare the chroma of the removed stem against the kept stem widened ±250 ms
(so an honest late tail still matches its source) and report the fraction of
removed energy sitting on pitch classes the kept stem is not singing. On this
material that read 0.00 through the solo passages and 0.13–0.18 in the stacked
ones, for both models. Treat it as a pointer to where to listen, not a verdict
— it is a proxy invented in one session, and the `(Reverb)` / `(No dry)` stem
in the ear is still the thing that settles it.

**Stems vary this much inside one song.** Measured per 8 s block on this file:
stereo width swings from −39 dB side/mid (literally mono, 96 s) to −8 dB
(160 s), and de-reverb finds −48 to −85 dB of reverb through 24–108 s but
−21 to −30 dB at the edges. One global cleanup setting is therefore the wrong
shape for this kind of source, which is what motivates a per-section wetness
fader rather than an on/off de-reverb.

**Two proxies that failed here, recorded so they are not retried.** Post-offset
tail energy returned ~1.0 (no decay at all) because the singing is nearly
continuous — there are no gaps to decay into, so the "tail" window just catches
the next phrase. And envelope autocorrelation over 150–900 ms lags pinned to
the lag floor on most blocks: it finds the rhythm of the *singing*, which a
tempo-synced delay is deliberately hiding inside. Neither is usable on dense
material.

**User verdict on this stem (2026-08-22): Apollo-only wins.** "Only sounds a
little more refined than the original, but it's the best." De-reverb was not
wanted here — its output is kept in mind as an *alt track* to switch to when a
specific section needs drying, not as part of the default chain. So for mixed
solo/stacked lead stems the default is the same as for backing stems:
`--stages superres`.

### Universal Apollo and skip-silence, first full-song pass (2026-08-22)

All seven RiversOnMars stems through `--stages superres --skip-silence`,
vocal ckpt for the two vocal stems, Lew's universal ckpt for the rest.
Null residual against the source = how much the model actually changed:

| stem | model | residual | spans / processed |
|---|---|---|---|
| Lead Vocal | vocal | -24.7 dB | dense, whole file |
| Backing Vocals | vocal | -23.1 dB | 7 / 73% |
| Bass | universal | -23.1 dB | dense, whole file |
| Drum Kit | universal | -21.2 dB | dense, whole file |
| Guitar | universal | -20.4 dB | 7 / 72% |
| Synth | universal | -19.6 dB | 8 / 82% |
| Sound Effects | universal | -16.8 dB | 3 / 82% |

The gradient is sensible: the busier and more layered the material, the more
fine detail there is to restore. All outputs are sample-exact in length; a
20 s synth smoke test measured -16.2 dB residual against the same clip
through the *vocal* model barely changing it — the universal ckpt does real
new work on instruments rather than repeating what ep54 would do.

Skip-silence held its guarantee on a real stem: skipped stretches verified
**bit-identical** to the input (max |diff| exactly 0.0 over 17.6% of the FX
stem). Engagement is conservative by design — the Backing stem is 61% under
-50 dBFS on a 100 ms grid but only 27% got skipped, because 1 s pads and a
3 s merge gap keep decays attached to their notes. That is the right side to
err on; lower `--silence-db` or trim the pads only with a null test in hand.

Whole song, one 4080: ~9.5 minutes for all seven stems.

Listening verdicts on these outputs are pending. The vocal-stem verdict from
earlier today (Apollo-only, "a little more refined, but the best") is what
motivated the batch; per-instrument verdicts still need ears.

## MIDI

### What a Suno per-stem MIDI export actually contains (2026-08-22)

Measured over 200 per-stem exports on disk (85,343 notes, ~25 songs):

- **Zero pitch-bend events in every file.** A handful of CCs per file (0–14),
  which is an init message, not expression.
- **Velocity is flat.** Most files have exactly **1 distinct velocity value**;
  the rest have 2–20. (The older whole-song "Instrumental"/"Vocals" exports
  from 2024 carried 90+ distinct velocities — the per-stem exporter dropped
  dynamics entirely.) So "better dynamics" is not an improvement target, it is
  a missing feature: there are none to improve.
- **7.7% of notes are under 30 ms.** Drum stems are the bulk — every hit is a
  1–2 ms trigger (e.g. 2261/2261 on the RiversOnMars Drum Kit), which is a
  convention, not a defect. But pitched stems have them too: Guitar 142/261,
  Vocals 139/507, Bass 135/1444 on individual songs.
- **2,892 same-pitch overlaps** — a note retriggered while the same pitch is
  still sounding. Heaviest on Guitar (172, 160), Synth (172, 116), Keyboard
  (140, 105) per file.
- **Only 656 of the 6,572 short notes are same-pitch tail re-detections**
  (under 30 ms, starting within 100 ms after the same pitch ended). The
  user's "it's the tail detected as a new onset" theory is true for those;
  the other 90% of flickers are *different* pitches, i.e. transcriber noise.
- **Polyphony is implausible**: max simultaneous notes of 95 on one Guitar
  file, 81 on an FX file, 14 on a Bass. A per-instrument voice cap is a
  legitimate cleanup rule, not an aesthetic choice.

Implication: a cleanup pass can fix overlaps, flickers and polyphony by rule,
but expression has to come from the *stem audio* — the export does not carry
any to recover.

### Suno MIDI runs early against its own wav, by a per-song constant (2026-08-22)

The big one. Pitch-matching a lead-vocal MIDI against pyin on its own wav
stem: **28% of notes on the sung pitch as exported, 86% shifted +0.55 s.**
Not an octave (0–3% at ±12), not the tracker — a time offset. Per song:

| song | offset | stems agreeing |
|---|---|---|
| RiversOnMars ("Synth Groove …") | +0.517 … +0.533 s | all 7 |
| We Be Pop | +0.224 … +0.256 s | all 5 |
| RideTheWave | +0.219 … +0.256 s | 3 of 4 (Lead Vocal +1.4 s — a bad file, pitch-matches 28% at best) |
| Pockets Keep | +0.085 … +0.112 s | all 3 |

Constant within a song to ±25 ms (quarter-by-quarter scan), different
between songs. The sign: audio events happen *later* than the MIDI says, so
the MIDI must be moved later. Dropped at bar 1 beside its wav in a DAW the
notes lead the audio by up to half a second — almost certainly most of the
hand cleanup the exports used to need.

Estimator that works on every instrument: cross-correlate a MIDI onset
impulse train (30 ms Hann-smoothed) against the wav's onset-strength
envelope, peak lag within ±1.5 s. It agrees with the pitch-derived offset to
~25 ms and, because stems of one song agree, `midi-clean` takes the per-song
median and flags any stem >100 ms from it. Verified end to end: the cleaned
RiversOnMars lead vocal pitch-matches 86% at zero shift.

`midi-clean` over the full raw corpus (474 files, 222,618 notes): 3.1% of
notes removed — 2,331 duplicates collapsed, 5,850 restrikes truncated, 488
tails extended, 1,643 flickers dropped, 7,347 voices stolen, 2,492 chord
stubs dropped; polyphony reduced on 232 files. No listening verdict yet.

Two traps met on the way: (1) Suno song titles contain em-dashes, MIDI text
metas are latin-1, and mido raises on save rather than substituting — 74
files died on one "—" until `write_midi` started substituting; (2) onset
strength cannot judge a chord-dropped note, because it shares its onset with
the note that was kept. Judge those by pitch against the audio instead.


Stem-to-MIDI exports split one instrument across two tracks — bass low, voicing
high — then start writing the same notes to *both* partway through, which
double-triggers the instrument. On the reference file: 1040 notes across two
tracks → 860 merged, 180 collapsed as duplicates. Duplicates ran 1–2 per bar
through bar 60, then 8–20 per bar to the end.

Two parser-level gotchas:

- These files contain **illegal key signatures** ("14 sharps", "16 sharps") that
  make `mido` hard-fail. `amtw/tools/midi/midi.py` patches
  `MetaSpec_key_signature` to tolerate them. Any new MIDI code must import
  through that module or repeat the patch.
- Merging two *separate* files whose tempo maps differ can't be done in ticks —
  the same tick is a different moment in each file. `--align auto` detects this
  and re-times in seconds at a fixed BPM.

## Measurement errors made here

Kept because each one produced a confident wrong answer.

1. **Autocorrelation "reflection" peaks were just the pitch period.**
2. **FFT peak-picking is sample-rate biased.** 10798.9 Hz sits exactly on a bin
   centre at 44.1k but between bins at 48k, which produced a wrong conclusion
   that de-reverb was introducing a resonance. Use a bin-alignment-robust band
   prominence measure for any narrowband claim, and always compare raw against
   processed **at the same sample rate**.
3. **Max-normalised standard deviation is not a measure of modulation depth.** A
   taller peak squashes everything else. This produced "the fry HF band is
   compressed / under-modulated" when the truth is the opposite: envelope
   coefficient of variation is 1.020 at the artifact vs 0.455 in clean singing —
   it is *more* modulated, i.e. spiky and impulsive. **Always use coefficient of
   variation (std/mean), never max-normalised std.**

4. **Two metrics written to answer "did a harmony get stripped?" both failed,
   and one failed silently plausibly.** A tail-energy measure built on
   percentile loud/quiet bands returned exactly 0.000 on backing vocals,
   because intermittent material makes those bands degenerate. Worse, a
   "count prominent spectral peaks per frame" measure reported 15.2 → 12.2 →
   9.6 → 12.1 across the chain, which reads as a dramatic harmony loss — but
   the null test showed the last two stages were the *same signal*
   (residual −67.6 dB, correlation 1.0000), so a metric giving different
   answers for identical audio proves nothing. Likely 16-bit requantisation
   noise. **Before believing a new metric, run it on two files you already
   know are identical.** The listening test settled the question in seconds
   where both metrics had failed.

Also worth remembering: `scipy.ndimage.uniform_filter1d` runs a moving sum whose
rounding error can go slightly negative over near-silent stretches; `sqrt()` of
that gives NaN, and NaN written to a PCM16 wav becomes a **constant DC offset**,
not an obvious failure. `audio_utils.save` now refuses non-finite input.

## Tempo maps

### MonstersUndone: consolidated Suno import and drumless passages (2026-09-12)

Source: `MonstersUndone.dawproject`, Bitwig 6.1; matching originals in
Downloads/Set the Monsters Loose Stems. All clips were placed at beat 16
(bar 5). The exported tempo automation was already linear but remained at
beat 0; its initial duplicate points included 110 BPM followed by 97.071671.
Use the source MIDI tempo map shifted to the musical start, not this displaced
project lane. All eight embedded WAVs matched the downloaded originals.

48 MIDI tracks in eight parts matched their source onset/pitch fingerprints
exactly; six wrappers had generic group names and most children were named
Acoustic Grand Piano. Consolidation yields eight named tracks. Existing cleanup
rules took 3490 notes to 3463: 18 duplicates and 9 short flickers removed,
106 same-pitch restrikes truncated, 61 polyphony voice steals. Final same-pitch
overlap count: zero. All 908 drum notes remain. Banjo and Koto use the permissive
polyphonic profile, not a monophonic voice cap.

Non-vocal alignment estimates: guitar +245.3 ms, bass +234.7, drums +224.0,
koto +240.0, synth +229.3. Banjo's -736 ms peak is inconsistent and excluded.
Shared correction: +234.667 ms relative to audio. Independent quarter-song
checks on drums were +224/+224/+229.3/+229.3 ms and bass
+240/+245.3/+234.7/+229.3 ms. Koto had an ambiguous section near the search
boundary; do not promote it to an independent clock. No vocals set the grid.

`project-groove` ran successfully through the workbench UI. It fits 694 drum
anchors plus 71 lower-weight non-vocal consensus anchors more than one beat
from any drum anchor (two instruments within 25 ms). Drumless intro and later
gaps now have support; shared bleed means this consensus is NOT independent
ground truth. Final written lane: 1023 linear points, 86.0765–99.0276 BPM,
anchor absolute error median 5.67 ms, p95 20.77 ms, max 34.57 ms. A 0.1 BPM
thinning tolerance alone does not bound cumulative timing error; the new
workflow tightens it until added drift is under 1 ms (0.799 ms here).

Musical start remains beat 16. All raw audio clips move together to beat
15.619962250, 234.667 ms before it, within the flat count-in. Cleaned note
times are converted from the original stepped MIDI tempo to seconds, then
inverted through the written ramps. Every non-project.xml ZIP entry, including
all eight WAVs, remains byte-identical. This preserves performance time while
changing the grid; leaving note beat positions alone would move them audibly.

All source MIDI CCs were terminal CC7=100 at tick 160595. Bitwig imported them
as linear lanes starting at zero volume, ramping over the entire song, then
falling to zero. Removed those non-musical importer lanes; mixer settings and
note velocities are retained. Unexpected controllers fail closed.

The user imported the result in Bitwig, auditioned the metronome and confirmed
the sync/groove is good on 2026-09-12. They muted all eight MIDI tracks and
grouped the audio under Group 9. No further timing correction was requested.
The runtime's
analysis libraries are restored, and registry roundtrip checks pass for all
22 tools. Full doctor still fails on missing Torch/engine environments and
model checkpoints; this CPU-only workflow does not need those engines.

### Live project bridge in Bitwig 6.1 (2026-09-12)

Enabled the new official-API JavaScript controller in the running project,
without reopening Bitwig or exporting/importing the project. The loopback TCP
bridge read 19 tracks: eight muted instruments, Group 9, eight audio tracks,
FX 1 and Master. It read stopped transport at beat 350.6808606162667 and
86.58008575439453 BPM.

Renamed Group 9 to `Group 9 [bridge test]` through the protocol, verified the
readback, submitted a stale request (rejected), then restored Group 9 and
verified that **all track snapshot values matched the initial snapshot**.
Evidence is in runtime `jobs/MonstersUndone/live-bridge/verification.json`.
The MCP stdio initialize, tool listing and live snapshot succeeded. The same
live snapshot also completed from the workbench's Run button. Guarded same-name
writes returned verified readback through both MCP and the workbench edit form.
Four transport/protocol regression tests passed, including fragmented UTF-8
frames, oversized-frame rejection, disconnected/unsupported requests, and MCP
initialization plus invalid edit arguments. All 26 catalog entries round-trip
between the workbench argument builder and CLI without failures.

RemoteConnection uses four-byte big-endian length prefixes in both directions:
send requires the prefix and the receive callback removes it. The controller's
flat bank includes group children, effect tracks and master. No exact note,
tempo-envelope, device or audio-file editing is implemented in this version.
The revision guard observes state changes; it is not an atomic GUI transaction.
The existing doctor failures (Torch/engines/model files) remain unrelated to
the dependency-free live bridge.

### Where Suno's drum hits sit against its own beat grid (2026-08-22)

RiversOnMars Drum Kit, 849 onsets, position inside the beat under the
project's (Suno-derived) tempo lane, 16 bins:

```
0.000 ################### 157      0.500 ################### 152
0.188 ### 27                       0.688 ##### 44
0.250 ############### 127          0.750 ################### 155
0.438 ########## 85                0.938 ########### 95
```

Hits cluster on the 16ths, with a second population one bin *early* of each
(0.19 / 0.44 / 0.69 / 0.94 — 251 hits, 30%): a pushed, anticipating feel,
~45 ms ahead of the grid. A per-beat tempo map cannot represent that; it is
the sub-beat timing the user's hand-drawn ramps absorb.

`tempo-map` on that project: 844/849 hits anchored, anchor error after the
solve median 2.9 ms / 95th percentile 11.8 ms / max 71 ms (the max is in the
last two bars, where the kit thins out), tempo −2.9%…+3.2% around the prior.
The user's own hand map on another song stays within about ±5%, so the
excursion size is in character.

**User verdict (2026-08-23): "That worked out exactly like I wanted."** The
test was the light project (`tempo-map --light`: lane + note clips, no
audio) opened in Bitwig with the stems dropped at 2.4.2.00 (beat 7.25),
raw. So: Bitwig integrates `interpolation="linear"` tempo points the way
`solve.seg_seconds` does, the drop-position convention holds, and the
anchor rule was right often enough on this song. A job that takes the user
2–3 hours by hand.

Two things learned building it: the count-in must be pinned flat, because
the user's own lead-in tweak (a point at 7.75 beats, 87.5 bpm) otherwise
becomes the prior and the solved lane ramps up into the song; and anchoring
every hit at 3 ms tightness draws tempo wiggles for drum-machine jitter, so
the timing sigma is 4 ms — tight for a 20–45 ms push, loose for 2 ms noise.

## Expression read off the stems (2026-08-23)

The exports carry none (see the MIDI section), so `suno-project` reads it
from the wav. What the first song measured:

**Pitch, lead vocal (353 voiced notes).** The transcribed key is right for
86% of notes (median offset from key 0.19 st). The note *core* (15–85% of
its length) moves 0.80 st median; the *whole* note 1.80 st median / 5.7 st
at the 90th percentile — Suno's note boundaries include the glide into the
neighbouring pitch. Rules that followed: frames more than 2.5 st from the
key are not this note; curves clamp at ±2 st; a note whose contour mostly
disagrees with its key (median off >1 st, or >30% of frames far) gets no
curve. Result: 288 of 358 notes carry a curve, range median 1.2 st, 90% 2.4
st, ~11 points each. Bass: 170 of 359, median 0.3 st. Backing vocals get no
curves on purpose — a stack is not mono.

**Velocity.** Percentile mapping (10th→floor, 90th→ceiling) was wrong: it
forced the quietest tenth of every stem to the floor whether it was 3 dB
quieter or 30. Fixed dB range instead: ceiling at the stem's 90th-percentile
note energy, floor 24 dB below. Drums normalise per piece (a loud hat is loud
for a hat): kick 83–120, hats 72–120, snare/side-stick carry ghost notes to
the floor. Pitched notes measure the peak in a ±0.6 st band around f0 and
2·f0 over the first 80 ms, so an inner voice is read as itself.

**Listening verdict pending** on both. The user's stated worry is that the
stem split makes some notes much softer than played; the floor is the
answer offered, not a measurement.

## Guitar AG stateful-string A/B (2026-08-27)

The Guitar AG Plan 0090 fixture compared three aligned 10.125 s renders with
the A/B tool's loudness matching enabled: the legacy modal engine, a stateful
two-polarization waveguide preserving repick state, and the same stateful
engine resetting on repicks.

**User verdict:** legacy "sounds not bad" but has a spectral-chirp attack and
a somewhat glassy note body; both stateful variants "just sound like a synth."
No timestamp markers were recorded. This is a negative result for the current
stateful timbre, not for the A/B harness: stability, determinism, spectral
metrics, and audible preserve/reset differences did not make the new engine
read as electric-guitar DI. Keep it offline and improve isolated-note string,
pickup, and body mechanics before testing state continuity as a promotion gate.

Notes JSON:
`output/ab_notes/guitar-ag-plan0090-stateful.json` (local, gitignored).

## Guitar AG legacy-layer ablation (2026-08-27)

Plan 0091 used aligned 10.125 s renders to remove the legacy modal engine's
short chirp modes, explicit pick/contact overlays, and global finger-noise
generator independently.

At ordinary pick settings, removing the chirp modes was barely different. The
user clarified that objectionable chirp occurs under deep pick, flexible pick
stiffness, and raised texture; test the reported regime rather than defaults.
Removing the explicit overlays removed recognizable pick sound but did not
change the modal-body character. At 1.924–3.157 s, high E sounded like a
semi-realistic low-register guitar digitally pitch-shifted upward, pointing to
a register-identity problem rather than brightness alone.

The isolated finger-noise contribution sounded like "plucking the teeth on a
stiff plastic hair comb." The desired replacement is speed-driven friction
hiss plus less-periodic transverse/bowing motion, with depth optionally engaging
a restrained string/harmonic-position-dependent squeak.

**Residual-generation measurement error:** FFmpeg `amix` treated a negative
weight as a magnitude and summed the two files. The false residual was exactly
6 dB louder and sounded like its sources. Use `amerge` plus explicit `pan`
channel subtraction, then verify that ablated source plus residual reconstructs
the original. Corrected residuals measured infinite reconstruction PSNR.

Notes JSON:
`output/ab_notes/guitar-ag-plan0091-attack.json` and
`output/ab_notes/guitar-ag-plan0091-finger-noise.json` (local, gitignored).

A targeted third pass used 100% `Pick Bite`, 10% `Pick Stiffness`, and 75%
`Pick Texture`. The current attack sounded like a pronounced but sparse woody
rattle; removing the short chirp modes was again not much different. The
correctly isolated explicit attack extras sounded like crude digital synthesis,
not a plausible material interaction. This rules out the short chirp-mode bank
as the primary cause in the reported failure regime and rejects retuning the
additive pick/contact layers as the next path. The next comparison should inject
a finite-duration pick force into the modal string and let pickup output emerge
from the resulting string response.

Deep-pick notes JSON:
`output/ab_notes/guitar-ag-plan0091-deep-pick.json` (local, gitignored).

## Guitar AG modal-coupled pick direction (2026-08-27)

Plan 0092 replaced direct picked output with a deterministic finite force on the
legacy modal quadrature state. Human listening selected the 1.75x force version
as the next foundation and requested a lesser amount of the current additive
attack for texture, with higher event density. The direct layer should therefore
become subordinate surface detail rather than the sparse woody event rejected in
Plan 0091.

The same pass described the upper-register body as analogous to vocal pitch
shifting without formant correction: the low note retains plausible scale while
high notes sound artificially smaller. This supports a separate test that keeps
harmonic frequencies pitch-relative but anchors more of the pickup/material
spectral envelope in absolute Hz.

No Plan 0092 notes JSON was saved; this verdict was provided directly in the
task conversation.

## Guitar AG register/formant anchor (2026-08-27)

Plan 0094 kept the accepted medium hybrid pick fixed and compared 0%, 35%, 65%,
and 100% movement from a harmonic-number modal envelope toward an absolute-
frequency envelope. Audition-only register gain kept note levels comparable.

With loudness matching on, the user judged the 35% anchor "pretty good" and
"much better than current." It also flattened progressively and lost some metal
ring and brightness toward the high register. This is a positive result for the
formant premise but a negative result for using one scalar to control amplitude
and decay together. Preserve the 35% amplitude correction and test decay plus a
narrow fixed-Hz metallic side-mode contribution independently.

No Plan 0094 notes JSON was saved; the exported notes were provided directly in
the task conversation.

## Guitar AG decay/metal-ring separation (2026-08-27)

Plan 0095 held the accepted 35% amplitude/formant envelope fixed and crossed
anchored versus harmonic-number decay with zero versus a labelled 6x restoration
of lost inharmonic side-mode energy. Literal 1x restoration had been too quiet
for a useful listening slot, so 6x was an audibility diagnostic rather than a
proposed production amount.

With loudness matching on, the user called the combined harmonic-number-decay
plus 6x restoration track "pretty good." Keep that combination as the
provisional offline foundation and calibrate restoration downward. No separate
verdict was recorded for decay-only or metal-only, so this result does not prove
that both axes are independently necessary.

No Plan 0095 notes JSON was saved; the exported notes were provided directly in
the task conversation.

## Guitar AG metal-restoration amount calibration (2026-08-27)

Plan 0096 held harmonic-number decay and the accepted 35% amplitude envelope
fixed while comparing 0x, 2x, 4x, and the previously accepted 6x side-mode
restoration. The four full mixes were within 0.1 dB mean and 0.2 dB per note.

With loudness matching on, the user selected 2x as good. Use 2x in the
consolidated offline recipe and retire the deliberately exaggerated 6x probe.
The selected render hash is
`ABF261ECD386B652755244D6A63786E6DB4A8899E1948DDF263750EC770AC041`.

No Plan 0096 notes JSON was saved; the verdict was provided directly in the task
conversation.

## Guitar AG production-tone promotion gate (2026-08-27)

Plan 0097 compared the current production-equivalent legacy tone against the
complete accepted offline recipe in one aligned 26.9-second program: ordinary
E2–E4 picking, the deep/flexible/textured failure regime, and a compact
riff/arpeggio/upper-melody/chord phrase.

With loudness matching on, the user confirmed that the candidate track works.
This clears the combined recipe for a separate production implementation rather
than another isolated-tone experiment. Preserve the former tone as an explicit
offline regression recipe during promotion.

No Plan 0097 notes JSON was saved; the verdict was provided directly in the task
conversation.

## Guitar AG hybrid pick-texture calibration (2026-08-27)

Plan 0093 kept the 1.75x modal-force foundation and compared 12% and 22% mixes
of the direct texture at 2.5x event density, plus a same-mix sparse control and
the isolated dense contribution. With loudness matching on, the user accepted
12% dense texture as a good medium setting and 22% as a good maximum setting.

This is a range calibration rather than a single winner. Use 12% as the neutral
attack baseline for body/register experiments and preserve 22% as the upper
texture extent. No notes JSON was saved; the exported notes were provided in the
task conversation.

## Ground truth

`data/labels/pockets_fry_segments.json` — 16 user-marked segments on one lead
vocal: 14 scratchy, 1 "pop", and 1 "saturation on peaks" the user called
musically acceptable. That last one is a valuable **negative** example; a
feature that flags it is a feature that fails.

This is the only reason any detector claim above is checkable. Any detector work
must report against it.

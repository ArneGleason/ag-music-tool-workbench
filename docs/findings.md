# Findings

Measured results, settled questions, and dead ends. **Read this before
proposing an experiment.** Re-running something settled here is the most common
way a session gets wasted.

Rules for this file: record negative results — they are worth more than the
positive ones. Record measurement *errors* too; three of them below produced
confident wrong answers that survived for days. If a finding is wrong, overturn
it with a measurement and edit the entry. Don't quietly contradict it.

---

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

## MIDI

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

## Ground truth

`data/labels/pockets_fry_segments.json` — 16 user-marked segments on one lead
vocal: 14 scratchy, 1 "pop", and 1 "saturation on peaks" the user called
musically acceptable. That last one is a valuable **negative** example; a
feature that flags it is a feature that fails.

This is the only reason any detector claim above is checkable. Any detector work
must report against it.

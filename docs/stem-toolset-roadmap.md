# Stem toolset roadmap (2026-08-22)

One tool family per *kind* of Suno stem, instead of one pipeline that assumes
every input is a solo lead vocal. Written after a research pass over what
shipped in 2025–26; findings.md holds the measurements this plan leans on.

## Where each stem type stands

| stem type | settled recipe today | planned upgrade |
|---|---|---|
| solo lead vocal | `run --stages cleanup superres`; fry repair via `harmonic --adaptive --from-notes` | none needed — this is the mature path |
| lead with stacked/harmony passages | **`--stages superres` only** (Apollo). De-reverb is near-no-op, `--deecho` eats the stack — findings 2026-08-22 | karaoke split → treat layers separately (below) |
| backing vocals | **`--stages superres` only** (findings 2026-08-08) | same karaoke-split option |
| effected vocals, effects wanted | nothing — the chain only knows how to *remove* effects | wet/dry layer tool (below) |
| drums | `drum-clean` for bleed | + Apollo **universal** pass; later per-piece via DrumSep |
| bass / guitar / synth | nothing | Apollo **universal** pass |

## Build order

**1. Apollo universal model as a superres choice.** Lew's universal Apollo
restores any music, not just vocals; checkpoint + MSST config are on HF
(`ASesYusuf1/Apollo_universal_model`, rehost of the model MVSEP runs as
"Universal Super Resolution"). The superres stage hardcodes the vocal ckpt
(`core/paths.py:61`); adding a `--model vocal|universal` choice plus a doctor
check unlocks drums, bass, guitar and synth in one small change. Everything
else about the stage (MSST subprocess, msst venv, chunked inference) is reused
as-is.

**2. Stem profiles on the bench.** One tool where the first field is *what
kind of stem is this* and every default follows from that — the table above,
encoded. The per-type knowledge currently lives in findings.md, which the
person using the bench should never need to read.

**3. Wet/dry layer tool — for "effects preserved and even improved".** The
cleanup stage already writes both halves of a de-reverb: `(No Reverb)` and
`(Reverb)`. So: split, run Apollo on *each half separately*, recombine
time-domain at unity — the effect survives and gets the same detail
restoration as the voice. A per-section wetness fader (`out = dry + α(t)·wet`)
falls out for free, which is also the "alt track to dry up specific sections"
idea from the RiversOnMars session. Time-domain sum keeps the
untouched-samples guarantee. Open question to A/B: does Apollo-on-the-wet-half
beat Apollo-on-the-sum (which is what superres-only does today)?

**4. Karaoke split (lead vs harmony stack) as a bench tool.** audio-separator
already lists the current community models — `Mel-Roformer-Karaoke-Aufr33-Viperx`,
Gabox V1/V2, becruily — loadable in the main venv today, no new plumbing.
Standalone it answers "give me just the lead / just the stack"; inside the
profiles it enables de-reverbing *only* the lead layer of a stacked stem,
which the whole-stem chain must never do.

## Watchlist — promising, not plumbed in

- **SonicMaster** (AMAAI-Lab, ICML 2026): one flow-matching model, text-prompt
  controlled, covering reverb/clipping/EQ/dynamics/stereo — the closest thing
  yet to "improve the effects" rather than remove them. Generative, though,
  and this repo closed resynthesis because three generative engines all
  warbled on sustained notes. Trial under the A/B tool before any bench entry;
  needs its own venv.
- **AnyEnhance** (Amphion): unified speech+singing enhancement (denoise,
  de-reverb, de-clip, SR). Only a challenge-baseline checkpoint is public
  (`viewfinder-annn/AnyEnhance-v1`); the real weights are still "near future".
  Re-check occasionally.
- **FlashSR / AudioSR / UniverSR**: general audio super-resolution to 48 kHz,
  FlashSR ~22× faster than AudioSR. Overlaps Apollo; only worth an A/B if
  universal-Apollo disappoints on instruments.
- **DrumSep mdx23c** (jarredou build: kick 16.7 / snare 11.5 / toms 12.3 SDR):
  per-piece drum split for rebalancing or piece-level cleanup. MSST-loadable.
- **MelBand Roformer Denoise** (aufr33, SDR ≈28): likely better than the
  UVR-DeNoise the cleanup stage offers; drop-in candidate when denoise
  actually gets used.
- **RemFX** (2023): general effect *removal* (distortion, compression, reverb,
  chorus, delay). Research-grade; the wet/dry approach above gets the same
  outcome from models we already trust.

## Deliberately not planned

- Resynthesis stays closed (findings). Nothing above re-renders the voice.
- No full-mix mastering ambitions — stems in, stems out, Bitwig does the mix.

## MIDI side (added 2026-08-22)

What a Suno per-stem MIDI export contains is now measured (findings): no
pitch bend, one velocity, flickers, overlaps, implausible polyphony, and a
per-song time offset against its own wav. `midi-clean` handles all of that.

What it cannot do is expression, because the export has none. Next:

1. **Expressive mono transcription** (lead vocal, bass) from the *restored*
   stem: pyin/RMVPE contour → note segmentation → per-note bend curve,
   velocity from onset energy, gain curve from the envelope. Deliver as an
   MPE MIDI file; Bitwig's "PB Expressions" should map it to per-note pitch —
   one import test needed before building on it.
2. **Polyphonic stems via Basic Pitch** (guitar, synth), judged by ear
   against Suno's transcription — render both with `harm-render` and A/B.
3. Ground truth for free: the Bitwig bridge can read a hand-cleaned clip, so
   raw export vs the user's cleaned version is a labelled pair for any rule.

## Tempo maps — the delivery format exists (2026-08-22)

Suno's MIDI tempo map is one `set_tempo` per beat (e.g. 83.25, 83.18, 82.59 …
every 480 ticks): constant inside the beat, a jump at each beat. It cannot
express swing, a pushed hat, or a fill, because those are sub-beat.

The user's hand-made map, read from a Bitwig `.dawproject` export
(`WeBeBeWeBe/Webee.3.61b.dawproject`): **944 linearly-interpolated tempo
points over 118 bars, 99% of them on a 16th-note grid**, 119–133 bpm around
125.8. Inside a beat it makes an S-shape — e.g. 125.6 → 124.3 at the 2nd
16th → 126.8 at the 4th → 125.4 on the next beat — which lands the hat where
it was played while the next downbeat still lands on the grid. New parts
written "square" on that grid then sit in the groove.

**DAWproject is how to deliver ramps.** Its `<TempoAutomation unit="bpm"
timeUnit="beats">` holds `<RealPoint value time interpolation="linear"/>`
entries — that *is* a ramp — and Bitwig opens `.dawproject` natively. A tool
that writes one can therefore hand Bitwig a performance-following tempo map,
plus the aligned stems as audio clips and the cleaned MIDI as note clips, as
a starter project. Standard MIDI files cannot do this; no point trying.

Built as `tempo-map` (2026-08-22): onsets from the drum stem → each 16th
anchored to a hit under a bounded rule → least-squares linear-ramp solve →
`.tempo.dawproject` plus a drums+click mix and a review picture. Judged by
ear next. The anchor rule is the part most likely to need the user's
judgment — a review UI where anchors can be toggled is the natural next step
if the automatic choice is wrong often enough to matter.

Also learned from the user: bass can be square, lagging, or anticipating
relative to the drums, and the groove direction changes by section — even
reverses at a big change. That is why the map follows the drums; a later
tool could *measure* the other stems' offsets against the drum-derived grid
section by section, which is information the user currently discovers by
hand.

## Built 2026-08-23: `suno-project`

The MIDI side above collapsed into one tool: Stems folder → light
`.dawproject` with tempo lane, cleaned expressive note tracks, empty audio
tracks. Verified structurally; the user's Bitwig is the test. Open items:

- a review page for tempo anchors (toggle an anchor, re-solve)
- per-stem groove measurement against the drum grid (the bass-leads /
  bass-lags observation), as information first, as a correction maybe
- per-note gain envelopes — the band energy over time is already computed;
  emit when the user wants them
- polyphonic pitch curves (guitar, synth): needs per-note partial tracking;
  not started

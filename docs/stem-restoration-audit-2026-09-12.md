# Stem restoration research audit — 2026-09-12

Research shortlist, not local measurements or listening verdicts. No new models
were installed or audio processed for this audit. Read `findings.md` before
experimentation; previous resynthesis failures and stacked-voice loss still apply.

## Recommendation

Compare original, existing Apollo, and Smule Renaissance Small on identical short
quiet, strong, and doubled/wide passages of MonstersUndone. Preserve sample timing,
match audition loudness, and judge breath, consonants, voice identity and stereo
image. Width alone does not prove doubling. Do not process the whole song until
Arne has judged the samples. The cause of the described artifacts is not diagnosed:
generation, compression and separation could contribute, and no unique clean
original can be assumed for generated material.

## Candidates

- **Smule Renaissance Small (24 October 2025): first new audition.** Singing-trained
  restoration directly in the complex STFT domain with phase-aware losses; targets
  noise, reverb, band limitation and clipping. The authors report strong singing
  benchmark results, which do not establish superiority on this whispery Suno stem.
  [Paper](https://arxiv.org/abs/2510.21659),
  [code](https://github.com/smulelabs/smule-renaissance),
  [weights](https://huggingface.co/smulelabs/Smule-Renaissance-Small).
  The [stock runner](https://github.com/smulelabs/smule-renaissance/blob/main/main.py)
  averages stereo to mono and high-passes at 60 Hz. An audition must expose or adapt
  this preprocessing; separate channel inference also requires stereo-coherence
  verification. Direct spectral processing does not guarantee preservation.

- **Music Source Restoration / MSR (March 2026): closest research problem.**
  Ensemble separation followed by targeted BSRNN reconstruction addresses imperfect
  stems from mixed/processed music. Overall challenge placement is not evidence
  of uniformly improved vocals: the paper's vocal metrics are mixed after the
  restoration stage. More integration work than a simple replacement processor.
  [Paper](https://arxiv.org/abs/2603.16926),
  [implementation](https://github.com/xinghour/Music-source-restoration-CUPAudioGroup),
  [baseline weights](https://huggingface.co/yongyizang/MSRChallengeBaseline),
  [MSRKit](https://github.com/yongyizang/MSRKit).

- **LOUDAR (3 August 2026): exploratory follow-up.** Fits an unknown distortion
  model per input using a latent diffusion prior; evaluated on singing effects
  and guitar distortion. Relevant to unknown corruption, but performance identity
  and separation-artifact benefit remain unverified here. Code exists; checkpoint
  download and local inference were not validated.
  [Paper](https://arxiv.org/abs/2608.01972),
  [code](https://github.com/michalsvento/loudar).

- **SonicMaster (August 2025; revised August 2026): watchlist.** Text-controlled
  restoration/mastering with flow matching. Potentially useful for broader sound
  changes; less compelling as the first minimal-repair trial. Code exists, but
  checkpoint readiness and preservation on this material were not established.
  [Paper](https://arxiv.org/abs/2508.03448),
  [code](https://github.com/AMAAI-Lab/SonicMaster).

Keep [Apollo](https://github.com/JusperLee/Apollo) as the familiar baseline. Its
[original research](https://arxiv.org/abs/2409.08514) centers on compressed music
restoration; that does not establish a universal repair for separator artifacts.
Newer publication dates alone are not a reason to replace an accepted result.

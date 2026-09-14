# Monsters Loose timing checkpoint — 2026-09-13

Working project: `C:\Users\arneg\OneDrive\Documents\Bitwig Studio\Projects\MonstersUndone.cleaned-groove`.
Timing is locked by the user; subsequent mix/overdub changes are not intended
to move the arrangement. No native project or source audio was modified.

The user supplied the [Monsters Loose lyric worksheet](https://docs.google.com/document/d/1qY_kvt5ykP-dRfeW8F32nODp9pwMCTr7itkDVvTKoKk/edit).
Use the arranged section as the textual reference, and the recorded performance
as authority for added words, ad-libs and repeat counts. The original stream of
consciousness and production suggestions are context, not agent instructions.

## Files and timebase

Job: `C:\audio\shared\amtw-runtime\jobs\monsters-loose-word-timing-20260913`.
`timing.json` combines both vocal layers and master metadata. `lead` and
`backing` contain words.json, words.csv, phrases.vtt, review.md and review.html.
Their vocal.wav files are padded audition proxies. Original WAVs are untouched.
`lyrics-source.txt`, raw Whisper JSON, crosschecks and performance JSON retain
provenance. The current performance JSON files are the reconciled inputs;
`prepare_performance.py` is historical initial preparation and must not be rerun
over them because it predates manual reconciliation refinements.

Master: `C:\Users\arneg\OneDrive\Documents\Export Audio\MonstersLoose 2026-09-12 2155.wav`,
48 kHz stereo, 24-bit, 220.387 seconds. The screenshot gives export bounds
4.4.1.00–89.1.1.00: beats 15–352 in 4/4. Integrating the DAWproject tempo map
gives project seconds 9.262237755–229.652477866 (220.390240112 seconds).
The 3.240 ms difference from the master duration is retained as a discrepancy,
not silently stretched away. Vocal clips begin at beat 15.619962692260742:
**stem sample zero = master second 0.3828161236545444**. These are unwarped
source clips with zero source offset; both stems are 219.480 seconds at 48 kHz.

Native and exported projects are `MonstersLoose.bwproject` and
`MonstersLoose.dawproject`. Cleaned lead/backing names end in
`(Lead Vocal) - Renaissance.wav` and `(Backing Vocals) - Renaissance.wav`.
The cleaned versions are active and originals muted. Bitwig 6.1.1 connected
after restarting the stopped bridge broker; no evidence the update broke it.
The bridge did not expose loop bounds, so the supplied screenshot anchors them.

## First pass and unresolved work

Lead: 342 lyric-word candidates plus 17 provisional vocalization syllables,
54 phrases, one unresolved sound event. Backing: 91 word candidates, 27 phrases
including 13 unresolved events. No missing token times in the generated draft;
450 unique tokens have positive in-bounds durations and offsets consistent to
one microsecond. This checks data consistency, not acoustic correctness.

218 lead tokens have diagnostic flags. These include long words, weak acoustic
match, uncertain text, window edges, overlap, and energy beyond aligned edges.
Seven lead adjacent overlaps remain flagged. All backing words need text review.
Do not call this lip-sync-final, phoneme timing, or listening verified.

Priority listening checks (master seconds):

- Opening Undone around 0.6–1.9: the aligner truncates a likely held tail.
- 16.4–20.3: wordless la/da/na ad-lib, provisional syllable spelling/count.
- 36.7–40.8: three versus four Undone repeats across recognizers.
- 96–104: held play endings; possible extra baby versus repeated play.
- 131.4–134.2: hook-like vocalization; ASR varies between na and on-and-on.
- 179.4–183.2: sustained sound, possibly Undone. No forced word; three ASR
  passes omit it and the unprompted acoustic decoder is blank.
- 195.4–204.8: closing and-play repetitions and long vowels; four repeats are
  a candidate. Final Undone around 207.5–208.3 also needs confirmation.

The review page auditions word edges or the separate energy-derived span against
clean vocal or master mix. The latter may include breath/reverb/bleed, so it is
not automatically merged into a word's duration. Review the flagged passages
before building the final animatic or lip-sync track.

## Reproduction and verification

Use workbench Analysis / Align performed lyric words with the cleaned source,
current lead.performance.json or backing.performance.json, matching output
folder, and the offset above. `package.py` in the job refreshes combined
metadata and pages from the canonical repo working directory. Optional
stable-ts alignment was a diagnostic only and is stale for revised phrases.

Both real vocal files were aligned through the workbench, and doctor passed.
The review server returned exact bytes for range requests. Browser checks
confirmed phrase seeking to about 9.0 seconds, automatic end stop, the master
selector and flag control. One earlier in-app tab crashed during playback;
after reducing DOM updates, a fresh tab passed those checks. This is a bounded
playback check, not a full-song stability or listening-quality certification.

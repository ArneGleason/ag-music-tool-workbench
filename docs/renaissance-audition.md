# Renaissance audition adapter

`stem-audition` is on the Listening workbench. It prepares short original/Apollo/
Renaissance comparisons and a source-minus-Renaissance difference signal, with
one second between excerpts. The difference is not an isolated noise estimate.
Use the existing A/B listening tool to open the four numbered WAVs from its job.

Renaissance is experimental here. L/R are processed independently with shared
peak normalization and the upstream 60 Hz high-pass. This retains two channels
but does not guarantee preservation of spatial character or doubled voices.
The adapter uses exact-length inverse STFT and trims two seconds of surrounding
context where available. Manifest lag/width figures are diagnostics, not verdicts.

Install outside the code checkout, under the configured runtime root:

- Clone https://github.com/smulelabs/smule-renaissance into
  `third_party/smule-renaissance`.
- Download https://huggingface.co/smulelabs/Smule-Renaissance-Small/resolve/main/smule-renaissance-small.pt
  to `models/renaissance/smule-renaissance-small.pt`.
- SHA-256: `dd73b487ed058fdea66a25915f9f5a50b3d2dd97c03480f268a1d50a00fe2b06`.
- Uses the existing main environment's Torch, torchaudio, NumPy, SciPy and
  soundfile; no new dependencies. This adapter currently requires CUDA.
- Apollo uses the existing MSST subprocess and vocal checkpoint. Outputs and
  contextual inputs stay in a unique runtime `jobs/vocal-audition-*` directory.

This is a short-excerpt audition tool, not a full-song restoration command.

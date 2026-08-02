# Working on this repo (for AI agents)

This project is built mostly by AI agents working one session at a time, each
one starting with no memory of the last. That constraint shapes everything
below. Read this file before changing anything.

## What this is

A **workbench** — a local web UI — plus a set of music-production tools that
appear in it. The workbench is the product; the tools are the content. Someone
who hates typing commands should be able to double-click one file and reach
every tool with real widgets.

The pipeline for restoring AI-generated vocal stems is the first family of
tools. MIDI repair is the second. More families are expected. Nothing about the
workbench is vocal-specific.

## The five rules

**1. A tool is not done until it is on the bench.**
A command that only exists in the CLI is invisible to the person using this.
A tool is one folder under `amtw/tools/` exporting `TOOL`; the bench and the
CLI are both generated from that single declaration, so it cannot land in one
and miss the other. See [docs/adding-a-tool.md](docs/adding-a-tool.md) — it is
a 10-minute recipe, not a refactor.

**2. Read [docs/findings.md](docs/findings.md) before proposing an experiment.**
It records what has been measured and settled, including several dead ends that
cost real time and three measurement errors that produced confident wrong
answers. Re-running a settled experiment is the single most common way an agent
wastes a session here. If a finding is wrong, overturn it with a measurement and
edit the file — do not quietly contradict it.

**3. Put the reason in the code, not just the diff.**
Comments here explain *why*, especially where the obvious thing is wrong: why
there are four venvs, why the runtime dir is outside the project, why a global
normalise would break a guarantee. Match that density. A future agent reads the
file, not the pull request.

**4. Verify by running it, and report what actually happened.**
This repo talks to real audio and real MIDI. Run the tool on a real file and
say what came out. "Should work" is not a result. If something is broken or
half-finished, say so plainly — an honest gap is cheap, a false claim of
completion costs the next agent a whole session.

**5. Don't let the user's ear get overruled by a metric.**
The measured HNR improvement from `amtw harmonic` is about 9% of the gap, and
it is audibly worthwhile. Conversely, an early "HNR improvement" turned out to
be the tool de-essing the whole track — the metric moved, the artifact didn't.
Where a listening verdict and a number disagree, the verdict wins and the metric
is suspect.

## Layout

```
amtw/
  spec.py           Field/Tool vocabulary; ONE declaration -> both the form and argparse
  registry.py       walks tools/, collects TOOL -- nothing lists tools by hand
  cli.py            builds subparsers from the registry; only `workbench` is hand-written
  core/             shared: paths, audio_utils, job, config, report, dsp
    dsp.py          STFT/periodicity primitives every fry tool must agree on
    paths.py        PROJECT_ROOT and the runtime root -- count parents carefully
  bench/            server.py + workbench.html (one file, no build step)
  tools/            ONE FOLDER PER TOOL, each exporting TOOL (or TOOLS)
    run/            the restore pipeline; stages/ are its internals
    harmonic/       fry-scrape repair (the one mechanism the user approved)
    detect/         fry detector (AUC 0.755; good enough to grade, not to gate)
    defizz/         spectral smear   -- unproven, see findings
    remod/          HF re-modulation -- unproven, see findings
    ab/             A/B listening server; ab.html is its UI
    midi/           merge + inspect, sharing one reader
    report/ doctor/
docs/               architecture, findings, how to add a tool
data/labels/        ground-truth listening labels -- the only way to check a detector
scripts/            runtime setup (venvs, model downloads)
```

## Conventions

- **Python 3.12, stdlib-first.** The workbench and A/B tool use `http.server`
  and hand-written HTML on purpose: no build step, no framework, no npm. Do not
  introduce a frontend toolchain.
- **New third-party dependency = justify it in the PR.** Four venvs already
  exist because engine dependencies conflict; adding to that is expensive.
- **Tools communicate over files and subprocesses**, not shared imports, so a
  tool needing an incompatible dependency set can live in its own venv.
- **Never write model weights or audio into the project folder.** Heavy,
  regenerable things go to the runtime root, so the repo stays clonable and
  nothing large is ever committed. `input/` and `output/` are gitignored.
- **Update [CHANGELOG.md](CHANGELOG.md)** under `[Unreleased]` in the same
  change. This is how the next agent learns what just moved.

## Before you finish

- [ ] `.\amtw.ps1 doctor` still passes
- [ ] the tool runs from the workbench UI, not just the CLI
- [ ] the tool's folder exports `TOOL`, with the `note` field carrying anything
      hard-won that a user should see at the moment they use it
- [ ] CHANGELOG updated
- [ ] anything you *measured* went into `docs/findings.md`, including negative
      results — those are worth more than the positive ones here

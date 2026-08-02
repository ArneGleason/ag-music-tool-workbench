# Contributing

Most work here is done by AI agents, one session at a time, each starting fresh.
If that's you, read [AGENTS.md](AGENTS.md) — it's the short version of this
file plus the rules that keep sessions from undoing each other.

## Setup

Windows, Python 3.12 on the `py` launcher, git, ffmpeg on PATH, and an NVIDIA
GPU for the model stages.

```powershell
.\scripts\setup_runtime.ps1     # builds four venvs, downloads checkpoints; safe to re-run
.\amtw.ps1 doctor               # should print all ok
```

The MIDI tools, the workbench, and the A/B tool need only the `main` venv and no
GPU. Working on those doesn't require the full setup.

## Adding a tool

The whole recipe is in [docs/adding-a-tool.md](docs/adding-a-tool.md): a module,
a CLI subcommand, one entry in `amtw/tools.py`.

The catalog entry is not optional. A tool that only exists in the CLI is
invisible to the person this is built for, who does not want to type commands.

## Before opening a PR

- [ ] `.\amtw.ps1 doctor` passes
- [ ] the tool runs **from the workbench UI**, not just the CLI
- [ ] you ran it on a real file and can say what came out
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] anything measured went into `docs/findings.md`, negative results included

## Style

- Python 3.12, `from __future__ import annotations`, 4-space indent, ~95 columns.
- **Comments explain why, not what.** This codebase is unusually comment-dense on
  purpose: the non-obvious decisions (four venvs, the runtime split, why a global
  normalise would break the untouched-audio guarantee) are the ones a future
  reader will otherwise undo. Match that.
- Stdlib-first. The workbench and A/B tool deliberately have no frontend
  toolchain — no framework, no bundler, no npm. Don't introduce one.
- A new third-party dependency needs justification in the PR. Four venvs already
  exist because dependencies conflict.
- Tools communicate over files and subprocesses, not shared imports. That's what
  lets a tool with incompatible dependencies live in its own venv.

## Things that will get a change rejected

- Writing model weights or working audio into the project folder — it's
  cloud-synced, and a sync client will corrupt a venv mid-install.
- Re-running an experiment that [docs/findings.md](docs/findings.md) already
  settled, without saying why the recorded result is wrong.
- Claiming something works without having run it.
- Global normalisation inside `amtw harmonic`. It rescales untouched regions and
  breaks the guarantee that unmarked audio comes back bit-identical.

## Reporting a finding

`docs/findings.md` is the project's memory. When you measure something, record
it there with the numbers, not the conclusion alone — a later session may
disagree with your interpretation but still need your data.

Negative results and measurement *errors* belong there too. Three of the entries
in that file are mistakes that produced confident wrong answers, and they're
kept because knowing the failure mode is what stops it recurring.

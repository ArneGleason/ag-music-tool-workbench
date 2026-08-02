# CLAUDE.md

Read **[AGENTS.md](AGENTS.md)** — it is the working contract for this repo and
applies to you.

The two things most likely to waste this session:

1. **[docs/findings.md](docs/findings.md)** records what has already been
   measured and settled, including dead ends and three measurement errors that
   produced confident wrong answers. Read it before proposing an experiment.
2. **A tool is not done until it is on the bench.** Every tool needs an entry in
   `amtw/tools.py` so it appears in the workbench UI. See
   [docs/adding-a-tool.md](docs/adding-a-tool.md).

Run things with `.\amtw.ps1 <command>` (wraps the `main` venv's python).
`.\amtw.ps1 doctor` checks the environment.

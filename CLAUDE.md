# CLAUDE.md

Read **[AGENTS.md](AGENTS.md)** — it is the working contract for this repo and
applies to you.

The three things most likely to waste this session:

1. **[docs/findings.md](docs/findings.md)** records what has already been
   measured and settled, including dead ends and three measurement errors that
   produced confident wrong answers. Read it before proposing an experiment.
2. **A tool is not done until it is on the bench.** A tool is one folder under
   `amtw/tools/` exporting `TOOL`; the bench form and the CLI subcommand are
   both generated from that one declaration. See
   [docs/adding-a-tool.md](docs/adding-a-tool.md).
3. **Verdicts come from the user's ears, through `amtw ab`.** You cannot hear
   anything: prepare the comparison, launch it, read the JSON back. See
   [docs/using-the-ab-tool.md](docs/using-the-ab-tool.md).

Run things with `.\amtw.ps1 <command>` (wraps the `main` venv's python).
`.\amtw.ps1 doctor` checks the environment.

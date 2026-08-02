"""Rebuild report.html for an existing job folder."""
from __future__ import annotations

import argparse
from pathlib import Path

from ...spec import Field, Tool


def run(args: argparse.Namespace) -> int:
    import json

    from ...core import report as report_mod
    from ...core.job import Job

    root = Path(args.jobdir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    job = Job(source=Path(manifest["source"]), root=root, manifest=manifest)
    rep = report_mod.build(job)
    print(rep)
    return 0


TOOL = Tool(
    name="report", title="Rebuild report", group="Pipeline", run=run, order=20,
    help="(re)build report.html for a job dir",
    blurb="Regenerates report.html for an existing job folder.",
    fields=[
        Field("jobdir", "Job folder", "dir", root="output", required=True),
    ],
)

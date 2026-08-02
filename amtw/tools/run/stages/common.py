"""Shared helpers for stage subprocesses."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from ....core.paths import subprocess_env


class StageError(RuntimeError):
    pass


def run_logged(cmd: list[str], log_path: Path, cwd: Path | None = None) -> None:
    """Run a stage subprocess, teeing output to a log file. Raises StageError
    with the log tail on failure."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        log.write("+ " + " ".join(str(c) for c in cmd) + "\n\n")
        log.flush()
        proc = subprocess.Popen(
            [str(c) for c in cmd],
            cwd=str(cwd) if cwd else None,
            env=subprocess_env(),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        code = proc.wait()
    elapsed = time.time() - t0
    if code != 0:
        tail = "".join(
            log_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)[-30:]
        )
        raise StageError(
            f"subprocess failed (exit {code}, {elapsed:.0f}s): {cmd[0]}\n--- log tail ---\n{tail}"
        )


def newest_wav(directory: Path, exclude: set[str] | None = None) -> Path:
    # rglob: some engines (MSST) nest outputs one directory per input file
    wavs = [
        p for p in directory.rglob("*.wav")
        if not exclude or p.name not in exclude
    ]
    if not wavs:
        raise StageError(f"no wav produced in {directory}")
    return max(wavs, key=lambda p: p.stat().st_mtime)

"""Stage 2 — spectral restoration: Lew's Apollo vocal enhancer via the MSST
framework (chunked inference with overlap built in). Runs as a subprocess in
the msst venv.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from ..config import PipelineCfg
from ..job import Job
from ..paths import APOLLO_CKPT, APOLLO_CONFIG, MSST_DIR, venv_python
from .common import StageError, newest_wav, run_logged


def run(cfg: PipelineCfg, job: Job, in_wav: Path) -> Path:
    stage_dir = job.dir("superres")
    t0 = time.time()

    if not APOLLO_CKPT.exists() or not APOLLO_CONFIG.exists():
        raise StageError(
            f"Apollo checkpoint/config missing under {APOLLO_CKPT.parent} — "
            "run: python -m amtw doctor"
        )

    # MSST processes folders; give it a folder containing only our file.
    in_dir = stage_dir / "in"
    in_dir.mkdir(exist_ok=True)
    staged = in_dir / in_wav.name
    shutil.copy2(in_wav, staged)

    out_dir = stage_dir / "out"
    out_dir.mkdir(exist_ok=True)

    run_logged(
        [
            venv_python("msst"),
            MSST_DIR / "inference.py",
            "--model_type", "apollo",
            "--config_path", APOLLO_CONFIG,
            "--start_check_point", APOLLO_CKPT,
            "--input_folder", in_dir,
            "--store_dir", out_dir,
        ],
        log_path=stage_dir / "stage.log",
        cwd=MSST_DIR,
    )

    result = newest_wav(out_dir)
    final = stage_dir / f"{in_wav.stem}_apollo.wav"
    shutil.move(str(result), final)

    job.record(
        "superres",
        model="apollo_vocals_ep54 (Lew)",
        out=str(final),
        seconds=round(time.time() - t0, 1),
    )
    return final

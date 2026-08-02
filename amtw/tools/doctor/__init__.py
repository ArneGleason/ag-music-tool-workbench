"""Environment check: venvs, CUDA, third-party clones, model checkpoints."""
from __future__ import annotations

import argparse

from ...spec import Tool


def run(_args: argparse.Namespace) -> int:
    import subprocess

    from ...core.paths import (APOLLO_CKPT, APOLLO_CONFIG, MSST_DIR, RUNTIME_ROOT,
                               SEEDVC_DIR, venv_python)

    ok = True

    def check(label: str, cond: bool, extra: str = "") -> None:
        nonlocal ok
        mark = "ok " if cond else "FAIL"
        print(f"  [{mark}] {label}{(' — ' + extra) if extra else ''}")
        ok = ok and cond

    print(f"runtime root: {RUNTIME_ROOT}")
    for env in ("main", "msst", "seedvc"):
        py = venv_python(env)
        if not py.exists():
            check(f"venv {env}", False, "missing")
            continue
        try:
            out = subprocess.run(
                [str(py), "-c",
                 "import torch; print(torch.__version__, torch.cuda.is_available())"],
                capture_output=True, text=True, timeout=120,
            ).stdout.strip()
            check(f"venv {env}", "True" in out, f"torch {out}")
        except Exception as e:  # noqa: BLE001
            check(f"venv {env}", False, str(e))

    check("seed-vc clone", (SEEDVC_DIR / "inference.py").exists())
    check("msst clone", (MSST_DIR / "inference.py").exists())
    check("apollo ckpt", APOLLO_CKPT.exists())
    check("apollo config", APOLLO_CONFIG.exists())

    try:
        import audio_separator  # noqa: F401
        check("audio-separator importable (main env)", True)
    except ImportError:
        check("audio-separator importable (main env)", False,
              "run amtw from the main venv python")

    # Optional. harm-render falls back to its built-in synth without these, so
    # a missing soundfont is a downgrade, not a failure — it must not turn
    # doctor red.
    from ..harmony import render as _r

    sf, exe = _r.find_soundfont(), _r.find_fluidsynth()
    print(f"  [{'ok ' if sf else '--'}] soundfont"
          f" — {sf.name if sf else f'none in {_r.SOUNDFONT_DIR} (harm-render uses its built-in synth)'}")
    print(f"  [{'ok ' if exe else '--'}] fluidsynth"
          f" — {exe if exe else 'not installed (optional)'}")

    print("all good" if ok else "problems found — see FAIL lines")
    return 0 if ok else 1


TOOL = Tool(
    name="doctor", title="Doctor", group="Pipeline", run=run, order=90,
    help="check venvs, clones, models, CUDA",
    blurb="Checks venvs, CUDA, third-party clones and model checkpoints.",
    fields=[],
)

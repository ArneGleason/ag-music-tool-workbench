"""Path layout.

Code lives in the repo. Everything heavy and regenerable — venvs, model
checkpoints, third-party clones, HF cache — lives in a local runtime root, so
the repo stays small enough to clone and nothing large is ever version
controlled or synced.
"""
import os
from pathlib import Path

# amtw/core/paths.py -> amtw/core -> amtw -> the repo root.
#
# Count carefully before moving this file. It broke exactly once, when paths.py
# moved from amtw/ into amtw/core/ and the old `parent.parent` quietly started
# resolving to amtw/ instead of the repo root — every tool the workbench
# launched then died with "No module named amtw", because it set the
# subprocess cwd from here.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The runtime folder is still named VocalStemRegen: it holds four venvs whose
# absolute paths are baked into their own scripts, plus several GB of model
# weights. Renaming it would mean a full re-setup and re-download for no
# functional gain, so the legacy name stays. AMTW_RUNTIME overrides it;
# VSR_RUNTIME still works for anyone who set it before the rename.
_RUNTIME_OVERRIDE = os.environ.get("AMTW_RUNTIME") or os.environ.get("VSR_RUNTIME")
RUNTIME_ROOT = Path(_RUNTIME_OVERRIDE) if _RUNTIME_OVERRIDE \
    else Path(os.environ["LOCALAPPDATA"]) / "VocalStemRegen"

VENVS = RUNTIME_ROOT / "venvs"
THIRD_PARTY = RUNTIME_ROOT / "third_party"
MODELS = RUNTIME_ROOT / "models"
HF_CACHE = RUNTIME_ROOT / "hf_cache"
LOGS = RUNTIME_ROOT / "logs"

SEEDVC_DIR = THIRD_PARTY / "seed-vc"
MSST_DIR = THIRD_PARTY / "msst"
YMSVC_DIR = THIRD_PARTY / "yingmusic"
YM_CKPT = MODELS / "yingmusic" / "YingMusic-SVC-full.pt"

APOLLO_CKPT = MODELS / "apollo" / "model_apollo_vocals_ep_54.ckpt"
APOLLO_CONFIG = MODELS / "apollo" / "config_apollo_vocals_ep_54.yaml"
UVR_MODEL_DIR = MODELS / "uvr"

INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"


def venv_python(name: str) -> Path:
    return VENVS / name / "Scripts" / "python.exe"


def subprocess_env() -> dict:
    """Environment for stage subprocesses: HF downloads go to the local cache."""
    env = os.environ.copy()
    env["HF_HOME"] = str(HF_CACHE)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env

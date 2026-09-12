"""Path layout.

Code lives in the repo. Everything heavy and regenerable — venvs, model
checkpoints, third-party clones, HF cache — lives in a local runtime root, so
the repo stays small enough to clone and nothing large is ever version
controlled or synced.
"""
import os
import json
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
#
# Every candidate is stripped. An environment variable with trailing
# whitespace prints identically to a clean one and fails every path test built
# from it -- "C:\...\Local \VocalStemRegen" looks right in an error message and
# exists nowhere. USERPROFILE is a fallback for the same reason: if
# LOCALAPPDATA is unusable, the standard location under the profile still is.
def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


_RUNTIME_OVERRIDE = _env("AMTW_RUNTIME") or _env("VSR_RUNTIME")
# USERPROFILE is stable across packaged apps; LOCALAPPDATA may be redirected
# into an app sandbox. A bad explicit pointer must fail, not create a new runtime.
_pointer = Path(_env("USERPROFILE") or Path.home()) / ".config" / "amtw" / "runtime.json"
if not _RUNTIME_OVERRIDE and _pointer.exists():
    _RUNTIME_OVERRIDE = json.loads(_pointer.read_text(encoding="utf-8-sig"))["runtime_root"]
if _RUNTIME_OVERRIDE:
    RUNTIME_ROOT = Path(_RUNTIME_OVERRIDE)
else:
    _local = _env("LOCALAPPDATA")
    if not _local and _env("USERPROFILE"):
        _local = str(Path(_env("USERPROFILE")) / "AppData" / "Local")
    _candidate = Path(_local) / "VocalStemRegen" if _local else None
    if _candidate is None or not _candidate.exists():
        _alt = (Path(_env("USERPROFILE")) / "AppData" / "Local" / "VocalStemRegen"
                if _env("USERPROFILE") else None)
        if _alt is not None and _alt.exists():
            _candidate = _alt
    _legacy = Path(_env("USERPROFILE") or Path.home()) / "AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Local/VocalStemRegen"
    if (_legacy / "models/apollo/model_apollo_vocals_ep_54.ckpt").exists() and not (_candidate and (_candidate / "models/apollo/model_apollo_vocals_ep_54.ckpt").exists()):
        _candidate = _legacy
    RUNTIME_ROOT = _candidate or Path(_local or ".") / "VocalStemRegen"

RUNTIME_ROOT = RUNTIME_ROOT.resolve()

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
# Lew's universal Apollo (any instrument, not just vocals). Rehost:
# huggingface.co/ASesYusuf1/Apollo_universal_model (the model MVSEP runs as
# "Universal Super Resolution"). Optional -- doctor reports it without failing.
APOLLO_UNIVERSAL_CKPT = MODELS / "apollo" / "model_apollo_universal.ckpt"
APOLLO_UNIVERSAL_CONFIG = MODELS / "apollo" / "config_apollo_universal.yaml"
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

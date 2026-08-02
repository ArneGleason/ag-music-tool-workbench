"""The restore pipeline.

Stages live in `stages/` because they are this tool's internals, not a shared
library — nothing else runs them. Note that resynth is **off by the evidence**:
three engines across two architecture families all failed with modulation
instability. The restore path (cleanup + superres) is the product.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ...core import audio_utils
from ...core.config import PipelineCfg
from ...core.job import Job
from ...spec import AUDIO, Field, Tool


def run(args: argparse.Namespace) -> int:
    from ...core import report as report_mod
    from ...core.config import DEREVERB_MODELS
    from .stages import cleanup, finalize, resynth, superres

    cfg = PipelineCfg()
    cfg.cleanup.enabled = "cleanup" in args.stages
    cfg.superres.enabled = "superres" in args.stages
    cfg.resynth.enabled = "resynth" in args.stages

    cfg.cleanup.denoise = args.denoise
    cfg.cleanup.deecho = args.deecho
    cfg.cleanup.dereverb_model = DEREVERB_MODELS[args.dereverb]
    cfg.resynth.engine = args.engine
    cfg.resynth.diffusion_steps = args.diffusion_steps
    cfg.resynth.inference_cfg_rate = args.cfg_rate
    cfg.resynth.semitone_shift = args.semitone_shift
    cfg.resynth.ref_seconds = args.ref_seconds
    cfg.resynth.reference_wav = args.reference or ""

    src = Path(args.input).resolve()
    if not src.exists():
        print(f"input not found: {src}", file=sys.stderr)
        return 2

    if args.sr:
        cfg.finalize.output_sr = args.sr
    elif args.match_input_sr:
        import soundfile as sf
        cfg.finalize.output_sr = sf.info(str(src)).samplerate

    job = Job.create(src, name=args.name)
    print(f"job: {job.root}")

    t0 = time.time()
    current = audio_utils.ffmpeg_to_wav(src, job.dir("input") / f"{src.stem}.wav")
    original = current
    print(f"[00 input   ] decoded -> {current.name}")

    if cfg.cleanup.enabled:
        current = cleanup.run(cfg, job, current)
        print(f"[10 cleanup ] -> {current.name}")
    if cfg.superres.enabled:
        current = superres.run(cfg, job, current)
        print(f"[20 superres] -> {current.name}")
    if cfg.resynth.enabled:
        current = resynth.run(cfg, job, current)
        print(f"[30 resynth ] -> {current.name}")

    final = finalize.run(cfg, job, current, original)
    print(f"[40 final   ] -> {final.name}")

    rep = report_mod.build(job)
    print(f"[report     ] -> {rep}")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


TOOL = Tool(
    name="run", title="Run pipeline", group="Pipeline", run=run, order=10,
    help="run the pipeline on a vocal stem",
    blurb="Full restore + re-synthesis on a vocal stem. Writes a job folder "
          "with every stage's output and a comparison report.",
    note="Restoration-only (cleanup + superres, no resynth) can't touch grit "
         "because it never re-synthesizes — worth A/B-ing on every song.",
    fields=[
        Field("input", "Vocal stem", "file", accept=AUDIO, root="input",
              required=True, help="wav / mp3 / flac / m4a"),
        Field("stages", "Stages", "multichoice", flag="--stages",
              choices=["cleanup", "superres", "resynth"],
              default=["cleanup", "superres", "resynth"],
              help="stages to run, space- or comma-separated"),
        Field("name", "Job name", "text", flag="--name",
              help="blank = <stem>_<timestamp>"),
        Field("deecho", "De-echo pass", "bool", flag="--deecho",
              help="kills short slap reflections that resynth otherwise "
                   "re-renders as a doubled vocal"),
        Field("dereverb", "De-reverb model", "choice", flag="--dereverb",
              choices=["classic", "roformer"], default="classic",
              help="measured difference between these is ~4% — classic is fine"),
        Field("engine", "Resynth engine", "choice", flag="--engine",
              choices=["seedvc", "yingmusic"], default="seedvc"),
        Field("reference", "Timbre reference", "file", flag="--reference",
              accept=AUDIO, root="output", advanced=True,
              help="blank = auto-picked from the stem itself"),
        Field("cfg_rate", "CFG rate", "float", flag="--cfg-rate", default=0.7,
              min=0.0, max=1.0, step=0.05, advanced=True,
              help="lower keeps more source grit; higher pushes toward the reference"),
        Field("diffusion_steps", "Diffusion steps", "int", flag="--diffusion-steps",
              default=50, min=10, max=100, step=5, advanced=True),
        Field("semitone_shift", "Semitone shift", "int", flag="--semitone-shift",
              default=0, min=-12, max=12, step=1, advanced=True),
        Field("ref_seconds", "Reference seconds", "float", flag="--ref-seconds",
              default=25.0, min=5, max=60, step=1, advanced=True),
        Field("denoise", "Extra de-noise pass", "bool", flag="--denoise",
              advanced=True, help="add UVR-DeNoise pass after de-reverb"),
        Field("sr", "Output sample rate", "int", flag="--sr", default=0,
              advanced=True, help="0 keeps the pipeline's native 44100"),
        Field("match_input_sr", "Match input rate", "bool", flag="--match-input-sr",
              advanced=True, help="resample final deliverable to the source stem's rate"),
    ],
)

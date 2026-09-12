"""VocalStemRegen wrapper for Vevo2 style-preserved SVC (FM-only path).

Run from the Amphion repo root so `models.*` imports resolve. Weights are
snapshot-downloaded to ./ckpts/Vevo2 on first use.
"""
import argparse
import os

import torch
from huggingface_hub import snapshot_download

from models.svc.vevo2.vevo2_utils import *  # noqa: F401,F403


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True, help="timbre reference wav")
    ap.add_argument("--output", required=True)
    ap.add_argument("--steps", type=int, default=32)
    ap.add_argument("--pitch-shift", default="False",
                    help="True shifts source toward reference range; for "
                         "self-conversion leave False")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}", flush=True)

    local_dir = snapshot_download(
        repo_id="RMSnow/Vevo2",
        repo_type="model",
        local_dir="./ckpts/Vevo2",
    )
    print(f"weights: {local_dir}", flush=True)

    pipeline = Vevo2InferencePipeline(  # noqa: F405
        content_style_tokenizer_ckpt_path=os.path.join(
            local_dir, "tokenizer/contentstyle_fvq16384_12.5hz"),
        fmt_cfg_path=os.path.join(
            local_dir, "acoustic_modeling/fm_emilia101k_singnet7k_repa/config.json"),
        fmt_ckpt_path=os.path.join(
            local_dir, "acoustic_modeling/fm_emilia101k_singnet7k_repa"),
        vocoder_cfg_path=os.path.join(local_dir, "vocoder/config.json"),
        vocoder_ckpt_path=os.path.join(local_dir, "vocoder"),
        device=device,
    )
    print("pipeline loaded", flush=True)

    gen_audio = pipeline.inference_fm(
        src_wav_path=args.source,
        timbre_ref_wav_path=args.target,
        use_pitch_shift=(args.pitch_shift.lower() == "true"),
        flow_matching_steps=args.steps,
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    save_audio(gen_audio, output_path=args.output)  # noqa: F405
    print(f"VEVO2-OK wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()

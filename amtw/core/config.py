"""Pipeline configuration. One dataclass per stage, defaults tuned for
Suno vocal stems on an RTX 4080 (16GB)."""
from dataclasses import dataclass, field


DEREVERB_MODELS = {
    "classic": "UVR-DeEcho-DeReverb.pth",
    "roformer": "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
}


@dataclass
class CleanupCfg:
    enabled: bool = True
    dereverb_model: str = "UVR-DeEcho-DeReverb.pth"
    deecho: bool = False                  # extra pass for short slap/early
                                          # reflections (Sucial roformer)
    deecho_model: str = "dereverb-echo_mel_band_roformer_sdr_13.4843_v2.ckpt"
    denoise: bool = False                 # opt-in: can dull breathy vocals
    denoise_model: str = "UVR-DeNoise.pth"


@dataclass
class SuperresCfg:
    enabled: bool = True                  # Apollo vocal enhancer via MSST


@dataclass
class ResynthCfg:
    enabled: bool = True
    engine: str = "seedvc"                # seedvc | yingmusic
    diffusion_steps: int = 50             # 30 fast / 50 good / 100 best
    inference_cfg_rate: float = 0.7
    length_adjust: float = 1.0
    semitone_shift: int = 0
    fp16: bool = True
    ref_seconds: float = 25.0             # reference window for self-conversion
    reference_wav: str = ""               # optional: explicit reference audio path
                                          # (e.g. a cleaner section from another song
                                          # by the same Suno persona)


@dataclass
class FinalizeCfg:
    match_input_loudness: bool = True     # match final LUFS to the original stem
    output_sr: int = 0                    # 0 = keep pipeline rate (44100);
                                          # e.g. 48000 for native 48k delivery


@dataclass
class PipelineCfg:
    cleanup: CleanupCfg = field(default_factory=CleanupCfg)
    superres: SuperresCfg = field(default_factory=SuperresCfg)
    resynth: ResynthCfg = field(default_factory=ResynthCfg)
    finalize: FinalizeCfg = field(default_factory=FinalizeCfg)

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import webrtcvad

from .config import MODEL_ID, MODEL_REVISION, PREPROCESSING_VERSION
from .media import MediaError


@dataclass(frozen=True)
class ModelInfo:
    id: str = MODEL_ID
    revision: str = MODEL_REVISION
    preprocessing_version: str = PREPROCESSING_VERSION
    dimension: int = 192


def load_pcm(path: Path):
    audio, rate = sf.read(path, dtype="float32")
    if rate != 16000 or audio.ndim != 1 or not np.isfinite(audio).all():
        raise MediaError("Model requires finite 16 kHz mono PCM audio.")
    return audio


def speech_frames(audio: np.ndarray):
    detector = webrtcvad.Vad(2)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    frame = 480  # 30ms at 16kHz
    return [(start, start + frame) for start in range(0, len(pcm) - frame + 1, frame)
            if detector.is_speech(pcm[start:start + frame].tobytes(), 16000)]


def prepare_voice(path: Path, reference: bool = False):
    audio = load_pcm(path)
    duration = len(audio) / 16000
    if reference and not 3 <= duration <= 60:
        raise MediaError("Reference must be 3–60 seconds; prefer 10–30 seconds of one speaker.")
    frames = speech_frames(audio)
    voice_seconds = len(frames) * .03
    if voice_seconds < (3 if reference else 1):
        raise MediaError("Insufficient speech; reference needs at least 3 seconds of voiced audio.")
    # Preserve pauses between first/last voiced frame; source timestamps remain separate.
    return audio[frames[0][0]:frames[-1][1]], voice_seconds


def segment_windows(path: Path):
    audio = load_pcm(path)
    frames = speech_frames(audio)
    if not frames:
        raise MediaError("No speech detected in the audio.")
    end = len(audio)
    for start in range(0, end, 80000):
        stop = min(start + 160000, end)
        if stop - start < 48000:
            continue
        spoken = sum(max(0, min(b, stop) - max(a, start)) for a, b in frames)
        if spoken < 16000:
            continue
        yield start // 16, stop // 16, audio[start:stop]


class EmbeddingModel:
    """Trusted installed SpeechBrain architecture, pinned weights; no remote Python/YAML."""

    info = ModelInfo()

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / MODEL_REVISION
        self.lock = threading.Lock()
        self.model = None
        self.features = None
        self.normalizer = None
        self.state = "missing"
        self.error = None
        self.downloaded_bytes = 0
        self.total_bytes = None

    def status(self):
        if self.state == "downloading":
            # Hugging Face's partial file is the source of progress, never a timer estimate.
            download_dir = self.cache_dir / ".cache/huggingface/download"
            partials = list(download_dir.glob("*.incomplete"))
            self.downloaded_bytes = sum(p.stat().st_size for p in partials if p.exists())
        return {**asdict(self.info), "status": self.state, "error": self.error,
                "source": f"https://huggingface.co/{MODEL_ID}/tree/{MODEL_REVISION}",
                "downloaded_bytes": self.downloaded_bytes, "total_bytes": self.total_bytes}

    def load(self, offline: bool = False):
        with self.lock:
            if self.model is not None:
                return
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.state, self.error = "downloading", None
            try:
                import torch
                from huggingface_hub import HfApi, hf_hub_download
                from speechbrain.lobes.features import Fbank
                from speechbrain.lobes.models.ECAPA_TDNN import ECAPA_TDNN
                from speechbrain.processing.features import InputNormalization

                name = "embedding_model.ckpt"
                weight_path = self.cache_dir / name
                if weight_path.exists():
                    self.state = "loading"
                if not weight_path.exists():
                    if offline:
                        raise MediaError("Pinned model is not cached; prepare it online first.")
                    metadata = HfApi().model_info(MODEL_ID, revision=MODEL_REVISION,
                                                 files_metadata=True)
                    file = next(item for item in metadata.siblings if item.rfilename == name)
                    self.total_bytes = file.size
                    cached = hf_hub_download(MODEL_ID, name, revision=MODEL_REVISION,
                                             local_dir=self.cache_dir)
                    weight_path = Path(cached)
                self.downloaded_bytes = weight_path.stat().st_size
                self.total_bytes = self.downloaded_bytes
                self.state = "loading"
                expected_hash = "0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2"
                if hashlib.sha256(weight_path.read_bytes()).hexdigest() != expected_hash:
                    raise MediaError("Pinned model checksum mismatch; remove corrupt cache and retry.")
                torch.set_num_threads(4)
                self.features = Fbank(n_mels=80)
                self.normalizer = InputNormalization(norm_type="sentence", std_norm=False)
                model = ECAPA_TDNN(input_size=80, channels=[1024, 1024, 1024, 1024, 3072],
                                  kernel_sizes=[5, 3, 3, 3, 1], dilations=[1, 2, 3, 4, 1],
                                  attention_channels=128, lin_neurons=192)
                # Only tensor weights are deserialized. No downloaded hyperparams are executed.
                weights = torch.load(weight_path, map_location="cpu", weights_only=True)
                model.load_state_dict(weights, strict=True)
                self.model = model.eval()
                self.state = "ready"
                (self.cache_dir / "model-info.json").write_text(json.dumps(asdict(self.info)))
            except Exception as exc:
                self.state = "failed"
                self.error = f"Model preparation failed ({type(exc).__name__}); retry download."
                raise MediaError(self.error) from exc

    def embed_samples(self, audio: np.ndarray):
        if self.model is None:
            raise MediaError("Model is not ready; prepare the pinned model first.")
        import torch
        with self.lock, torch.inference_mode():
            tensor = torch.from_numpy(np.asarray(audio, dtype=np.float32)).unsqueeze(0)
            features = self.features(tensor)
            features = self.normalizer(features, torch.ones(1))
            vector = self.model(features).squeeze().numpy().astype(np.float32)
        if vector.shape != (192,) or not np.isfinite(vector).all():
            raise MediaError("Model produced an invalid embedding.")
        norm = np.linalg.norm(vector)
        if norm < 1e-8:
            raise MediaError("Model produced a zero embedding.")
        return vector / norm

    def embed_audio(self, path: Path):
        audio, _ = prepare_voice(path, reference=True)
        return self.embed_samples(audio)

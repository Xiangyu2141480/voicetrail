import argparse
import json
import resource
import time
from pathlib import Path

from backend.app.config import Settings
from backend.app.embedding import EmbeddingModel
from backend.app.media import extract_audio

parser = argparse.ArgumentParser()
parser.add_argument("audio", type=Path)
parser.add_argument("--offline", action="store_true")
args = parser.parse_args()
settings = Settings.from_env()
settings.prepare()
model = EmbeddingModel(settings.data_dir / "models")
started = time.perf_counter()
model.load(offline=args.offline)
loaded = time.perf_counter()
normalized = settings.data_dir / "tmp/smoke.wav"
extract_audio(args.audio, normalized)
vector = model.embed_audio(normalized)
print(json.dumps({"model": model.status(), "dimension": len(vector),
                  "norm": float((vector @ vector) ** .5),
                  "load_seconds": loaded - started,
                  "inference_seconds": time.perf_counter() - loaded,
                  "peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "device": "cpu", "threads": 4}, indent=2))
normalized.unlink(missing_ok=True)

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

import numpy as np

from backend.app.config import Settings
from backend.app.embedding import EmbeddingModel, prepare_voice
from backend.app.media import extract_audio
from backend.app.search import rank_segments

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", required=True, type=Path)
parser.add_argument("--manifest", type=Path, default=Path("docs/evaluation_manifest.json"))
parser.add_argument("--output", type=Path, default=Path("docs/retrieval_results.json"))
args = parser.parse_args()
frozen = args.manifest.read_bytes()
manifest = json.loads(frozen)
settings = Settings.from_env()
settings.prepare()
model = EmbeddingModel(settings.data_dir / "models")
start = time.perf_counter()
model.load(offline=True)
vectors = {}
voiced = {}
for sample in manifest["samples"]:
    source = args.dataset / sample["path"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == sample["sha256"], sample["id"]
    normalized = settings.data_dir / "tmp/evaluation.wav"
    extract_audio(source, normalized)
    audio, voice_seconds = prepare_voice(normalized, reference=True)
    vectors[sample["id"]] = model.embed_samples(audio)
    voiced[sample["id"]] = voice_seconds
normalized.unlink(missing_ok=True)
targets = [s for s in manifest["samples"] if s["role"] == "target"]
queries = []
for speaker in manifest["known_speakers"]:
    reference = next(s for s in manifest["samples"]
                     if s["role"] == "reference" and s["speaker"] == speaker)
    ranked = rank_segments(vectors[reference["id"]],
                           np.stack([vectors[s["id"]] for s in targets]), len(targets))
    rows = [{"sample_id": targets[i]["id"], "speaker": targets[i]["speaker"],
             "recording": targets[i]["recording"], "score": score,
             "positive": targets[i]["speaker"] == speaker} for i, score in ranked]
    positive = [r["score"] for r in rows if r["positive"]]
    negative = [r["score"] for r in rows if not r["positive"]]
    assert all(s["recording"] != reference["recording"]
               for s in targets if s["speaker"] == speaker)
    queries.append({"reference_id": reference["id"], "speaker": speaker, "results": rows,
                    "passed": bool(positive and negative and min(positive) > max(negative))})
report = {"manifest_sha256": hashlib.sha256(frozen).hexdigest(),
          "model": model.status(), "device": "cpu", "threads": 4,
          "elapsed_seconds": time.perf_counter() - start,
          "peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "voiced_seconds": voiced, "queries": queries,
          "passed": all(q["passed"] for q in queries),
          "limitations": "Five English clean audiobook utterances, three speakers, different "
                         "chapters; no claim of accuracy, cross-age or independent environments."}
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)

"""Real-model API gate. No network, no test doubles, temporary isolated DB."""
import hashlib
import io
import json
import resource
import shutil
import socket
import tempfile
import time
import zipfile
from pathlib import Path

import soundfile as sf
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.db import Database
from backend.app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def deny_network(*args, **kwargs):
    raise RuntimeError("Real API gate forbids network connections.")


def wait_job(client, identifier):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{identifier}").json()
        if job["status"] in ("completed", "failed", "cancelled", "interrupted"):
            assert job["status"] == "completed", job
            return job
        time.sleep(.1)
    raise AssertionError("Job timed out.")


def ready(client):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        response = client.get("/api/health")
        assert response.status_code == 200, response.text
        info = response.json()
        if info["model"]["status"] == "ready":
            return {"X-VoiceTrail-Session": info["session_token"]}
        assert info["model"]["status"] != "failed", info["model"]
        time.sleep(.1)
    raise AssertionError("Cached model did not load.")


def main():
    base = Settings.from_env()
    base.prepare()
    manifest_bytes = (ROOT / "docs/evaluation_manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    dataset = base.data_dir / "evaluation"
    for sample in manifest["samples"]:
        source = dataset / sample["path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == sample["sha256"], sample["id"]
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    measurements = {}
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="real-api-", dir=base.data_dir / "tmp") as directory:
        runtime = Path(directory)
        settings = Settings(runtime)
        settings.prepare()
        shutil.rmtree(runtime / "models")
        (runtime / "models").symlink_to(base.data_dir / "models", target_is_directory=True)
        library_root = runtime / "许可音频 空格"
        library_root.mkdir()
        for sample in manifest["samples"]:
            if sample["role"] == "target":
                shutil.copyfile(dataset / sample["path"], library_root / f"{sample['id']} 原声.flac")
        queries = []
        with TestClient(create_app(settings), base_url="http://127.0.0.1:8765") as client:
            headers = ready(client)
            measurements["cached_start_seconds"] = time.perf_counter() - started

            def post(path, payload):
                response = client.post(path, json=payload, headers=headers)
                assert response.status_code == 200, response.text
                return response.json()
            library = post("/api/libraries", {"root": str(library_root)})["id"]
            timer = time.perf_counter()
            index = wait_job(client, post(f"/api/libraries/{library}/index", {})["job_id"])
            measurements["index_seconds"] = time.perf_counter() - timer
            assert index["processed"] == index["total"] == 3 and not index["error"], index
            db = Database(runtime / "index.sqlite")
            before = db.all("SELECT id FROM segment")
            timer = time.perf_counter()
            wait_job(client, post(f"/api/libraries/{library}/index", {})["job_id"])
            measurements["unchanged_scan_seconds"] = time.perf_counter() - timer
            assert db.all("SELECT id FROM segment") == before
            for speaker in manifest["known_speakers"]:
                sample = next(s for s in manifest["samples"]
                              if s["speaker"] == speaker and s["role"] == "reference")
                with (dataset / sample["path"]).open("rb") as file:
                    response = client.post("/api/references",
                                           files={"file": (sample["id"] + ".flac", file)},
                                           headers=headers)
                assert response.status_code == 200, response.text
                reference = response.json()["id"]
                timer = time.perf_counter()
                result = post("/api/search", {"reference_id": reference,
                                             "library_id": library, "top_k": 200})
                measurements[f"query_{speaker}_seconds"] = time.perf_counter() - timer
                rows = result["candidates"]
                positives = [row["similarity"] for row in rows if row["source_name"].startswith(speaker)]
                negatives = [row["similarity"] for row in rows if not row["source_name"].startswith(speaker)]
                assert max(positives) > max(negatives), rows
                queries.append({"speaker": speaker, "results": rows})
            candidate = queries[0]["results"][0]
            response = client.patch(f"/api/candidates/{candidate['id']}",
                                    json={"review_status": "confirmed"}, headers=headers)
            assert response.status_code == 200
            preview = client.get(f"/api/assets/{candidate['asset_id']}/media", params={
                "start_ms": candidate["start_ms"], "end_ms": candidate["end_ms"],
                "revision": candidate["source_revision"]})
            assert preview.status_code == 200, preview.text[:200]
            audio, rate = sf.read(io.BytesIO(preview.content))
            assert abs(len(audio) / rate * 1000 -
                       (candidate["end_ms"] - candidate["start_ms"])) <= 100
            export_job = wait_job(client, post("/api/exports", {
                "candidate_ids": [candidate["id"]]})["job_id"])
            download = client.get(f"/api/exports/{export_job['result_id']}/download")
            assert download.status_code == 200
            with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
                item = json.loads(archive.read("manifest.json"))["clips"][0]
                audio, rate = sf.read(io.BytesIO(archive.read(item["export_file"])))
                assert len(audio) > 0 and rate == 16000
            old_token = headers["X-VoiceTrail-Session"]
            reference_id = db.one("SELECT reference_id FROM candidate WHERE id=?", (candidate["id"],))[
                "reference_id"]
        with TestClient(create_app(settings), base_url="http://127.0.0.1:8765") as restarted:
            headers = ready(restarted)
            assert headers["X-VoiceTrail-Session"] != old_token
            response = restarted.post("/api/search", json={"reference_id": reference_id,
                                      "library_id": library}, headers=headers)
            assert response.status_code == 200, response.text
            row = next(row for row in response.json()["candidates"] if row["id"] == candidate["id"])
            assert row["review_status"] == "confirmed"
            assert len(restarted.get("/api/references").json()) == 2
            assert restarted.get(f"/api/exports/{export_job['result_id']}/download").status_code == 200
        report = {
            "passed": True, "network_connections_blocked": True, "dataset": manifest["dataset"],
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "device": "cpu",
            "files": 3, "indexed_segments": len(before), "source_duration_seconds": 53.065,
            "timings": measurements,
            "peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "restart_reference_review_export_persisted": True, "queries": queries,
            "limitations": "Different chapters of five English clean audiobook utterances. "
                           "Windowed API gate checks the best positive per speaker; the frozen "
                           "whole-utterance gate remains the stricter release prerequisite.",
        }
    (ROOT / "docs/api_results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "queries"}, indent=2))


if __name__ == "__main__":
    main()

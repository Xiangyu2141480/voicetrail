import hashlib
import json
import zipfile

import numpy as np
import pytest
import soundfile as sf

from backend.app.db import new_id
from backend.app.export import Exporter
from backend.app.media import MediaError, fingerprint
from tests.test_api import indexed  # noqa: F401
from tests.test_indexer import setup  # noqa: F401


@pytest.fixture
def candidate(indexed):  # noqa: F811 - pytest fixture registration import
    db, indexer, library, source, ref = indexed
    # Two tones make a measurable original-timeline boundary, not a fake quality result.
    audio = np.concatenate([np.sin(2 * np.pi * 300 * np.arange(16000) / 16000),
                            np.sin(2 * np.pi * 900 * np.arange(32000) / 16000)]).astype("float32")
    sf.write(source, audio * .3, 16000)
    segment = db.one("SELECT * FROM segment")
    db.execute("UPDATE source_revision SET sha256=?,duration_ms=3000 WHERE id=?",
               (fingerprint(source)["sha256"], segment["source_revision"]))
    db.execute("UPDATE segment SET start_ms=1000,end_ms=3000 WHERE id=?", (segment["id"],))
    identifier = new_id()
    db.execute("INSERT INTO candidate(id,reference_id,segment_id,similarity) VALUES(?,?,?,?)",
               (identifier, ref, segment["id"], .5))
    return db, indexer, source, identifier


def test_export_duration_boundaries_and_source_unmodified(candidate):
    db, indexer, source, identifier = candidate
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    exporter = Exporter(db, indexer.settings)
    job = db.enqueue("export", {"candidate_ids": [identifier]})
    exporter.run(job)
    assert db.get_job(job)["status"] == "completed"
    path = indexer.settings.data_dir / "exports" / f"{db.get_job(job)['result_id']}.zip"
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        item = manifest["clips"][0]
        assert item["start_ms"] == 1000 and item["end_ms"] == 3000
        assert item["source_sha256"] == before
        with archive.open(item["export_file"]) as handle:
            audio, rate = sf.read(handle)
        assert abs(len(audio) / rate - 2) <= .1
        dominant = np.fft.rfftfreq(len(audio), 1 / rate)[np.abs(np.fft.rfft(audio)).argmax()]
        assert abs(dominant - 900) < 2
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_stale_source_export_rejected(candidate):
    db, indexer, source, identifier = candidate
    source.write_bytes(source.read_bytes() + b"changed")
    job = db.enqueue("export", {"candidate_ids": [identifier]})
    with pytest.raises(MediaError, match="changed"):
        Exporter(db, indexer.settings).run(job)
    assert not list((indexer.settings.data_dir / "exports").glob("*.zip"))
    assert db.get_job(job)["status"] != "completed"


def test_ffmpeg_failure_no_success_zip(candidate, monkeypatch):
    db, indexer, source, identifier = candidate
    monkeypatch.setattr("backend.app.export.extract_audio",
                        lambda *args: (_ for _ in ()).throw(MediaError("decode failed")))
    job = db.enqueue("export", {"candidate_ids": [identifier]})
    with pytest.raises(MediaError):
        Exporter(db, indexer.settings).run(job)
    assert not list((indexer.settings.data_dir / "exports").glob("*.zip"))
    assert not db.all("SELECT * FROM export")


def test_cancel_export_never_commits_zip(candidate):
    db, indexer, source, identifier = candidate
    job = db.enqueue("export", {"candidate_ids": [identifier]})
    db.cancel(job)
    Exporter(db, indexer.settings).run(job)
    assert db.get_job(job)["status"] == "cancelled"
    assert not list((indexer.settings.data_dir / "exports").glob("*.zip"))

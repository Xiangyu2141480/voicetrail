import numpy as np
import pytest

from backend.app.config import Settings
from backend.app.db import Database
from backend.app.embedding import ModelInfo
from backend.app.indexer import Indexer
from backend.app.media import MediaError
from tests.test_media import generate


class TestOnlyModel:
    """Isolated transaction testing only; never used in production or quality evaluation."""
    info = ModelInfo()

    def embed_samples(self, audio):
        return np.ones(192, dtype=np.float32) / np.sqrt(192)

    def status(self):
        from dataclasses import asdict
        return {**asdict(self.info), "status": "ready", "error": None,
                "source": "isolated-test-only", "downloaded_bytes": 0, "total_bytes": None}


@pytest.fixture
def setup(tmp_path):
    settings = Settings(tmp_path / "runtime")
    settings.prepare()
    db = Database(settings.data_dir / "index.sqlite")
    root = tmp_path / "library"
    root.mkdir()
    source = root / "source.wav"
    generate(source, "-f", "lavfi", "-i", "sine=frequency=500:duration=12")
    library = db.register_library(root)
    indexer = Indexer(db, settings, TestOnlyModel())
    # Synthetic signal tests transaction semantics, not real speech quality.
    indexer.windows = lambda path: [(0, 10000, np.ones(160000, dtype=np.float32))]
    return db, indexer, library, source


def test_incremental_scan_does_not_duplicate(setup):
    db, indexer, library, source = setup
    indexer.run(db.enqueue("index", {"library_id": library}))
    before = db.all("SELECT * FROM segment")
    indexer.run(db.enqueue("index", {"library_id": library}))
    assert len(db.all("SELECT * FROM segment")) == len(before) == 1


def test_changed_source_discards_staging(setup):
    db, indexer, library, source = setup
    original = indexer.model.embed_samples

    def mutate(audio):
        source.write_bytes(source.read_bytes() + b"change")
        return original(audio)
    indexer.model.embed_samples = mutate
    indexer.run(db.enqueue("index", {"library_id": library}))
    assert not db.all("SELECT * FROM segment")
    assert db.one("SELECT status FROM asset")["status"] == "failed"


def test_crash_keeps_previous_generation(setup):
    db, indexer, library, source = setup
    indexer.run(db.enqueue("index", {"library_id": library}))
    previous = db.one("SELECT active_revision FROM asset")["active_revision"]
    source.write_bytes(source.read_bytes() + b"change")
    indexer.model.embed_samples = lambda audio: (_ for _ in ()).throw(MediaError("test failure"))
    indexer.run(db.enqueue("index", {"library_id": library}))
    assert db.one("SELECT active_revision FROM asset")["active_revision"] == previous
    assert len(db.all("SELECT * FROM segment")) == 1


def test_restart_recovers_running(setup):
    db, indexer, library, source = setup
    job = db.enqueue("index", {"library_id": library})
    db.execute("UPDATE job SET status='running' WHERE id=?", (job,))
    db.recover()
    assert db.get_job(job)["status"] == "interrupted"
    db.retry_job(job)
    assert db.get_job(job)["status"] == "queued"


def test_cancel_never_activates_partial(setup):
    db, indexer, library, source = setup
    job = db.enqueue("index", {"library_id": library})
    original = indexer.model.embed_samples

    def cancel(audio):
        db.cancel(job)
        return original(audio)
    indexer.model.embed_samples = cancel
    indexer.run(job)
    assert db.get_job(job)["status"] == "cancelled"
    assert not db.all("SELECT * FROM segment")


def test_missing_source_invalidates_active_generation(setup):
    db, indexer, library, source = setup
    indexer.run(db.enqueue("index", {"library_id": library}))
    source.unlink()
    indexer.run(db.enqueue("index", {"library_id": library}))
    asset = db.one("SELECT * FROM asset")
    assert asset["status"] == "missing" and asset["active_revision"] is None
    assert len(db.all("SELECT * FROM segment")) == 1  # Historical provenance is retained.

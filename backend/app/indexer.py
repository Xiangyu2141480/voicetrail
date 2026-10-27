import json
import time
from pathlib import Path

import numpy as np

from .db import new_id
from .embedding import segment_windows
from .media import MediaError, extract_audio, fingerprint

EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".aiff",
              ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wma"}


def registered_path(db, asset_id):
    asset = db.one("SELECT a.*,l.root FROM asset a JOIN library l ON a.library_id=l.id "
                   "WHERE a.id=?", (asset_id,))
    if not asset:
        raise MediaError("Registered asset not found.")
    root = Path(asset["root"])
    if root.resolve() != root:
        raise MediaError("Registered library location changed; register its new location.")
    path = (root / asset["relative_path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise MediaError("Source is missing or outside the registered library.")
    return path, asset


class Indexer:
    def __init__(self, db, settings, model):
        self.db, self.settings, self.model = db, settings, model
        self.windows = segment_windows

    def cancelled(self, job_id):
        return self.db.get_job(job_id)["cancel_requested"]

    def run(self, job_id):
        job = self.db.get_job(job_id)
        payload = json.loads(job["payload"])
        library_id = payload["library_id"]
        root = Path(self.db.one("SELECT root FROM library WHERE id=?", (library_id,))["root"])
        if not root.is_dir() or root.resolve() != root:
            raise MediaError("Registered directory is missing or changed; register it again.")
        files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS
                       and p.resolve().is_relative_to(root.resolve()))
        present = {str(p.relative_to(root)) for p in files}
        for asset in self.db.all("SELECT id,relative_path FROM asset WHERE library_id=?",
                                 (library_id,)):
            if asset["relative_path"] not in present:
                self.db.execute("UPDATE asset SET status='missing',active_revision=NULL,"
                                "error='Source missing; original was not deleted by VoiceTrail.' "
                                "WHERE id=?", (asset["id"],))
        for relative in sorted(present):
            self.db.execute("INSERT INTO asset(id,library_id,relative_path) VALUES(?,?,?) "
                            "ON CONFLICT(library_id,relative_path) DO NOTHING",
                            (new_id(), library_id, relative))
        self.db.execute("UPDATE job SET status='running',total=?,processed=0,error=NULL WHERE id=?",
                        (len(files), job_id))
        errors = 0
        for processed, source in enumerate(files, 1):
            if self.cancelled(job_id):
                break
            relative = str(source.relative_to(root))
            asset = self.db.one("SELECT * FROM asset WHERE library_id=? AND relative_path=?",
                                (library_id, relative))
            if not asset:
                asset = {"id": new_id(), "active_revision": None}
                self.db.execute("INSERT INTO asset(id,library_id,relative_path) VALUES(?,?,?)",
                                (asset["id"], library_id, relative))
            normalized = self.settings.data_dir / "tmp" / f"{new_id()}.wav"
            try:
                before = fingerprint(source)
                old = self.db.one("SELECT * FROM source_revision WHERE id=?",
                                  (asset["active_revision"],)) if asset["active_revision"] else None
                info = self.model.info
                if (old and old["sha256"] == before["sha256"] and old["model_id"] == info.id
                        and old["model_revision"] == info.revision
                        and old["preprocessing_version"] == info.preprocessing_version):
                    self.db.execute("UPDATE asset SET status='completed',error=NULL WHERE id=?",
                                    (asset["id"],))
                else:
                    self.db.execute("UPDATE asset SET status='running',error=NULL WHERE id=?",
                                    (asset["id"],))
                    duration = extract_audio(source, normalized).duration_ms
                    segments = [(start, end, self.model.embed_samples(audio))
                                for start, end, audio in self.windows(normalized)]
                    if not segments:
                        raise MediaError("No usable speech windows detected.")
                    after = fingerprint(source)
                    if before != after:
                        raise MediaError("Source changed during indexing; retry this file.")
                    if self.cancelled(job_id):
                        self.db.execute("UPDATE asset SET status='cancelled' WHERE id=?",
                                        (asset["id"],))
                        break
                    revision = new_id()
                    # Generation activation is a single transaction; prior annotations persist.
                    with self.db.connect() as c:
                        c.execute("INSERT INTO source_revision VALUES(?,?,?,?,?,?,?,?,?)",
                                  (revision, asset["id"], after["sha256"], json.dumps(after),
                                   info.id, info.revision, info.preprocessing_version,
                                   duration, time.time()))
                        for start, end, vector in segments:
                            c.execute("INSERT INTO segment VALUES(?,?,?,?,?,?,?,?,?)",
                                      (new_id(), asset["id"], revision, start, end, info.id,
                                       info.revision, info.preprocessing_version,
                                       np.asarray(vector, dtype="<f4").tobytes()))
                        c.execute("UPDATE asset SET active_revision=?,status='completed',error=NULL "
                                  "WHERE id=?", (revision, asset["id"]))
            except (MediaError, OSError) as exc:
                errors += 1
                self.db.execute("UPDATE asset SET status='failed',error=? WHERE id=?",
                                (str(exc) if isinstance(exc, MediaError) else
                                 "Source is unavailable; check it and retry.", asset["id"]))
            finally:
                normalized.unlink(missing_ok=True)
            self.db.execute("UPDATE job SET processed=? WHERE id=?", (processed, job_id))
        status = "cancelled" if self.cancelled(job_id) else "completed"
        self.db.execute("UPDATE job SET status=?,error=? WHERE id=?",
                        (status, f"{errors} files failed; see file statuses." if errors else None,
                         job_id))

import json
import os
import shutil
import time
import zipfile

from .candidates import candidate
from .db import new_id
from .indexer import registered_path
from .media import MediaError, extract_audio, fingerprint


def valid_source(db, asset_id, revision=None):
    path, asset = registered_path(db, asset_id)
    revision = revision or asset["active_revision"]
    if asset["status"] != "completed" or not revision or revision != asset["active_revision"]:
        raise MediaError("Source index is stale or unavailable; reindex and search again.")
    stored = db.one("SELECT * FROM source_revision WHERE id=?", (revision,))
    before = fingerprint(path)
    if before["sha256"] != stored["sha256"]:
        raise MediaError("Source changed since indexing; reindex and search again.")
    return path, before


class Exporter:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def run(self, job_id):
        identifiers = list(dict.fromkeys(json.loads(self.db.get_job(job_id)["payload"])[
            "candidate_ids"]))
        export_id = new_id()
        folder = self.settings.data_dir / "tmp" / export_id
        folder.mkdir()
        target = self.settings.data_dir / "exports" / f"{export_id}.zip"
        staging = folder / "archive.zip"
        self.db.execute("UPDATE job SET status='running',total=?,processed=0 WHERE id=?",
                        (len(identifiers), job_id))
        try:
            clips = []
            for i, identifier in enumerate(identifiers):
                if self.db.get_job(job_id)["cancel_requested"]:
                    self.db.execute("UPDATE job SET status='cancelled' WHERE id=?", (job_id,))
                    return
                row = candidate(self.db, identifier)
                if not row:
                    raise MediaError("Selected candidate no longer exists.")
                source, before = valid_source(self.db, row["asset_id"], row["source_revision"])
                name = f"clip-{i + 1:03d}.wav"
                info = extract_audio(source, folder / name, row["start_ms"], row["end_ms"])
                if fingerprint(source) != before:
                    raise MediaError("Source changed during export; retry after indexing.")
                clips.append({**row, "export_file": name, "source_sha256": before["sha256"],
                              "sample_rate": info.sample_rate, "channels": info.channels,
                              "encoding": "PCM_S16LE", "duration_ms": info.duration_ms})
                self.db.execute("UPDATE job SET processed=? WHERE id=?", (i + 1, job_id))
            (folder / "manifest.json").write_text(
                json.dumps({"format_version": 1, "clips": clips}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name in ["manifest.json", *[clip["export_file"] for clip in clips]]:
                    archive.write(folder / name, name)
            if self.db.get_job(job_id)["cancel_requested"]:
                self.db.execute("UPDATE job SET status='cancelled' WHERE id=?", (job_id,))
                return
            os.replace(staging, target)
            try:
                with self.db.connect() as connection:
                    connection.execute("INSERT INTO export VALUES(?,?,?)",
                                       (export_id, job_id, time.time()))
                    connection.execute("UPDATE job SET status='completed',result_id=? WHERE id=?",
                                       (export_id, job_id))
            except BaseException:
                target.unlink(missing_ok=True)
                raise
        finally:
            shutil.rmtree(folder, ignore_errors=True)

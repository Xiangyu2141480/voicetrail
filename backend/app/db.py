import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS library(id TEXT PRIMARY KEY, root TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS asset(
 id TEXT PRIMARY KEY, library_id TEXT NOT NULL REFERENCES library(id), relative_path TEXT NOT NULL,
 active_revision TEXT, status TEXT NOT NULL DEFAULT 'queued', error TEXT,
 UNIQUE(library_id, relative_path));
CREATE TABLE IF NOT EXISTS source_revision(
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES asset(id), sha256 TEXT NOT NULL,
 fingerprint TEXT NOT NULL, model_id TEXT NOT NULL, model_revision TEXT NOT NULL,
 preprocessing_version TEXT NOT NULL, duration_ms INTEGER NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS segment(
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES asset(id),
 source_revision TEXT NOT NULL REFERENCES source_revision(id),
 start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL, model_id TEXT NOT NULL,
 model_revision TEXT NOT NULL, preprocessing_version TEXT NOT NULL, embedding BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS job(
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
 processed INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0, error TEXT,
 cancel_requested INTEGER NOT NULL DEFAULT 0, result_id TEXT, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS reference(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, duration_ms INTEGER NOT NULL,
 model_id TEXT NOT NULL, model_revision TEXT NOT NULL, preprocessing_version TEXT NOT NULL,
 embedding BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS search_run(
 id TEXT PRIMARY KEY, reference_id TEXT NOT NULL REFERENCES reference(id),
 library_id TEXT NOT NULL REFERENCES library(id), created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS candidate(
 id TEXT PRIMARY KEY, reference_id TEXT NOT NULL REFERENCES reference(id),
 segment_id TEXT NOT NULL REFERENCES segment(id), similarity REAL NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'undecided', UNIQUE(reference_id, segment_id));
CREATE TABLE IF NOT EXISTS search_result(
 run_id TEXT NOT NULL REFERENCES search_run(id), candidate_id TEXT NOT NULL REFERENCES candidate(id),
 rank INTEGER NOT NULL, PRIMARY KEY(run_id,candidate_id));
CREATE TABLE IF NOT EXISTS export(
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES job(id), created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS segment_generation ON segment(asset_id,source_revision);
PRAGMA user_version=1;
"""


def new_id():
    return uuid.uuid4().hex


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("Database version is newer than this application.")
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def all(self, sql, args=()):
        with self.connect() as c:
            return [dict(row) for row in c.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        rows = self.all(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=()):
        with self.connect() as c:
            c.execute(sql, args)

    def register_library(self, root: Path):
        found = self.one("SELECT id FROM library WHERE root=?", (str(root.resolve()),))
        if found:
            return found["id"]
        identifier = new_id()
        self.execute("INSERT INTO library VALUES(?,?)", (identifier, str(root.resolve())))
        return identifier

    def enqueue(self, kind, payload):
        identifier = new_id()
        self.execute("INSERT INTO job(id,kind,payload,status,created) VALUES(?,?,?,'queued',?)",
                     (identifier, kind, json.dumps(payload), time.time()))
        return identifier

    def get_job(self, identifier):
        return self.one("SELECT * FROM job WHERE id=?", (identifier,))

    def cancel(self, identifier):
        self.execute("UPDATE job SET cancel_requested=1 WHERE id=?", (identifier,))

    def recover(self):
        self.execute("UPDATE job SET status='interrupted',error='Service stopped; retry this job.' "
                     "WHERE status='running'")
        self.execute("UPDATE asset SET status='queued',error='Interrupted; reindex to resume.' "
                     "WHERE status='running'")

    def retry_job(self, identifier):
        self.execute("UPDATE job SET status='queued',error=NULL,cancel_requested=0,processed=0 "
                     "WHERE id=? AND status IN ('interrupted','failed','cancelled')", (identifier,))

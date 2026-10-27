import time

import numpy as np

from .db import new_id
from .media import MediaError
from .search import rank_segments

CANDIDATE_SQL = """
SELECT c.id,c.similarity,c.review_status,s.asset_id,s.source_revision,s.start_ms,s.end_ms,
a.relative_path AS source_name FROM candidate c JOIN segment s ON c.segment_id=s.id
JOIN asset a ON s.asset_id=a.id
"""


def candidate(db, identifier):
    return db.one(CANDIDATE_SQL + " WHERE c.id=?", (identifier,))


def search(db, model_info, reference_id, library_id, top_k):
    ref = db.one("SELECT * FROM reference WHERE id=?", (reference_id,))
    if not ref:
        raise MediaError("Reference not found; choose or upload a reference.")
    version = (model_info.id, model_info.revision, model_info.preprocessing_version)
    if (ref["model_id"], ref["model_revision"], ref["preprocessing_version"]) != version:
        raise MediaError("Reference model version changed; create a new reference.")
    rows = db.all(
        "SELECT s.* FROM segment s JOIN asset a ON s.asset_id=a.id "
        "WHERE a.library_id=? AND a.status='completed' AND s.source_revision=a.active_revision "
        "AND s.model_id=? AND s.model_revision=? AND s.preprocessing_version=? ORDER BY s.id",
        (library_id, *version))
    run = new_id()
    with db.connect() as connection:
        connection.execute("INSERT INTO search_run VALUES(?,?,?,?)",
                           (run, reference_id, library_id, time.time()))
        if rows:
            ranked = rank_segments(np.frombuffer(ref["embedding"], dtype="<f4"),
                                   np.stack([np.frombuffer(r["embedding"], dtype="<f4")
                                             for r in rows]), top_k)
            for rank, (index, similarity) in enumerate(ranked):
                segment_id = rows[index]["id"]
                connection.execute(
                    "INSERT INTO candidate(id,reference_id,segment_id,similarity) VALUES(?,?,?,?) "
                    "ON CONFLICT(reference_id,segment_id) DO UPDATE SET similarity=excluded.similarity",
                    (new_id(), reference_id, segment_id, similarity))
                identifier = connection.execute(
                    "SELECT id FROM candidate WHERE reference_id=? AND segment_id=?",
                    (reference_id, segment_id)).fetchone()[0]
                connection.execute("INSERT INTO search_result VALUES(?,?,?)",
                                   (run, identifier, rank))
    results = db.all(CANDIDATE_SQL +
                     " JOIN search_result sr ON sr.candidate_id=c.id WHERE sr.run_id=? "
                     "ORDER BY sr.rank", (run,))
    return {"run_id": run, "candidates": results}

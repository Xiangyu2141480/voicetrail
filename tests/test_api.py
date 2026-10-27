import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.db import new_id
from backend.app.main import create_app
from tests.test_indexer import setup  # noqa: F401


def client_for(db, indexer):
    return TestClient(create_app(indexer.settings, model=indexer.model, start_worker=False),
                      base_url="http://127.0.0.1:8765")


def authorize(client):
    health = client.get("/api/health").json()
    return {"X-VoiceTrail-Session": health["session_token"]}


@pytest.fixture
def indexed(setup):  # noqa: F811 - pytest fixture registration import
    db, indexer, library, source = setup
    indexer.run(db.enqueue("index", {"library_id": library}))
    ref = new_id()
    info = indexer.model.info
    db.execute("INSERT INTO reference VALUES(?,?,?,?,?,?,?)",
               (ref, "Isolated test reference", 10000, info.id, info.revision,
                info.preprocessing_version, np.ones(192, dtype="<f4").tobytes()))
    return db, indexer, library, source, ref


def test_search_returns_source_timestamps_and_review_survives_restart(indexed):
    db, indexer, library, source, ref = indexed
    with client_for(db, indexer) as client:
        headers = authorize(client)
        result = client.post("/api/search", json={"reference_id": ref,
                             "library_id": library, "top_k": 5}, headers=headers)
        assert result.status_code == 200, result.text
        candidate = result.json()["candidates"][0]
        assert candidate["start_ms"] == 0 and candidate["end_ms"] == 10000
        assert candidate["source_revision"] == db.one("SELECT active_revision FROM asset")[
            "active_revision"]
        response = client.patch(f"/api/candidates/{candidate['id']}",
                                json={"review_status": "confirmed"}, headers=headers)
        assert response.status_code == 200
    with client_for(db, indexer) as restarted:
        headers = authorize(restarted)
        again = restarted.post("/api/search", json={"reference_id": ref,
                               "library_id": library}, headers=headers).json()["candidates"][0]
        assert again["id"] == candidate["id"]
        assert again["review_status"] == "confirmed"
        assert restarted.get("/api/references").json()[0]["id"] == ref


def test_unregistered_asset_and_path_escape_denied(indexed, tmp_path):
    db, indexer, library, source, ref = indexed
    with client_for(db, indexer) as client:
        authorize(client)
        assert client.get("/api/assets/unknown/media").status_code == 404
        outsider = tmp_path / "outside.wav"
        outsider.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(outsider)
        asset = db.one("SELECT id FROM asset")["id"]
        assert client.get(f"/api/assets/{asset}/media").status_code == 422


def test_cross_origin_write_and_dns_rebinding_denied(indexed):
    db, indexer, library, source, ref = indexed
    with client_for(db, indexer) as client:
        headers = authorize(client)
        payload = {"root": str(source.parent)}
        assert client.post("/api/libraries", json=payload).status_code == 403
        assert client.post("/api/libraries", json=payload, headers={
            **headers, "Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 403
        assert client.get("/api/health", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert client.post("/api/libraries", json=payload, headers=headers).status_code == 200


def test_stale_preview_and_removed_source_denied(indexed):
    db, indexer, library, source, ref = indexed
    asset = db.one("SELECT id FROM asset")["id"]
    with client_for(db, indexer) as client:
        headers = authorize(client)
        preview = client.get(f"/api/assets/{asset}/media?start_ms=0&end_ms=10000")
        assert preview.status_code == 200 and preview.content[:4] == b"RIFF"
        source.write_bytes(source.read_bytes() + b"changed")
        assert client.get(f"/api/assets/{asset}/media").status_code == 422
        assert client.delete(f"/api/assets/{asset}", headers=headers).status_code == 200
        assert source.is_file()
        assert client.get(f"/api/assets/{asset}/media").status_code == 404


def test_short_reference_rejected(indexed):
    db, indexer, library, source, ref = indexed
    with client_for(db, indexer) as client:
        response = client.post("/api/references/from-asset",
                               json={"asset_id": db.one("SELECT id FROM asset")["id"],
                                     "start_ms": 0, "end_ms": 2000},
                               headers=authorize(client))
        assert response.status_code == 422 and "3" in response.json()["detail"]

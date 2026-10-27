import json
import secrets
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import schemas
from .candidates import candidate, search
from .config import Settings
from .db import Database, new_id
from .embedding import EmbeddingModel
from .export import Exporter, valid_source
from .indexer import Indexer, registered_path
from .jobs import Worker
from .media import MediaError, extract_audio, fingerprint
from .references import create_reference


def create_app(settings=None, model=None, start_worker=True):
    settings = settings or Settings.from_env()
    settings.prepare()
    db = Database(settings.data_dir / "index.sqlite")
    injected_model = model is not None
    model = model or EmbeddingModel(settings.data_dir / "models")
    indexer, exporter = Indexer(db, settings, model), Exporter(db, settings)
    worker = Worker(db, {
        "index": indexer.run, "export": exporter.run,
        "model": lambda job: prepare_model(job),
    })
    token = secrets.token_urlsafe(32)
    host = f"127.0.0.1:{settings.port}"
    origins = (None, f"http://{host}") + (("http://127.0.0.1:5173",) if settings.dev_ui else ())

    def prepare_model(job_id):
        offline = json.loads(db.get_job(job_id)["payload"]).get("offline", False)
        model.load(offline=offline)
        db.execute("UPDATE job SET status='completed',processed=1,total=1 WHERE id=?", (job_id,))

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            if not injected_model and (model.cache_dir / "embedding_model.ckpt").is_file():
                db.enqueue("model", {"offline": True})
            worker.start()
        yield
        if start_worker:
            worker.stop()

    app = FastAPI(title="VoiceTrail", version="0.1.0-alpha.1", lifespan=lifespan)
    app.state.db = db
    app.state.model = model

    @app.middleware("http")
    async def local_session(request: Request, call_next):
        # Host and Fetch Metadata reject DNS rebinding and cross-site GETs too.
        if (request.headers.get("host") != host
                or request.headers.get("sec-fetch-site") == "cross-site"
                or request.headers.get("origin") not in origins):
            return JSONResponse({"detail": "Only the local VoiceTrail page may access this service."},
                                status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            supplied = request.headers.get("x-voicetrail-session", "")
            cookie = request.cookies.get("voicetrail_session", "")
            if not (secrets.compare_digest(supplied, token) and
                    secrets.compare_digest(cookie, token)):
                return JSONResponse({"detail": "Local session expired; refresh this page."},
                                    status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; "
            "object-src 'none'; base-uri 'self'")
        return response

    @app.exception_handler(MediaError)
    async def media_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    def require(table, identifier):
        # Table is supplied only by these fixed routes, never by request data.
        found = db.one(f"SELECT * FROM {table} WHERE id=?", (identifier,))
        if not found:
            raise HTTPException(404, "Registered item not found.")
        return found

    @app.get("/api/health", response_model=schemas.Health)
    def health(response: Response):
        response.set_cookie("voicetrail_session", token, httponly=True, samesite="strict")
        response.headers["Cache-Control"] = "no-store"
        return {"status": "ok", "ffmpeg": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
                "model": model.status(), "session_token": token}

    @app.post("/api/model/prepare", response_model=schemas.JobCreated)
    def model_prepare():
        existing = db.one("SELECT id FROM job WHERE kind='model' AND status IN "
                          "('queued','running') ORDER BY created DESC LIMIT 1")
        return {"job_id": existing["id"] if existing else db.enqueue("model", {"offline": False})}

    @app.get("/api/libraries", response_model=list[schemas.Library])
    def libraries():
        return [{"id": row["id"], "name": Path(row["root"]).name}
                for row in db.all("SELECT * FROM library")]

    @app.post("/api/libraries", response_model=schemas.Library)
    def register(payload: schemas.LibraryInput):
        root = Path(payload.root).expanduser().resolve()
        if not root.is_dir():
            raise MediaError("Directory is unavailable; enter an existing local folder.")
        return {"id": db.register_library(root), "name": root.name}

    @app.get("/api/libraries/{identifier}/assets", response_model=list[schemas.Asset])
    def assets(identifier: str):
        require("library", identifier)
        return db.all("SELECT * FROM asset WHERE library_id=? ORDER BY relative_path", (identifier,))

    @app.post("/api/libraries/{identifier}/index", response_model=schemas.JobCreated)
    def enqueue_index(identifier: str):
        require("library", identifier)
        if model.status()["status"] != "ready":
            raise MediaError("Model is not ready; prepare it before indexing.")
        return {"job_id": db.enqueue("index", {"library_id": identifier})}

    @app.get("/api/jobs", response_model=list[schemas.Job])
    def jobs():
        return db.all("SELECT * FROM job ORDER BY created DESC LIMIT 50")

    @app.get("/api/jobs/{identifier}", response_model=schemas.Job)
    def job(identifier: str):
        return require("job", identifier)

    @app.post("/api/jobs/{identifier}/cancel", response_model=schemas.Job)
    def cancel(identifier: str):
        require("job", identifier)
        db.cancel(identifier)
        return db.get_job(identifier)

    @app.post("/api/jobs/{identifier}/retry", response_model=schemas.Job)
    def retry(identifier: str):
        require("job", identifier)
        db.retry_job(identifier)
        return db.get_job(identifier)

    @app.get("/api/references", response_model=list[schemas.Reference])
    def references():
        return db.all("SELECT id,name,duration_ms FROM reference")

    @app.post("/api/references", response_model=schemas.Reference)
    def upload_reference(file: UploadFile = File(...)):
        source = settings.data_dir / "tmp" / new_id()
        try:
            size = 0
            with source.open("wb") as output:
                for block in iter(lambda: file.file.read(1024 * 1024), b""):
                    size += len(block)
                    if size > 128 * 1024 * 1024:
                        raise MediaError("Reference upload exceeds 128 MiB; trim it locally first.")
                    output.write(block)
            name = Path((file.filename or "Reference").replace("\\", "/")).name
            return create_reference(db, settings, model, source, name[:255])
        finally:
            source.unlink(missing_ok=True)
            file.file.close()

    @app.post("/api/references/from-asset", response_model=schemas.Reference)
    def reference_range(payload: schemas.ReferenceRange):
        require("asset", payload.asset_id)
        source, asset = registered_path(db, payload.asset_id)
        return create_reference(db, settings, model, source, Path(asset["relative_path"]).name,
                                payload.start_ms, payload.end_ms)

    @app.post("/api/search", response_model=schemas.SearchResponse)
    def query(payload: schemas.SearchInput):
        require("library", payload.library_id)
        return search(db, model.info, payload.reference_id, payload.library_id, payload.top_k)

    @app.patch("/api/candidates/{identifier}", response_model=schemas.Candidate)
    def review(identifier: str, payload: schemas.ReviewInput):
        require("candidate", identifier)
        db.execute("UPDATE candidate SET review_status=? WHERE id=?",
                   (payload.review_status, identifier))
        return candidate(db, identifier)

    @app.get("/api/assets/{identifier}/media")
    def media(identifier: str, start_ms: int = 0, end_ms: int | None = None,
              revision: str | None = None):
        row = require("asset", identifier)
        if row["status"] == "removed":
            raise HTTPException(404, "Asset was removed from the index.")
        source, before = valid_source(db, identifier, revision)
        stored = require("source_revision", row["active_revision"])
        end_ms = stored["duration_ms"] if end_ms is None else end_ms
        if start_ms < 0 or end_ms - start_ms > 60000:
            raise MediaError("Preview range must be positive and at most 60 seconds.")
        preview = settings.data_dir / "previews" / (
            f"{row['active_revision']}-{start_ms}-{end_ms}.wav")
        if not preview.exists():
            extract_audio(source, preview, start_ms, end_ms)
            if fingerprint(source) != before:
                preview.unlink(missing_ok=True)
                raise MediaError("Source changed during preview; reindex.")
        return FileResponse(preview, media_type="audio/wav",
                            headers={"Cache-Control": "no-store"})

    @app.delete("/api/assets/{identifier}")
    def remove(identifier: str):
        asset = require("asset", identifier)
        running = db.one("SELECT id FROM job WHERE kind='index' AND status IN ('queued','running') "
                         "AND json_extract(payload,'$.library_id')=?", (asset["library_id"],))
        if running:
            raise HTTPException(409, "Cancel indexing before removing an asset.")
        db.execute("UPDATE asset SET status='removed',active_revision=NULL,error=NULL WHERE id=?",
                   (identifier,))
        return {"status": "removed"}

    @app.post("/api/exports", response_model=schemas.JobCreated)
    def enqueue_export(payload: schemas.ExportInput):
        for identifier in payload.candidate_ids:
            require("candidate", identifier)
        return {"job_id": db.enqueue("export", payload.model_dump())}

    @app.get("/api/exports/{identifier}/download")
    def download(identifier: str):
        require("export", identifier)
        path = settings.data_dir / "exports" / f"{identifier}.zip"
        if not path.is_file():
            raise HTTPException(404, "Export file is unavailable; export the selection again.")
        return FileResponse(path, media_type="application/zip",
                            filename=f"voicetrail-{identifier[:8]}.zip")

    dist = Path(__file__).resolve().parents[2] / "frontend/dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app

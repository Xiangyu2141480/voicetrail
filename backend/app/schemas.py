"""The shared HTTP contract; scripts/contracts.py emits TypeScript from OpenAPI."""
from typing import Literal

from pydantic import BaseModel, Field


class LibraryInput(BaseModel):
    root: str = Field(min_length=1, max_length=4096)


class Library(BaseModel):
    id: str
    name: str


class Asset(BaseModel):
    id: str
    library_id: str
    relative_path: str
    active_revision: str | None
    status: str
    error: str | None


class Job(BaseModel):
    id: str
    kind: str
    status: str
    processed: int
    total: int
    error: str | None
    result_id: str | None


class JobCreated(BaseModel):
    job_id: str


class Reference(BaseModel):
    id: str
    name: str
    duration_ms: int


class ReferenceRange(BaseModel):
    asset_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class SearchInput(BaseModel):
    reference_id: str
    library_id: str
    top_k: int = Field(default=20, ge=1, le=200)


class Candidate(BaseModel):
    id: str
    asset_id: str
    source_revision: str
    source_name: str
    start_ms: int
    end_ms: int
    similarity: float
    review_status: Literal["confirmed", "rejected", "undecided"]


class SearchResponse(BaseModel):
    run_id: str
    candidates: list[Candidate]


class ReviewInput(BaseModel):
    review_status: Literal["confirmed", "rejected", "undecided"]


class ExportInput(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=200)


class ModelStatus(BaseModel):
    id: str
    revision: str
    preprocessing_version: str
    dimension: int
    status: str
    error: str | None
    source: str
    downloaded_bytes: int
    total_bytes: int | None


class Health(BaseModel):
    status: str
    ffmpeg: bool
    model: ModelStatus
    session_token: str

"""Pydantic models and row serialization for the v1 API contract."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

DEFAULT_PROGRESS: dict[str, Any] = {
    "percent": None,
    "downloaded_bytes": None,
    "total_bytes": None,
    "speed_bps": None,
    "eta_seconds": None,
    "stage": None,
}


class InfoRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class QualityOut(BaseModel):
    id: str
    kind: Literal["video", "audio"]
    height: int | None = None


class InfoOut(BaseModel):
    url: str
    platform: Literal["youtube", "bilibili"]
    video_id: str
    title: str
    uploader: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None
    webpage_url: str
    qualities: list[QualityOut]


class JobCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    quality: str = "best"


class ProgressOut(BaseModel):
    percent: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bps: float | None = None
    eta_seconds: int | None = None
    stage: Literal["video", "audio"] | None = None


class FileOut(BaseModel):
    name: str
    size_bytes: int
    content_type: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class JobOut(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed", "canceled"]
    phase: Literal["downloading", "postprocessing"] | None = None
    url: str
    platform: Literal["youtube", "bilibili"]
    title: str | None = None
    quality: str
    progress: ProgressOut
    file: FileOut | None = None
    error: ErrorDetail | None = None
    cancel_requested: bool
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    expires_at: str


class JobListOut(BaseModel):
    items: list[JobOut]


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


def _load_json(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def job_public(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a jobs row into the stable public representation."""
    progress = _load_json(row.get("progress_json"), dict(DEFAULT_PROGRESS))
    merged = {**DEFAULT_PROGRESS, **progress}
    file_info = None
    if row.get("output_filename") and row.get("output_size_bytes") is not None:
        file_info = {
            "name": row["output_filename"],
            "size_bytes": row["output_size_bytes"],
            "content_type": row.get("content_type") or "application/octet-stream",
        }
    error = _load_json(row.get("error_json"), {})
    return {
        "id": row["id"],
        "status": row["status"],
        "phase": row.get("phase"),
        "url": row["url"],
        "platform": row["platform"],
        "title": row.get("title"),
        "quality": row["quality"],
        "progress": merged,
        "file": file_info,
        "error": error or None,
        "cancel_requested": bool(row.get("cancel_requested")),
        "created_at": row["created_at"],
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "expires_at": row["expires_at"],
    }

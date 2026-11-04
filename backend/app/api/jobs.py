from __future__ import annotations

import queue
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse

from app.api.deps import no_store, require_token
from app.core import timeutil
from app.core.urls import normalize_url
from app.downloader.formats import validate_quality
from app.downloader.manager import JobManager
from app.errors import ApiError
from app.schemas import JobCreate, JobListOut, JobOut, job_public
from app.storage import files, jobs_repo

router = APIRouter(dependencies=[Depends(require_token), Depends(no_store)])


def _get_job_or_404(db_path, job_id: str) -> dict[str, Any]:
    row = jobs_repo.get_job(db_path, job_id)
    if row is None:
        raise ApiError(404, "job_not_found")
    return row


@router.post("/jobs", status_code=201, response_model=JobOut)
def create_job(payload: JobCreate, request: Request, response: Response) -> dict[str, Any]:
    settings = request.app.state.settings
    manager: JobManager = request.app.state.manager
    downloader = request.app.state.downloader

    normalized = normalize_url(payload.url)
    quality = validate_quality(payload.quality)

    if files.disk_free_bytes(settings.data_dir) < int(settings.max_filesize_bytes * 1.1):
        raise ApiError(507, "insufficient_storage")

    cached = downloader.cached_info(normalized.url)
    job_id = uuid.uuid4().hex
    created = timeutil.now()
    jobs_repo.create_job(
        settings.db_path,
        job_id=job_id,
        url=normalized.url,
        platform=normalized.platform,
        quality=quality,
        title=cached.title if cached else None,
        thumbnail_url=cached.thumbnail_url if cached else None,
        progress={
            "percent": None,
            "downloaded_bytes": None,
            "total_bytes": None,
            "speed_bps": None,
            "eta_seconds": None,
            "stage": None,
        },
        created_at=timeutil.iso(created),
        expires_at=timeutil.iso(timeutil.plus_hours(created, settings.job_ttl_hours)),
    )
    try:
        manager.submit(job_id)
    except queue.Full:
        jobs_repo.delete_job(settings.db_path, job_id)
        raise ApiError(503, "queue_full", headers={"Retry-After": "10"}) from None

    row = _get_job_or_404(settings.db_path, job_id)
    response.headers["Location"] = f"/api/v1/jobs/{job_id}"
    return job_public(row)


@router.get("/jobs", response_model=JobListOut)
def list_jobs(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    settings = request.app.state.settings
    rows = jobs_repo.list_jobs(settings.db_path, limit)
    return {"items": [job_public(row) for row in rows]}


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return job_public(_get_job_or_404(settings.db_path, job_id))


@router.post("/jobs/{job_id}/cancel", status_code=202, response_model=JobOut)
def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    manager: JobManager = request.app.state.manager
    return job_public(manager.request_cancel(job_id))


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, request: Request) -> Response:
    settings = request.app.state.settings
    row = _get_job_or_404(settings.db_path, job_id)
    if row["status"] in ("queued", "running"):
        raise ApiError(409, "job_not_deletable")
    files.remove_job_dir(files.job_dir(settings, job_id))
    jobs_repo.delete_job(settings.db_path, job_id)
    return Response(status_code=204)


@router.get("/jobs/{job_id}/file")
def get_file(job_id: str, request: Request) -> FileResponse:
    settings = request.app.state.settings
    row = _get_job_or_404(settings.db_path, job_id)
    if row["status"] != "completed":
        raise ApiError(409, "file_not_ready")

    directory = files.job_dir(settings, job_id)
    output = files.find_output(directory)
    if output is None:
        raise ApiError(410, "file_gone")
    root = directory.resolve()
    resolved = output.resolve()
    if root not in resolved.parents:
        raise ApiError(410, "file_gone")

    return FileResponse(
        resolved,
        media_type=row.get("content_type") or files.content_type_for(resolved),
        filename=row.get("output_filename") or resolved.name,
        headers={
            "Cache-Control": "private, max-age=0",
            "X-Content-Type-Options": "nosniff",
        },
    )
